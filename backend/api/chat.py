"""
AI Copilot Chat API.

Endpoints:
  POST /api/investigations/{investigation_id}/chat
      — Streams foundation-sec:8b response via SSE.
        Persists user question and assistant response to SQLite chat_messages.

  GET  /api/investigations/{investigation_id}/chat/history
      — Returns previous chat messages for the investigation.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Literal, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.api.query import verify_citations
from backend.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/api/investigations", tags=["investigations"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHAT_MESSAGES_DDL = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id               TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    role             TEXT NOT NULL,
    content          TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_inv ON chat_messages (investigation_id);
"""

_COPILOT_SYSTEM = """You are an expert cybersecurity analyst AI Copilot embedded in a SOC investigation platform.
You are given context about an ongoing security investigation.
Answer the analyst's question concisely. Identify relevant MITRE ATT&CK techniques when applicable.
If you are uncertain, say so. Do not fabricate event IDs or hostnames."""

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    investigation_id: str
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str
    context_limit: int = 10  # max timeline items to include as context


# ---------------------------------------------------------------------------
# Helper: build investigation context from timeline
# ---------------------------------------------------------------------------


async def _build_investigation_context(
    investigation_id: str,
    stores: object,
    context_limit: int,
) -> str:
    """
    Build a short text block of the most recent timeline items for the
    investigation. Calls the merge_and_sort_timeline function directly
    (avoids HTTP round-trip).
    """
    try:
        from backend.api.timeline import merge_and_sort_timeline

        # Fetch detections from SQLite
        detection_rows = await asyncio.to_thread(
            stores.sqlite.get_detections_by_case, investigation_id
        )

        # Fetch events from DuckDB (up to context_limit)
        event_rows = await stores.duckdb.fetch_all(
            """SELECT event_id, timestamp, event_type, severity, hostname, process_name,
                      attack_technique, attack_tactic, command_line
               FROM normalized_events
               WHERE case_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            [investigation_id, context_limit],
        )

        items = merge_and_sort_timeline(event_rows, detection_rows)
        recent = items[-context_limit:]

        if not recent:
            return f"No timeline events found for investigation {investigation_id}."

        lines = [f"Investigation ID: {investigation_id}", f"Timeline ({len(recent)} items):"]
        for item in recent:
            line = f"  [{item.timestamp[:19]}] [{item.item_type.upper()}] {item.title}"
            if item.severity:
                line += f" (severity: {item.severity})"
            if item.attack_technique:
                line += f" [MITRE: {item.attack_technique}]"
            if item.attack_tactic:
                line += f" [Tactic: {item.attack_tactic}]"
            lines.append(line)

        return "\n".join(lines)

    except Exception as exc:
        log.warning(
            "Failed to build investigation context",
            investigation_id=investigation_id,
            error=str(exc),
        )
        return f"Investigation ID: {investigation_id} (context unavailable: {exc})"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/{investigation_id}/chat")
async def chat_stream(
    investigation_id: str,
    body: ChatRequest,
    request: Request,
) -> StreamingResponse:
    """Stream a foundation-sec:8b response for an analyst question via SSE."""
    ollama = request.app.state.ollama
    stores = request.app.state.stores

    context = await _build_investigation_context(
        investigation_id, stores, body.context_limit
    )
    prompt = f"Investigation context:\n{context}\n\nAnalyst question: {body.question}"

    full_tokens: list[str] = []

    async def event_stream():
        # Persist user message before streaming
        await asyncio.to_thread(
            stores.sqlite.insert_chat_message,
            investigation_id,
            "user",
            body.question,
        )
        async for token in ollama.stream_generate_iter(
            prompt,
            system=_COPILOT_SYSTEM,
            use_cybersec_model=True,  # routes to foundation-sec:8b
        ):
            full_tokens.append(token)
            yield f"data: {json.dumps({'token': token})}\n\n"
        # Persist assistant response after stream completes
        asyncio.create_task(
            asyncio.to_thread(
                stores.sqlite.insert_chat_message,
                investigation_id,
                "assistant",
                "".join(full_tokens),
            )
        )
        # Extract event IDs from context for citation verification
        # Context lines contain investigation_id and timeline entries
        _id_pattern = re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            re.IGNORECASE,
        )
        context_ids_found = _id_pattern.findall(context)
        full_response = "".join(full_tokens)
        citation_ok = verify_citations(full_response, context_ids_found)
        yield f"data: {json.dumps({'done': True, 'citation_verified': citation_ok})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{investigation_id}/chat/history")
async def get_chat_history(
    investigation_id: str,
    request: Request,
) -> JSONResponse:
    """Return stored chat messages for an investigation, oldest first."""
    stores = request.app.state.stores
    messages = await asyncio.to_thread(
        stores.sqlite.get_chat_history, investigation_id
    )
    return JSONResponse({"messages": messages})
