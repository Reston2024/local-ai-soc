"""Causality engine API endpoints — Phase 8 rewrite.

Mounted at /api prefix via app.include_router(causality_router, prefix="/api").
Routes use the /causality sub-prefix to avoid conflicts with backend/api/graph.py.

All routes read from DuckDB/SQLite instead of the legacy in-memory lists.
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request

# --- Deferred imports (graceful degradation if causality package absent) ---
try:
    from backend.causality.engine import build_causality_sync as _build_causality
except ImportError:
    _build_causality = None  # type: ignore[assignment]

try:
    from prompts.investigation_summary import format_prompt as _format_summary_prompt
except ImportError:
    _format_summary_prompt = None  # type: ignore[assignment]

causality_router = APIRouter(prefix="/causality", tags=["causality"])

# Column order matches normalized_events DDL in duckdb_store.py
_EVENT_COLUMNS = [
    "event_id", "timestamp", "ingested_at", "source_type", "source_file",
    "hostname", "username", "process_name", "process_id",
    "parent_process_name", "parent_process_id",
    "file_path", "file_hash_sha256", "command_line",
    "src_ip", "src_port", "dst_ip", "dst_port", "domain", "url",
    "event_type", "severity", "confidence", "detection_source",
    "attack_technique", "attack_tactic",
    "raw_event", "tags", "case_id",
]


def _row_to_dict(row: tuple) -> dict:
    """Convert a DuckDB tuple row to a field-name-keyed dict."""
    d = {}
    for i, col in enumerate(_EVENT_COLUMNS):
        if i < len(row):
            val = row[i]
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            d[col] = val
    return d


async def _fetch_events_for_detection(stores, detection: dict) -> list[dict]:
    """Fetch NormalizedEvent dicts for matched event IDs in a detection."""
    if not detection:
        return []
    matched_ids = detection.get("matched_event_ids") or []
    if not matched_ids:
        return []
    placeholders = ",".join(["?" for _ in matched_ids])
    rows = await stores.duckdb.fetch_all(
        f"SELECT * FROM normalized_events WHERE event_id IN ({placeholders}) ORDER BY timestamp",
        list(matched_ids),
    )
    return [_row_to_dict(row) for row in rows]


async def _fetch_recent_events(stores, limit: int = 500) -> list[dict]:
    """Fetch the most recent events from DuckDB."""
    rows = await stores.duckdb.fetch_all(
        "SELECT * FROM normalized_events ORDER BY timestamp DESC LIMIT ?",
        [limit],
    )
    return [_row_to_dict(row) for row in rows]


# ---------------------------------------------------------------------------
# GET /api/causality/graph/{alert_id}
# ---------------------------------------------------------------------------

@causality_router.get("/graph/{alert_id}")
async def get_causality_graph(alert_id: str, request: Request):
    """Return causality graph centered on a specific alert.
    Nodes and edges represent the causal chain of events around the alert.
    Returns an empty graph (200) when the alert is not found.
    """
    if _build_causality is None:
        raise HTTPException(status_code=503, detail="Causality engine not available")

    stores = request.app.state.stores

    detection = await asyncio.to_thread(stores.sqlite.get_detection, alert_id)
    events = await _fetch_events_for_detection(stores, detection) if detection else []

    if not events:
        events = await _fetch_recent_events(stores)

    # Engine expects events with "id" key for BFS lookups
    events_for_engine = [{**e, "id": e["event_id"]} for e in events]

    # Build a synthetic alert dict for the engine
    alerts_for_engine = []
    if detection:
        first_event_id = (detection.get("matched_event_ids") or [None])[0]
        alerts_for_engine = [{
            "id": alert_id,
            "event_id": first_event_id,
            "severity": detection.get("severity", "medium"),
            "description": detection.get("explanation", ""),
            "attack_tags": [],
        }]

    result = await asyncio.to_thread(
        lambda: _build_causality(alert_id, events_for_engine, alerts_for_engine)
    )

    if not result:
        return {
            "alert_id": alert_id,
            "nodes": [],
            "edges": [],
            "attack_paths": [],
            "chain": [],
            "techniques": [],
            "score": 0,
            "first_event": "",
            "last_event": "",
        }
    return result


# ---------------------------------------------------------------------------
# GET /api/causality/entity/{entity_id}
# ---------------------------------------------------------------------------

@causality_router.get("/entity/{entity_id:path}")
async def get_entity(entity_id: str, request: Request):
    """Return entity details and related events.
    entity_id is a canonical ID of the form 'type:value' (e.g. 'host:workstation01').
    """
    if _build_causality is None:
        raise HTTPException(status_code=503, detail="Causality engine not available")

    entity_type, _, entity_value = entity_id.partition(":")
    if not entity_type or not entity_value:
        raise HTTPException(status_code=400, detail="entity_id must be 'type:value' format")

    # Map entity type to NormalizedEvent field names
    type_field_map = {
        "host": ["hostname"],
        "ip": ["src_ip", "dst_ip"],
        "domain": ["domain"],
        "user": ["username"],
        "process": ["process_name"],
        "file": ["file_path"],
    }
    fields = type_field_map.get(entity_type)
    if not fields:
        raise HTTPException(status_code=400, detail=f"Unknown entity type: {entity_type!r}")

    stores = request.app.state.stores

    # Build WHERE clause for the entity search
    conditions = " OR ".join(f"LOWER({f}) = LOWER(?)" for f in fields)
    params = [entity_value] * len(fields)
    rows = await stores.duckdb.fetch_all(
        f"SELECT * FROM normalized_events WHERE {conditions} ORDER BY timestamp LIMIT 100",
        params,
    )
    related = [_row_to_dict(row) for row in rows]

    return {
        "entity_id": entity_id,
        "type": entity_type,
        "value": entity_value,
        "attributes": {},
        "first_seen": related[0].get("timestamp", "") if related else "",
        "last_seen": related[-1].get("timestamp", "") if related else "",
        "related_event_count": len(related),
        "related_events": related[:50],
        "related_alert_count": 0,
    }


# ---------------------------------------------------------------------------
# GET /api/causality/attack_chain/{alert_id}
# ---------------------------------------------------------------------------

@causality_router.get("/attack_chain/{alert_id}")
async def get_attack_chain(alert_id: str, request: Request):
    """Return the attack chain for a specific alert.
    Chain edges are ordered by timestamp (earliest first).
    Returns an empty chain (200) when the alert is not found.
    """
    if _build_causality is None:
        raise HTTPException(status_code=503, detail="Causality engine not available")

    stores = request.app.state.stores

    detection = await asyncio.to_thread(stores.sqlite.get_detection, alert_id)
    events = await _fetch_events_for_detection(stores, detection) if detection else []

    if not events:
        events = await _fetch_recent_events(stores)

    events_for_engine = [{**e, "id": e["event_id"]} for e in events]
    alerts_for_engine = []
    if detection:
        first_event_id = (detection.get("matched_event_ids") or [None])[0]
        alerts_for_engine = [{
            "id": alert_id,
            "event_id": first_event_id,
            "severity": detection.get("severity", "medium"),
            "description": detection.get("explanation", ""),
            "attack_tags": [],
        }]

    result = await asyncio.to_thread(
        lambda: _build_causality(alert_id, events_for_engine, alerts_for_engine)
    )

    if not result:
        return {
            "alert_id": alert_id,
            "edges": [],
            "chain": [],
            "techniques": [],
            "score": 0,
            "first_event": "",
            "last_event": "",
        }
    return {
        "alert_id": alert_id,
        "edges": result.get("edges", []),
        "chain": result.get("chain", []),
        "techniques": result.get("techniques", []),
        "score": result.get("score", 0),
        "first_event": result.get("first_event", ""),
        "last_event": result.get("last_event", ""),
    }


# ---------------------------------------------------------------------------
# POST /api/causality/query
# ---------------------------------------------------------------------------

@causality_router.post("/query")
async def investigation_query(request: Request, request_body: dict):
    """Flexible investigation query endpoint.
    Accepts: {"q": str, "entity_id": str|null, "technique": str|null,
              "severity": str|null, "limit": int=20, "offset": int=0}
    Returns: {"events": [...], "total": int}
    """
    stores = request.app.state.stores

    q = str(request_body.get("q", "")).lower()
    severity = request_body.get("severity")
    technique = request_body.get("technique")
    limit = min(int(request_body.get("limit", 20)), 100)
    offset = int(request_body.get("offset", 0))

    conditions = []
    params: list = []

    if q:
        conditions.append(
            "(LOWER(hostname) LIKE ? OR LOWER(event_type) LIKE ? "
            "OR LOWER(src_ip) LIKE ? OR LOWER(dst_ip) LIKE ? OR LOWER(domain) LIKE ?)"
        )
        like_q = f"%{q}%"
        params.extend([like_q, like_q, like_q, like_q, like_q])
    if severity:
        conditions.append("LOWER(severity) = LOWER(?)")
        params.append(severity)
    if technique:
        conditions.append("LOWER(attack_technique) LIKE ?")
        params.append(f"%{technique.lower()}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    count_rows = await stores.duckdb.fetch_all(
        f"SELECT COUNT(*) FROM normalized_events {where}",
        params if params else None,
    )
    total = count_rows[0][0] if count_rows else 0

    rows = await stores.duckdb.fetch_all(
        f"SELECT * FROM normalized_events {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (params + [limit, offset]) if params else [limit, offset],
    )
    events = [_row_to_dict(row) for row in rows]

    return {
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# POST /api/causality/investigate/{alert_id}/summary
# ---------------------------------------------------------------------------

@causality_router.post("/investigate/{alert_id}/summary")
async def get_investigation_summary(alert_id: str, request: Request):
    """Generate an AI-assisted investigation summary for an alert.
    Returns a completed summary string (not streaming).
    Read-only — does not modify underlying data.
    """
    if _format_summary_prompt is None:
        raise HTTPException(status_code=503, detail="Investigation summary not available")
    if _build_causality is None:
        raise HTTPException(status_code=503, detail="Causality engine not available")

    stores = request.app.state.stores

    detection = await asyncio.to_thread(stores.sqlite.get_detection, alert_id)
    if not detection:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id!r} not found")

    events = await _fetch_events_for_detection(stores, detection)
    events_for_engine = [{**e, "id": e["event_id"]} for e in events]

    first_event_id = (detection.get("matched_event_ids") or [None])[0]
    alerts_for_engine = [{
        "id": alert_id,
        "event_id": first_event_id,
        "severity": detection.get("severity", "medium"),
        "description": detection.get("explanation", ""),
        "attack_tags": [],
    }]

    result = await asyncio.to_thread(
        lambda: _build_causality(alert_id, events_for_engine, alerts_for_engine)
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id!r} not found")

    severity = detection.get("severity", "unknown")

    prompt = _format_summary_prompt(
        alert_id=alert_id,
        severity=severity,
        first_event=result.get("first_event", ""),
        last_event=result.get("last_event", ""),
        techniques=result.get("techniques", []),
        nodes=result.get("nodes", []),
        chain=result.get("chain", []),
    )

    try:
        import os

        import httpx
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{ollama_host}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            summary = (
                resp.json().get("response", "")
                if resp.status_code == 200
                else f"[LLM unavailable: HTTP {resp.status_code}]"
            )
    except Exception as exc:
        summary = f"[LLM unavailable: {type(exc).__name__}]"

    return {
        "alert_id": alert_id,
        "summary": summary,
        "techniques": result.get("techniques", []),
        "score": result.get("score", 0),
    }
