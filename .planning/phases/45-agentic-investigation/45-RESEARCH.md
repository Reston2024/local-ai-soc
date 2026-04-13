# Phase 45: Agentic Investigation - Research

**Researched:** 2026-04-12
**Domain:** smolagents ToolCallingAgent + Ollama LiteLLM + FastAPI SSE streaming + Svelte 5 tabs
**Confidence:** HIGH (core APIs verified via official docs; tool-calling pattern verified via Ollama docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- InvestigationView gets a **second tab: [Summary] [Agent]**. Existing static summary stays on [Summary] tab — zero disruption.
- Agent runs **on demand only** — clicking the [Agent] tab triggers the run.
- After a run completes, result is **cached in memory** (keyed by detection_id). Re-opening shows previous result without re-running.
- **Empty state** (before first run): clean panel with `Run agentic investigation ▶` button and one-line description.
- Each tool call is a **collapsible trace card** — collapsed = tool icon + name + 1-line outcome summary. Expand = full args + formatted result.
- Results inside expanded cards shown as **formatted summaries**, not raw JSON.
- While running between tool calls: LLM chain-of-thought reasoning streams as text between step cards.
- Tool call budget counter in Agent tab header during a run: **`3/10 calls used`**.
- **Distinct Verdict section** pinned at bottom: TP/FP badge + confidence % + 2-3 sentence narrative + Confirm buttons.
- Confirm buttons fire same `submitVerdict()` flow as Phase 44 (`POST /api/feedback`).
- **90s timeout or 10-call limit**: completed cards remain, yellow warning banner above Verdict.
- **Ollama unavailable**: inline error on in-progress card + `Retry ↺` button (full re-run, not resume). Cached result cleared on retry.
- Use smolagents ToolCallingAgent + qwen3:14b via Ollama.
- Memory-only caching (no SQLite persistence) is acceptable for Phase 45.

### Claude's Discretion
- Exact SSE event format (step cards vs reasoning text vs verdict)
- smolagents tool registration syntax and LiteLLM/Ollama adapter config
- Exact icons per tool
- Agent tab CSS layout
- Exact LLM prompt/system message structure for verdict generation
- Whether to cache results in SQLite or memory-only (memory-only acceptable)

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P45-T01 | Define 6 investigation tools: query_events, get_entity_profile, enrich_ip, search_sigma_matches, get_graph_neighbors, search_similar_incidents | Tool class pattern with `Tool.forward()` documented; all 6 tools wrap existing DuckDB/Chroma/SQLite stores |
| P45-T02 | Implement smolagents ToolCallingAgent with sandboxed execution, local Ollama backend | `ToolCallingAgent` + `LiteLLMModel(model_id="ollama_chat/qwen3:14b", api_base=...)` is the verified pattern |
| P45-T03 | POST /api/investigate/agentic — runs agent loop, streams reasoning steps back to client | `anyio.to_thread.run_sync` + `asyncio.Queue` bridge + `EventSourceResponse` from sse-starlette (already installed) |
| P45-T04 | InvestigationView agentic mode — tool calls, intermediate results, final verdict as chain of reasoning | Svelte 5 `$state` runes + new [Agent] tab alongside [Summary]; SSE reader pattern matches existing `chatStream()` |
| P45-T05 | Hard resource limits — max 10 tool calls per investigation, 90s timeout, read-only tools | `max_steps=10` on `agent.run()` + `asyncio.wait_for(..., timeout=90)` wrapping the thread |
</phase_requirements>

---

## Summary

Phase 45 introduces a genuine agentic investigation loop by wiring smolagents `ToolCallingAgent` to `qwen3:14b` through LiteLLM's Ollama adapter. The agent calls six read-only tools that wrap existing DuckDB, Chroma, and SQLite stores. Each tool call, along with the model's chain-of-thought reasoning between calls, is streamed to the frontend via SSE. The final output is a structured TP/FP verdict with a confidence percentage that integrates directly into the Phase 44 feedback loop.

The critical integration challenge is that smolagents is **synchronous only** — `agent.run(stream=True)` yields a synchronous Python generator and the tools are synchronous `forward()` methods. The project already uses `asyncio.to_thread()` for all blocking I/O, and the official smolagents async guide recommends `anyio.to_thread.run_sync`. The streaming bridge pattern is: run the agent in a thread, use a `queue.Queue` (thread-safe, not asyncio) to pass step events into an async SSE generator that reads from the queue.

qwen3:14b in Ollama natively supports tool calling via the `/api/chat` endpoint. The LiteLLM `ollama_chat/` prefix correctly routes to this endpoint. The model's thinking mode should be disabled via a `/no_think` instruction in the system prompt for agentic tasks to avoid stopwords being emitted mid-tool-call.

**Primary recommendation:** Use `ToolCallingAgent` with `LiteLLMModel(model_id="ollama_chat/qwen3:14b", api_base="http://127.0.0.1:11434", num_ctx=8192)`. Run via `anyio.to_thread.run_sync` with a `queue.Queue` bridge for SSE streaming. Set `max_steps=10` at call time. Wrap with `asyncio.wait_for` for the 90s timeout.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| smolagents | 1.24.0 | ToolCallingAgent framework | Official HuggingFace agentic loop; ToolCallingAgent outputs JSON tool calls (safe, no code exec) |
| smolagents[litellm] | 1.24.0 | LiteLLM model adapter | Extra that enables `LiteLLMModel`; required for Ollama routing |
| litellm | (via smolagents) | Model routing layer | `ollama_chat/` prefix routes to `/api/chat` with native tool-call support |
| sse-starlette | 3.0.3 | SSE responses | Already installed; `EventSourceResponse` is the project's established SSE pattern |
| anyio | (via fastapi) | Thread-to-async bridge | `anyio.to_thread.run_sync` is the official smolagents-recommended async integration |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| queue (stdlib) | — | Thread-safe event queue | Bridge between synchronous agent thread and async SSE generator |
| asyncio (stdlib) | — | Timeout enforcement | `asyncio.wait_for` wraps the `to_thread` call for 90s limit |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ToolCallingAgent` (JSON) | `CodeAgent` (Python code) | CodeAgent is more expressive but executes arbitrary code — unsafe in a server context; ToolCallingAgent is safe and sufficient for the 6 predefined tools |
| `LiteLLMModel` via Ollama | `OllamaModel` (if it existed) | smolagents has no native Ollama class; LiteLLM with `ollama_chat/` prefix is the documented approach |
| `anyio.to_thread.run_sync` | `asyncio.to_thread` | Both work; `anyio.to_thread.run_sync` is official smolagents recommendation; `asyncio.to_thread` is the project convention — either works, prefer `asyncio.to_thread` for consistency |

**Installation:**
```bash
uv add "smolagents[litellm]"
```
This adds `smolagents` and `litellm` (the routing layer). No other new dependencies needed — `sse-starlette`, `anyio`, and `asyncio` are already present.

---

## Architecture Patterns

### Recommended Project Structure
```
backend/services/agent/
├── tools.py         # 6 Tool subclasses wrapping DuckDB/Chroma/SQLite
├── runner.py        # ToolCallingAgent setup + run_investigation() + SSE bridge
backend/api/
├── investigate.py   # Add POST /api/investigate/agentic route (existing router)
dashboard/src/views/
├── InvestigationView.svelte  # Add [Summary][Agent] tabs + Agent panel
dashboard/src/lib/
├── api.ts           # Add AgentStep/AgentReasoning/AgentVerdict interfaces + runAgentic()
```

### Pattern 1: smolagents Tool Definition (Class-Based)
**What:** Define each of the 6 tools as a `Tool` subclass with `name`, `description`, `inputs`, `output_type`, and `forward()`. The `forward()` method must be **synchronous** — use `asyncio.new_event_loop().run_until_complete()` or spawn via `asyncio.run()` if you need to call async store methods from inside the tool (since smolagents tools run in a thread, you can create a fresh event loop).

**When to use:** All 6 investigation tools.

```python
# Source: https://huggingface.co/docs/smolagents/main/en/guided_tour
from smolagents import Tool
import asyncio

class QueryEventsTool(Tool):
    name = "query_events"
    description = (
        "Query normalized events from DuckDB by hostname, process name, or time range. "
        "Returns a summary of matching events with counts by event_type."
    )
    inputs = {
        "hostname": {"type": "string", "description": "Host to filter by (optional)", "nullable": True},
        "process_name": {"type": "string", "description": "Process name to filter (optional)", "nullable": True},
        "limit": {"type": "integer", "description": "Max events to return (default 20)"},
    }
    output_type = "string"

    def __init__(self, duckdb_store):
        super().__init__()
        self._store = duckdb_store

    def forward(self, hostname=None, process_name=None, limit=20):
        # Tool runs in a thread — create a fresh event loop for async store calls
        loop = asyncio.new_event_loop()
        try:
            rows = loop.run_until_complete(
                self._store.fetch_df(
                    "SELECT event_type, COUNT(*) as cnt FROM normalized_events WHERE ... LIMIT ?",
                    [limit]
                )
            )
        finally:
            loop.close()
        # Return formatted summary string, not raw JSON
        counts = {r["event_type"]: r["cnt"] for r in rows}
        return f"{sum(counts.values())} events found — " + ", ".join(f"{k}: {v}" for k, v in counts.items())
```

**CRITICAL PITFALL:** smolagents tools execute synchronously. The `forward()` method cannot be `async def`. However, since the entire agent runs in a background thread (via `asyncio.to_thread`), the tool's thread is NOT the event loop thread — you can safely call `asyncio.run()` or `loop.run_until_complete()` for store queries inside `forward()`.

### Pattern 2: LiteLLMModel with Ollama
**What:** Connect smolagents to qwen3:14b via LiteLLM's Ollama adapter.

```python
# Source: https://huggingface.co/docs/smolagents/main/en/guided_tour
from smolagents import LiteLLMModel, ToolCallingAgent

model = LiteLLMModel(
    model_id="ollama_chat/qwen3:14b",
    api_base="http://127.0.0.1:11434",
    api_key="ollama",        # required field even for local; any string works
    num_ctx=8192,            # CRITICAL: Ollama default 2048 is too small for tool calling
)
agent = ToolCallingAgent(
    tools=[...],
    model=model,
    max_steps=10,
)
```

### Pattern 3: SSE Bridge — Synchronous Generator to Async SSE
**What:** Bridge the synchronous `agent.run(stream=True)` generator to an async FastAPI SSE endpoint via a thread-safe `queue.Queue`.

**The challenge:** `agent.run(stream=True)` returns a **synchronous generator** — it yields `ActionStep`, `PlanningStep`, etc. objects as the agent executes. These steps cannot be directly `await`-ed. The solution is to run the generator in a thread and communicate via a queue.

```python
# Source: official smolagents async guide + sse-starlette pattern
import asyncio
import json
import queue
import threading
from typing import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from smolagents import ToolCallingAgent, LiteLLMModel
from smolagents.memory import ActionStep

async def agent_sse_stream(
    agent: ToolCallingAgent,
    task: str,
    timeout: float = 90.0,
) -> AsyncIterator[dict]:
    """Yield SSE-compatible dicts from a synchronous smolagents run."""
    event_queue: queue.Queue = queue.Queue()

    def _run_sync():
        try:
            for step in agent.run(task, stream=True, max_steps=10):
                event_queue.put(("step", step))
            event_queue.put(("done", None))
        except Exception as exc:
            event_queue.put(("error", str(exc)))

    thread = threading.Thread(target=_run_sync, daemon=True)
    thread.start()

    deadline = asyncio.get_event_loop().time() + timeout
    call_count = 0

    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            yield {"event": "limit", "data": json.dumps({"reason": "timeout"})}
            break
        try:
            # Poll queue without blocking the event loop
            kind, payload = await asyncio.get_event_loop().run_in_executor(
                None, lambda: event_queue.get(timeout=0.1)
            )
        except queue.Empty:
            await asyncio.sleep(0)
            continue

        if kind == "done":
            yield {"event": "done", "data": "{}"}
            break
        elif kind == "error":
            yield {"event": "error", "data": json.dumps({"message": payload})}
            break
        elif kind == "step":
            step = payload
            if isinstance(step, ActionStep):
                call_count += 1
                # Emit tool_call event
                tool_calls = getattr(step, "tool_calls", None) or []
                observations = getattr(step, "observations", "")
                for tc in tool_calls:
                    yield {
                        "event": "tool_call",
                        "data": json.dumps({
                            "call_number": call_count,
                            "tool_name": tc.name,
                            "arguments": tc.arguments,
                            "result": str(observations)[:500],  # truncate
                        })
                    }
                # Emit reasoning text (model_output before the tool call)
                model_output = getattr(step, "model_output", "") or ""
                if model_output:
                    yield {
                        "event": "reasoning",
                        "data": json.dumps({"text": model_output})
                    }
                if call_count >= 10:
                    yield {"event": "limit", "data": json.dumps({"reason": "max_calls"})}
                    break
```

**Note on step_callbacks vs stream=True:** Both approaches work for intercepting steps. `stream=True` is simpler for SSE because the generator yields naturally. `step_callbacks` are better when you need side effects (logging, DB writes). For this phase, `stream=True` is the right choice.

### Pattern 4: Svelte 5 Tabs (No Stores)
**What:** Add [Summary][Agent] tabs to `InvestigationView.svelte` using `$state` runes only.

```typescript
// Pattern used across DetectionsView (Phase 43-04 verdict filter pattern)
let activeTab = $state<'summary' | 'agent'>('summary')

// Template
{#if activeTab === 'summary'}
  <!-- existing summary content — zero changes -->
{:else}
  <!-- Agent panel -->
{/if}
```

**The existing layout** is a two-column grid (`55% 45%`). The [Summary]/[Agent] tabs replace the panel header of the LEFT panel (timeline/evidence). The RIGHT panel (AI Copilot) is unaffected.

### Pattern 5: SSE Client in TypeScript (Matching Existing chatStream Pattern)
**What:** The `runAgentic()` function in `api.ts` follows the same fetch+ReadableStream pattern as `chatStream()`.

```typescript
// Mirrors the existing chatStream pattern in api.ts (line 886)
runAgentic: async (
  detectionId: string,
  onStep: (step: AgentStep) => void,
  onReasoning: (text: string) => void,
  onVerdict: (verdict: AgentVerdict) => void,
  onLimit: (reason: string) => void,
  onDone: () => void,
  signal?: AbortSignal,
): Promise<void> => {
  const res = await fetch('/api/investigate/agentic', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ detection_id: detectionId }),
    signal,
  })
  if (!res.ok) throw new Error(`Agent failed: ${res.status}`)
  const reader = res.body?.getReader()
  if (!reader) throw new Error('No response body')
  const decoder = new TextDecoder()
  // ... same line-by-line SSE parsing as chatStream
}
```

### Anti-Patterns to Avoid
- **Async tool forward():** Never define `forward()` as `async def` — smolagents cannot await it. Wrap with `asyncio.run()` or `loop.run_until_complete()` inside the synchronous method.
- **Calling `agent.run()` directly in async endpoint:** Blocks the event loop. Always use `asyncio.to_thread` or `anyio.to_thread.run_sync`.
- **Using `stream=True` without consuming the generator:** The generator is lazy — if you don't iterate it, nothing executes.
- **Omitting `num_ctx=8192`:** Ollama defaults to 2048 context tokens. Tool-calling conversations with 10 steps easily exceed this, causing truncation and malformed JSON responses.
- **Using qwen3 thinking mode for tool calls:** Qwen3's thinking mode emits `<think>...</think>` tokens mid-response. These can interfere with tool-call JSON parsing. Add `/no_think` to the system prompt.
- **Raw JSON in tool results:** Tool `forward()` must return a descriptive string, not a dict/JSON blob. Dicts are serialized unpredictably; strings are unambiguous to the LLM.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tool dispatch loop | Custom ReAct loop parsing LLM output | `smolagents.ToolCallingAgent` | Tool-call JSON parsing, retry on malformed output, max_steps enforcement — all handled |
| Model routing to Ollama | Custom httpx calls for chat completions | `LiteLLMModel(model_id="ollama_chat/...")` | Handles tool-call schema translation, JSON mode fallback for non-native models |
| SSE event formatting | Manual `data: ...\n\n` construction | `sse-starlette EventSourceResponse` | Already installed; handles keep-alive, encoding, disconnects |
| Tool schema generation | Manually write JSON schemas for tools | `Tool` subclass with `inputs` dict | smolagents auto-generates the JSON schema from the `inputs` dict for the LLM system prompt |

**Key insight:** smolagents handles the entire ReAct loop (LLM call → parse tool call JSON → dispatch → observe → repeat). The only custom code needed is the 6 tool `forward()` implementations and the SSE bridge.

---

## Common Pitfalls

### Pitfall 1: qwen3 Thinking Mode Breaks Tool-Call JSON
**What goes wrong:** qwen3:14b has a "thinking mode" that prefixes responses with `<think>...</think>` tokens. smolagents parses the model output for JSON tool calls. If thinking tokens appear inside the JSON-expected region, parsing fails and the agent errors.
**Why it happens:** qwen3 defaults to thinking mode (`/think` behaviour). LiteLLM passes the raw model output to smolagents without stripping think tags.
**How to avoid:** Add `/no_think` as the first line of the system prompt. Alternatively, pass `think=False` in the LiteLLM model kwargs if your litellm version supports it.
**Warning signs:** `AttributeError` or JSON parse errors in agent logs after the first LLM call.

### Pitfall 2: Event Loop Already Running (Nested asyncio.run)
**What goes wrong:** Calling `asyncio.run()` inside a tool `forward()` that is already executing inside an `asyncio.to_thread()` call raises `RuntimeError: This event loop is already running`.
**Why it happens:** `asyncio.to_thread()` runs in the same process; the main event loop is running on the main thread. The thread has NO running event loop, so `asyncio.run()` should work. BUT if you accidentally call it from the main thread context, it will fail.
**How to avoid:** In each tool `forward()`, always create a fresh loop: `loop = asyncio.new_event_loop(); try: result = loop.run_until_complete(...); finally: loop.close()`.
**Warning signs:** `RuntimeError: This event loop is already running` during a tool call.

### Pitfall 3: smolagents Tools Are Not Async — Store Access Pattern
**What goes wrong:** The project's DuckDB store uses `await store.fetch_df(...)`. Inside a synchronous `forward()` you cannot `await`.
**Why it happens:** The `asyncio.to_thread()` that runs the agent creates a new thread without an event loop, but the store's async methods require one.
**How to avoid:** Use `asyncio.new_event_loop().run_until_complete(store.fetch_df(...))` inside each tool. Alternatively, the tools can use the DuckDB connection directly via synchronous DuckDB calls (bypassing the async wrapper) — the DuckDB read connections are thread-safe.

**Preferred pattern — direct sync DuckDB reads from tools:**
```python
# Tools receive stores as constructor arguments
# Use synchronous DuckDB reads directly (bypasses async queue):
import duckdb

