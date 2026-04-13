"""
backend/services/agent/runner.py

smolagents ToolCallingAgent setup and SSE streaming bridge.

Architecture:
- build_agent(stores) constructs a ToolCallingAgent wired to qwen3:14b via LiteLLM.
- run_investigation(agent, task) is an async generator that runs the synchronous
  agent in a background thread, bridges step events through a queue.Queue,
  and yields SSE-compatible dicts for the FastAPI endpoint.

CRITICAL CONSTRAINTS:
- smolagents.agent.run() is SYNCHRONOUS — never call it directly in async code.
- Use threading.Thread + queue.Queue bridge (NOT asyncio.Queue — wrong thread model).
- System prompt MUST start with /no_think to suppress qwen3 thinking tokens.
- num_ctx=8192 is REQUIRED — default 2048 causes silent tool-call JSON truncation.
"""
from __future__ import annotations

import asyncio
import json
import queue
import re
import threading
from typing import Any, AsyncIterator, Optional

from smolagents import LiteLLMModel, ToolCallingAgent

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.services.agent.tools import (
    EnrichIpTool,
    GetEntityProfileTool,
    GetGraphNeighborsTool,
    QueryEventsTool,
    SearchSigmaMatchesTool,
    SearchSimilarIncidentsTool,
)

log = get_logger(__name__)

MAX_STEPS = 10
DEFAULT_TIMEOUT = 90.0

SYSTEM_PROMPT = """/no_think
You are a cybersecurity investigation agent for a SOC analyst.
Your job: analyze a security detection by querying events, enriching suspicious IPs,
checking graph relationships, and searching for similar confirmed incidents.

Follow this investigation strategy:
1. Query events for the detected host to understand what happened.
2. Get the entity profile to assess the host's baseline behaviour.
3. Enrich any suspicious destination IPs to check for known threats.
4. Search for similar confirmed incidents to leverage past analyst decisions.
5. Check graph neighbors for lateral movement indicators.
6. Search Sigma matches to correlate with known detection rules.

After gathering evidence, produce your final answer as valid JSON:
{"verdict": "TP", "confidence": 85, "narrative": "2-3 sentence explanation"}
or
{"verdict": "FP", "confidence": 90, "narrative": "2-3 sentence explanation"}

Be concise. Use only the tools provided. Do not guess — base your verdict on evidence.
"""


def build_agent(stores) -> ToolCallingAgent:
    """
    Construct a ToolCallingAgent wired to qwen3:14b via Ollama/LiteLLM.

    Args:
        stores: Stores container from app.state.stores. Must have:
                stores.duckdb._db_path, stores.sqlite._db_path,
                stores.chroma._data_dir or stores.chroma.persist_dir

    Returns:
        Configured ToolCallingAgent with 6 investigation tools, max_steps=10.
        Note: agent.tools dict contains 7 entries (6 custom + built-in final_answer).
    """
    db_path = stores.duckdb._db_path
    sqlite_path = stores.sqlite._db_path
    # ChromaStore may expose _data_dir or persist_dir depending on init path
    chroma_path = getattr(stores.chroma, "_data_dir", None) or getattr(
        stores.chroma, "persist_dir", str(settings.DATA_DIR) + "/chroma"
    )
    if hasattr(chroma_path, "__str__"):
        chroma_path = str(chroma_path)

    model = LiteLLMModel(
        model_id="ollama_chat/qwen3:14b",
        api_base=str(settings.OLLAMA_HOST),
        api_key="ollama",  # required field even for local; any non-empty string
        num_ctx=8192,  # CRITICAL: prevents silent truncation during tool-call conversations
    )

    tools = [
        QueryEventsTool(db_path=db_path),
        GetEntityProfileTool(db_path=db_path),
        EnrichIpTool(sqlite_path=sqlite_path),
        SearchSigmaMatchesTool(sqlite_path=sqlite_path),
        GetGraphNeighborsTool(sqlite_path=sqlite_path),
        SearchSimilarIncidentsTool(chroma_path=chroma_path),
    ]

    agent = ToolCallingAgent(
        tools=tools,
        model=model,
        max_steps=MAX_STEPS,
    )
    return agent


