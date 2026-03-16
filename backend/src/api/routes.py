"""Route handlers for AI SOC Brain API.

Phase 2 additions:
  POST /ingest          — batch ingest (Vector, syslog relay, script-driven)
  POST /ingest/syslog   — single syslog line (any RFC3164/5424/CEF format)
  GET  /events/stream   — SSE stream of new events (live browser push)
  GET  /health          — now reports active ingestion sources
"""
import asyncio
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from backend.src.api.models import (
    HealthResponse, GraphResponse, NormalizedEvent, Alert, IngestSource
)
from backend.src.parsers.normalizer import normalize
from backend.src.graph.builder import build_graph
from backend.src.detection.rules import evaluate
from backend.src.fixtures.loader import load_ndjson
from backend.src.ingestion.syslog_parser import parse_syslog_line
from backend.src.ingestion.opensearch_sink import try_index

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory store (Phase 2 — not production).
# Replace with DuckDB store in Phase 3.
# ---------------------------------------------------------------------------
_events: list[dict] = []
_alerts: list[dict] = []

# SSE: clients subscribe to this queue for live event push
_sse_queues: list[asyncio.Queue] = []

FIXTURE_PATH = Path(__file__).parents[3] / "fixtures" / "ndjson" / "sample_events.ndjson"

# Active ingestion sources observed this session (for /health reporting)
_active_sources: set[str] = set()


def _store_event(event: NormalizedEvent) -> list[Alert]:
    """Persist event + run detection. Returns triggered alerts."""
    _events.append(event.model_dump())
    _active_sources.add(event.source.value)
    new_alerts = evaluate(event)
    _alerts.extend(a.model_dump() for a in new_alerts)
    # Push to SSE subscribers (non-blocking)
    payload = json.dumps(event.model_dump(mode="json"))
    for q in list(_sse_queues):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass
    # Index to OpenSearch if configured (SCAFFOLD — no-op if OPENSEARCH_URL unset)
    try_index(event)
    return new_alerts


# ---------------------------------------------------------------------------
# Wave 1 endpoints — preserved
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        ingestion_sources=sorted(_active_sources),
    )


@router.get("/events")
def get_events():
    return _events


@router.post("/events", status_code=201)
def post_event(raw: dict):
    event = normalize(raw, source=IngestSource.api)
    _store_event(event)
    return event.model_dump(mode="json")


@router.get("/timeline")
def get_timeline():
    return sorted(_events, key=lambda e: e.get("timestamp", ""))


@router.get("/graph", response_model=GraphResponse)
def get_graph():
    return build_graph(_events)


@router.get("/alerts")
def get_alerts():
    return _alerts


@router.post("/fixtures/load")
def load_fixtures():
    result = load_ndjson(FIXTURE_PATH, _events, normalize, evaluate)
    _alerts.extend(result.get("alert_list", []))
    _active_sources.add(IngestSource.fixture.value)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {"loaded": result["loaded"], "alerts": result["alerts"]}


# ---------------------------------------------------------------------------
# Phase 2 — Batch ingest
# ---------------------------------------------------------------------------

@router.post("/ingest", status_code=202)
def ingest_batch(request_body: dict):
    """Accept a batch of events from Vector, a syslog relay, or scripts.

    Body: { "events": [ {...}, ... ], "source": "vector" }
    Returns: { "accepted": N, "alerts": M }
    """
    events_raw: list[dict] = request_body.get("events", [])
    source_str: str = request_body.get("source", "api")

    try:
        source = IngestSource(source_str)
    except ValueError:
        source = IngestSource.api

    accepted = 0
    total_alerts = 0
    for raw in events_raw:
        if not isinstance(raw, dict):
            continue
        event = normalize(raw, source=source)
        new_alerts = _store_event(event)
        total_alerts += len(new_alerts)
        accepted += 1

    return {"accepted": accepted, "alerts": total_alerts, "source": source.value}


@router.post("/ingest/syslog", status_code=202)
async def ingest_syslog(request: Request):
    """Accept a raw syslog line (RFC3164, RFC5424, or CEF) as plain text body.

    Intended for forwarding from syslog-ng, rsyslog, or Vector syslog source.
    Content-Type: text/plain
    Body: single syslog line
    """
    body = await request.body()
    line = body.decode("utf-8", errors="replace").strip()
    if not line:
        return {"accepted": 0}

    raw = parse_syslog_line(line)
    event = normalize(raw, source=IngestSource.syslog)
    new_alerts = _store_event(event)
    return {"accepted": 1, "alerts": len(new_alerts), "event_id": event.id}


# ---------------------------------------------------------------------------
# Phase 2 — SSE live stream
# ---------------------------------------------------------------------------

@router.get("/events/stream")
async def stream_events(request: Request):
    """Server-Sent Events stream — pushes new events to browser in real time.

    Browsers connect once; events appear as 'data: {...}\\n\\n' SSE frames.
    Use as fallback if polling every 10s is too coarse for a live attack.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_queues.append(queue)

    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {"data": payload}
                except asyncio.TimeoutError:
                    # Heartbeat keeps connection alive through proxies
                    yield {"data": ":heartbeat"}
        finally:
            _sse_queues.remove(queue)

    return EventSourceResponse(generator())