def forward(self, ...):
    with duckdb.connect(self._db_path, read_only=True) as conn:
        rows = conn.execute("SELECT ...").fetchall()
    return _format_results(rows)
```
This avoids the nested event loop problem entirely and is safe because DuckDB supports multiple concurrent read-only connections.

### Pitfall 4: smolagents stream=True Generator Must Be Fully Consumed
**What goes wrong:** The generator from `agent.run(stream=True)` is lazy — it only executes when iterated. If you start a thread that creates the generator but doesn't iterate it, the agent never runs.
**Why it happens:** Python generators are lazy by design.
**How to avoid:** The `_run_sync()` thread function must use a `for` loop (not store the generator): `for step in agent.run(task, stream=True): queue.put(step)`.

### Pitfall 5: LiteLLM/Ollama Tool Calling Fallback Behavior
**What goes wrong:** Not all Ollama models support native function calling. LiteLLM silently falls back to JSON mode when native tool calling is unsupported, which changes the response format.
**Why it happens:** LiteLLM auto-detects capability and switches modes. qwen3:14b DOES support native tool calling in Ollama, but if the model is unavailable and falls back to a different model, JSON mode kicks in.
**How to avoid:** Verify Ollama has `qwen3:14b` pulled before starting the agent. The health check already in place (`ollama_client.health_check()`) can be reused.
**Warning signs:** Tool calls come back as plain text JSON strings rather than structured `tool_calls` objects.

### Pitfall 6: FinalAnswerStep Callbacks Not Fired (Known Bug)
**What goes wrong:** `step_callbacks` registered for `FinalAnswerStep` are never called in the current smolagents 1.24.0 (GitHub issue #1879).
**Why it happens:** Known bug — `FinalAnswerStep` is never passed to `_finalize_step()`.
**How to avoid:** Don't rely on step callbacks for the final answer. With `stream=True`, the generator return value IS the final answer. Capture it with: `result = None; for step in gen: ...; result = agent.memory.steps[-1]` — or better, the generator's final value from `StopIteration.value`.

---

## Code Examples

### Complete Agent Runner Setup
```python
# Source: https://huggingface.co/docs/smolagents/main/en/guided_tour
# backend/services/agent/runner.py
from smolagents import LiteLLMModel, ToolCallingAgent
from backend.core.config import settings