def _parse_verdict_from_output(text: str) -> Optional[dict]:
    """
    Extract verdict JSON from the agent's final answer text.
    Returns None if parsing fails — caller should yield a fallback verdict.
    """
    if not text:
        return None
    # Find the JSON block — model may wrap it in ```json ... ``` or emit it inline
    match = re.search(r'\{[^{}]*"verdict"[^{}]*\}', text, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        verdict = obj.get("verdict", "").upper()
        if verdict not in ("TP", "FP"):
            return None
        return {
            "verdict": verdict,
            "confidence": int(obj.get("confidence", 50)),
            "narrative": str(obj.get("narrative", text[:200])),
        }
    except (json.JSONDecodeError, ValueError):
        return None


async def run_investigation(
    agent: ToolCallingAgent,
    task: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> AsyncIterator[dict[str, Any]]:
    """
    Run the agentic investigation and yield SSE-compatible event dicts.

    Yields events:
      {"event": "tool_call",  "data": json_str}  — each tool invocation
      {"event": "reasoning",  "data": json_str}  — LLM reasoning text between calls
      {"event": "verdict",    "data": json_str}  — final TP/FP verdict
      {"event": "limit",      "data": json_str}  — max_calls or timeout reached
      {"event": "done",       "data": "{}"}      — stream complete
      {"event": "error",      "data": json_str}  — agent error

    Thread-safety: agent.run(stream=True) executes in a daemon thread; events
    are communicated via queue.Queue (thread-safe). The async generator polls
    the queue without blocking the event loop.
    """
    event_queue: queue.Queue = queue.Queue()
    final_answer: list[str] = []  # mutable container for cross-thread result capture

    def _run_sync() -> None:
        """Execute the synchronous agent generator in a background thread."""
        try:
            gen = agent.run(task, stream=True, reset=True)
            for step in gen:
                event_queue.put(("step", step))
            # After generator exhausts, retrieve final answer from agent memory
            try:
                from smolagents.memory import FinalAnswerStep

                last_steps = agent.memory.steps if hasattr(agent, "memory") else []
                for s in reversed(last_steps):
                    if isinstance(s, FinalAnswerStep):
                        final_answer.append(getattr(s, "final_answer", "") or "")
                        break
            except Exception:
                pass
            event_queue.put(("done", None))
        except Exception as exc:
            event_queue.put(("error", str(exc)))

    thread = threading.Thread(target=_run_sync, daemon=True)
    thread.start()

    deadline = asyncio.get_event_loop().time() + timeout
    call_count = 0
    limit_fired = False

    try:
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                yield {"event": "limit", "data": json.dumps({"reason": "timeout"})}
                limit_fired = True
                break

            try:
                kind, payload = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: event_queue.get(timeout=0.1)
                )
            except queue.Empty:
                await asyncio.sleep(0)
                continue

            if kind == "done":
                # Emit verdict from captured final answer or last step model output
                raw_answer = final_answer[0] if final_answer else ""
                verdict_obj = _parse_verdict_from_output(raw_answer)
                if verdict_obj:
                    yield {"event": "verdict", "data": json.dumps(verdict_obj)}
                yield {"event": "done", "data": "{}"}
                break

            elif kind == "error":
                yield {"event": "error", "data": json.dumps({"message": str(payload)})}
                break

            elif kind == "step":
                step = payload
                # Defensively access step attributes — smolagents API varies by version
                tool_calls = getattr(step, "tool_calls", None) or []
                observations = getattr(step, "observations", "") or ""
                model_output = getattr(step, "model_output", "") or ""

                # Emit reasoning text (model thinking before the tool call)
                if model_output and model_output.strip():
                    yield {
                        "event": "reasoning",
                        "data": json.dumps({"text": model_output.strip()}),
                    }

                # Emit each tool call
                for tc in tool_calls:
                    call_count += 1
                    tc_name = getattr(tc, "name", str(tc))
                    tc_args = getattr(tc, "arguments", {}) or {}
                    yield {
                        "event": "tool_call",
                        "data": json.dumps(
                            {
                                "call_number": call_count,
                                "tool_name": tc_name,
                                "arguments": tc_args,
                                "result": str(observations)[:500],
                            }
                        ),
                    }
                    if call_count >= MAX_STEPS:
                        yield {
                            "event": "limit",
                            "data": json.dumps({"reason": "max_calls"}),
                        }
                        limit_fired = True
                        break

                if limit_fired:
                    break

    finally:
        # Let the thread finish naturally (daemon=True ensures it doesn't block shutdown)
        thread.join(timeout=2.0)