SYSTEM_PROMPT = """/no_think
You are a cybersecurity investigation agent for a SOC analyst.
Your job: analyze a security detection by querying events, enriching IPs,
checking graph relationships, and searching for similar incidents.
After gathering evidence, produce a final verdict: TP (True Positive) or FP (False Positive).
Format your final answer as JSON: {"verdict": "TP"|"FP", "confidence": 0-100, "narrative": "2-3 sentences"}
"""

def build_agent(stores) -> ToolCallingAgent:
    model = LiteLLMModel(
        model_id="ollama_chat/qwen3:14b",
        api_base=str(settings.OLLAMA_BASE_URL),
        api_key="ollama",
        num_ctx=8192,
    )
    tools = [
        QueryEventsTool(stores.duckdb),
        GetEntityProfileTool(stores.duckdb),
        EnrichIpTool(stores.sqlite),
        SearchSigmaMatchesTool(stores.sqlite),
        GetGraphNeighborsTool(stores.sqlite),
        SearchSimilarIncidentsTool(stores.chroma),
    ]
    return ToolCallingAgent(
        tools=tools,
        model=model,
        instructions=SYSTEM_PROMPT,
        verbosity_level=0,   # suppress stdout logs in production
    )
```

### SSE Endpoint Pattern
```python
# backend/api/investigate.py — add to existing router
@router.post("/agentic")
async def run_agentic_investigation(request: Request):
    body = await request.json()
    detection_id = body.get("detection_id", "")
    stores = request.app.state.stores

    agent = build_agent(stores)
    task = f"Investigate detection {detection_id}. Query events, enrich IPs, check graph, find similar cases, then give a TP/FP verdict."

    async def event_generator():
        import queue as _queue
        import threading

        q: _queue.Queue = _queue.Queue()

        def _run():
            try:
                for step in agent.run(task, stream=True, max_steps=10):
                    q.put(("step", step))
                q.put(("done", agent.memory.steps[-1] if agent.memory.steps else None))
            except Exception as exc:
                q.put(("error", str(exc)))

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        import asyncio, json
        from smolagents.memory import ActionStep

        deadline = asyncio.get_event_loop().time() + 90.0
        call_count = 0

        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                yield {"event": "limit", "data": json.dumps({"reason": "timeout", "calls_used": call_count})}
                return

            try:
                kind, payload = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: q.get(timeout=0.2)
                )
            except _queue.Empty:
                await asyncio.sleep(0)
                continue

            if kind == "error":
                yield {"event": "error", "data": json.dumps({"message": payload})}
                return
            elif kind == "done":
                yield {"event": "done", "data": json.dumps({"final_step": str(payload)})}
                return
            elif kind == "step" and isinstance(payload, ActionStep):
                call_count += 1
                # ... serialize and yield step
                yield {"event": "tool_call", "data": json.dumps({...})}

    from sse_starlette.sse import EventSourceResponse
    return EventSourceResponse(event_generator())
```

### Svelte 5 Tab Pattern
```svelte
<!-- InvestigationView.svelte — minimal tab addition -->
<script lang="ts">
  // Add to existing script block:
  let activeTab = $state<'summary' | 'agent'>('summary')
  let agentSteps = $state<AgentStep[]>([])
  let agentReasoning = $state<string>('')
  let agentVerdict = $state<AgentVerdict | null>(null)
  let agentRunning = $state(false)
  let callsUsed = $state(0)
  // Cache keyed by detection_id:
  const agentCache = new Map<string, { steps: AgentStep[]; verdict: AgentVerdict | null }>()
</script>

<!-- Tab header replaces the existing panel-header h2: -->
<div class="tab-bar">
  <button class:active={activeTab === 'summary'} onclick={() => activeTab = 'summary'}>Summary</button>
  <button class:active={activeTab === 'agent'} onclick={() => activeTab = 'agent'}>
    Agent
    {#if agentRunning}
      <span class="call-counter">{callsUsed}/10 calls used</span>
    {/if}
  </button>
</div>

{#if activeTab === 'summary'}
  <!-- ZERO changes — existing timeline + CAR + similar cases here -->
{:else}
  <!-- Agent panel content here -->
{/if}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled ReAct loops with raw LLM calls | smolagents ToolCallingAgent (1.24.0) | Released Jan 2026 | Full tool dispatch, step memory, max_steps enforcement built in |
| Ollama with custom HTTP client only | LiteLLM `ollama_chat/` prefix (native tool calls) | Ollama added native tool calling support ~2024 | JSON function calling without JSON mode workarounds |
| qwen2.5 for tool calling | qwen3:14b (hybrid thinking/no-thinking) | Released April 2025 | Better tool-call JSON accuracy; `/no_think` disables thinking overhead |

**Deprecated/outdated:**
- `ollama/` LiteLLM prefix: Use `ollama_chat/` instead — routes to `/api/chat` with proper tool-call support. `ollama/` routes to `/api/generate` which does not support native tool calling.
- `step_callbacks` for final answer capture: Broken in smolagents 1.24.0 (issue #1879). Use generator return value or `agent.memory.steps` instead.

---

## Open Questions

1. **qwen3:14b tool-call reliability at 10-step depth**
   - What we know: qwen3 ranks highly on BFCL (function calling benchmark). Ollama confirms qwen3 supports native tool calling. With `/no_think` the model should not emit thinking tokens.
   - What's unclear: Actual pass rate for multi-turn SOC investigation tasks with 6 domain-specific tools has not been benchmarked for this project.
   - Recommendation: Include a simple integration smoke test (`POST /api/investigate/agentic` with a known detection_id) in Wave 0. If qwen3:14b underperforms, the LiteLLM model_id is a one-line change to any other model.

2. **smolagents ActionStep structure in v1.24.0**
   - What we know: `ActionStep` has `tool_calls`, `observations`, `model_output` attributes based on source code references and documentation.
   - What's unclear: Exact attribute names and types have not been verified against the v1.24.0 source directly (Context7 does not index smolagents).
   - Recommendation: Wave 0 stub test should import `ActionStep` and assert attribute presence rather than hardcoding field names. Runner code should use `getattr(step, "tool_calls", [])` defensively.

3. **LiteLLM version pinning**
   - What we know: `smolagents[litellm]` installs litellm as a transitive dependency. The exact version is not pinned.
   - What's unclear: Whether the installed litellm version has the known Ollama tool-calling bug (issue #11104 in litellm) fixed.
   - Recommendation: After `uv add "smolagents[litellm]"`, run `uv run python -c "import litellm; print(litellm.__version__)"` and verify it is >= 1.52.0 where the Ollama chat fix landed.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (uv run pytest) |
| Config file | pyproject.toml — `pytest-asyncio` mode: auto |
| Quick run command | `uv run pytest tests/unit/test_agent_tools.py tests/unit/test_agent_runner.py -x` |
| Full suite command | `uv run pytest tests/unit/ -x --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P45-T01 | `QueryEventsTool.forward()` returns formatted string with event counts | unit | `uv run pytest tests/unit/test_agent_tools.py::TestQueryEventsTool -x` | ❌ Wave 0 |
| P45-T01 | `GetEntityProfileTool.forward()` returns entity summary string | unit | `uv run pytest tests/unit/test_agent_tools.py::TestGetEntityProfileTool -x` | ❌ Wave 0 |
| P45-T01 | `EnrichIpTool.forward()` returns OSINT enrichment string | unit | `uv run pytest tests/unit/test_agent_tools.py::TestEnrichIpTool -x` | ❌ Wave 0 |
| P45-T01 | `SearchSigmaMatchesTool.forward()` returns matching rules string | unit | `uv run pytest tests/unit/test_agent_tools.py::TestSearchSigmaMatchesTool -x` | ❌ Wave 0 |
| P45-T01 | `GetGraphNeighborsTool.forward()` returns neighbor entities string | unit | `uv run pytest tests/unit/test_agent_tools.py::TestGetGraphNeighborsTool -x` | ❌ Wave 0 |
| P45-T01 | `SearchSimilarIncidentsTool.forward()` returns similar cases string | unit | `uv run pytest tests/unit/test_agent_tools.py::TestSearchSimilarIncidentsTool -x` | ❌ Wave 0 |
| P45-T02 | `build_agent()` creates ToolCallingAgent with 6 tools | unit | `uv run pytest tests/unit/test_agent_runner.py::test_build_agent -x` | ❌ Wave 0 |
| P45-T03 | `POST /api/investigate/agentic` returns 200 with SSE content-type | unit (mocked) | `uv run pytest tests/unit/test_agentic_api.py::test_agentic_endpoint_exists -x` | ❌ Wave 0 |
| P45-T05 | Agent stops at max_steps=10 (tool count enforcement) | unit | `uv run pytest tests/unit/test_agent_runner.py::test_max_steps_limit -x` | ❌ Wave 0 |
| P45-T05 | 90s timeout fires limit event | unit (mocked clock) | `uv run pytest tests/unit/test_agent_runner.py::test_timeout_fires -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_agent_tools.py tests/unit/test_agent_runner.py tests/unit/test_agentic_api.py -x`
- **Per wave merge:** `uv run pytest tests/unit/ -x --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_agent_tools.py` — 6 tool stubs + mock store fixtures (REQ P45-T01)
- [ ] `tests/unit/test_agent_runner.py` — build_agent, max_steps, timeout stubs (REQ P45-T02, P45-T05)
- [ ] `tests/unit/test_agentic_api.py` — endpoint exists, SSE content-type, 90s timeout stub (REQ P45-T03)
- [ ] Framework install: `uv add "smolagents[litellm]"` — smolagents not yet installed

---

## Sources

### Primary (HIGH confidence)
- https://huggingface.co/docs/smolagents/main/en/guided_tour — ToolCallingAgent, Tool class, LiteLLMModel with Ollama, `max_steps`, `stream=True`
- https://huggingface.co/docs/smolagents/en/reference/agents — MultiStepAgent/ToolCallingAgent API reference, `step_callbacks` parameter, `stream` parameter on `run()`
- https://huggingface.co/docs/smolagents/main/examples/async_agent — Official async integration pattern (`anyio.to_thread.run_sync`)
- https://pypi.org/project/smolagents/ — Version 1.24.0 confirmed, Python >=3.10 requirement
- https://docs.ollama.com/capabilities/tool-calling — qwen3 used in all tool-calling examples; confirms native tool call support
- `backend/api/investigations.py` (project codebase) — SSE `EventSourceResponse` pattern is established
- `dashboard/src/lib/api.ts` lines 886-918 (project codebase) — `chatStream()` SSE client pattern to replicate

### Secondary (MEDIUM confidence)
- https://docs.litellm.ai/docs/providers/ollama — `ollama_chat/` prefix routes to `/api/chat` with tool calling; JSON mode fallback documented
- https://github.com/huggingface/smolagents/issues/334 — Async tool support NOT available; workaround: run sync in thread
- https://github.com/huggingface/smolagents/issues/1879 — FinalAnswerStep callbacks broken in current version
- https://qwenlm.github.io/blog/qwen3/ — qwen3 thinking/no-thinking mode; `/no_think` instruction confirmed

### Tertiary (LOW confidence — needs validation)
- https://github.com/BerriAI/litellm/issues/11104 — Ollama tool calling bug in older litellm versions; verify litellm >= 1.52.0 after install
- smolagents `ActionStep` attribute names (`tool_calls`, `observations`, `model_output`) — referenced in docs but exact API not verified against v1.24.0 source

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — smolagents 1.24.0, LiteLLMModel, Ollama `ollama_chat/` prefix all verified via official docs
- Architecture: HIGH — SSE bridge pattern, tool class syntax, Svelte 5 tab pattern all verified against existing project code and official sources
- Pitfalls: HIGH — Async limitation (GitHub issue #334), thinking mode issue (official Qwen docs), num_ctx requirement (official guide) all officially documented

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (smolagents releases frequently; re-verify ActionStep attributes if version changes)
