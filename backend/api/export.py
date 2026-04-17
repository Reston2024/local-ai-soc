"""
Export API — export events, detections, and graph data for analyst use.

Endpoints:
  GET /export/events/csv              — export filtered events as CSV
  GET /export/events/json             — export filtered events as JSON
  GET /export/case/{case_id}/bundle   — export full case bundle as JSON
  GET /export/case/{case_id}/notebook — export one-click incident notebook as JSON
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/export", tags=["export"])


# ---------------------------------------------------------------------------
# GET /export/events/csv
# ---------------------------------------------------------------------------


@router.get("/events/csv")
async def export_events_csv(
    request: Request,
    case_id: Optional[str] = Query(None),
    hostname: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    timestamp_from: Optional[datetime] = Query(None),
    timestamp_to: Optional[datetime] = Query(None),
    limit: int = Query(10_000, ge=1, le=100_000),
) -> StreamingResponse:
    """
    Export events as CSV (streamed).

    Applies the same filters as GET /events but returns a downloadable CSV.
    """
    stores = request.app.state.stores

    conditions: list[str] = []
    params: list[Any] = []

    if case_id:
        conditions.append("case_id = ?")
        params.append(case_id)
    if hostname:
        conditions.append("hostname ILIKE ?")
        params.append(f"%{hostname}%")
    if severity:
        conditions.append("severity ILIKE ?")
        params.append(severity)
    if timestamp_from:
        conditions.append("timestamp >= ?")
        params.append(timestamp_from)
    if timestamp_to:
        conditions.append("timestamp <= ?")
        params.append(timestamp_to)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT * FROM normalized_events
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT ?
    """
    params.append(limit)

    rows = await stores.duckdb.fetch_df(sql, params)

    def _generate_csv() -> bytes:
        buf = io.StringIO()
        if not rows:
            writer = csv.writer(buf)
            writer.writerow(["No events found"])
            return buf.getvalue().encode("utf-8")

        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            # Stringify any complex types for CSV compatibility
            clean = {k: str(v) if v is not None else "" for k, v in row.items()}
            writer.writerow(clean)
        return buf.getvalue().encode("utf-8")

    csv_bytes = await asyncio.to_thread(_generate_csv)
    filename = f"events_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    log.info("Events CSV export", rows=len(rows), export_filename=filename)
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# GET /export/events/json
# ---------------------------------------------------------------------------


@router.get("/events/json")
async def export_events_json(
    request: Request,
    case_id: Optional[str] = Query(None),
    hostname: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(10_000, ge=1, le=100_000),
) -> StreamingResponse:
    """Export events as newline-delimited JSON (NDJSON)."""
    stores = request.app.state.stores

    conditions: list[str] = []
    params: list[Any] = []

    if case_id:
        conditions.append("case_id = ?")
        params.append(case_id)
    if hostname:
        conditions.append("hostname ILIKE ?")
        params.append(f"%{hostname}%")
    if severity:
        conditions.append("severity ILIKE ?")
        params.append(severity)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"SELECT * FROM normalized_events {where_clause} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = await stores.duckdb.fetch_df(sql, params)

    def _generate_ndjson() -> bytes:
        lines = []
        for row in rows:
            # Convert datetime objects to ISO strings for JSON serialization
            clean = {}
            for k, v in row.items():
                if isinstance(v, datetime):
                    clean[k] = v.isoformat()
                else:
                    clean[k] = v
            lines.append(json.dumps(clean))
        return "\n".join(lines).encode("utf-8")

    ndjson_bytes = await asyncio.to_thread(_generate_ndjson)
    filename = f"events_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}.ndjson"

    log.info("Events JSON export", rows=len(rows))
    return StreamingResponse(
        iter([ndjson_bytes]),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# GET /export/case/{case_id}/bundle
# ---------------------------------------------------------------------------


@router.get("/case/{case_id}/bundle")
async def export_case_bundle(case_id: str, request: Request) -> JSONResponse:
    """
    Export a complete case bundle as JSON.

    Includes: case metadata, entities, edges, detections, and associated events.
    Suitable for archiving, transfer, or audit trail purposes.
    """
    stores = request.app.state.stores

    # Case metadata
    case = await asyncio.to_thread(stores.sqlite.get_case, case_id)
    if not case:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Case {case_id!r} not found")

    # Entities
    entities = await asyncio.to_thread(stores.sqlite.get_entities_by_case, case_id)

    # Detections
    detections = await asyncio.to_thread(stores.sqlite.get_detections_by_case, case_id)

    # Events from DuckDB
    events = await stores.duckdb.fetch_df(
        "SELECT * FROM normalized_events WHERE case_id = ? ORDER BY timestamp",
        [case_id],
    )

    # Edges: collect for all entities in case
    entity_ids = {e["id"] for e in entities}

    def _fetch_edges(ids: set[str]) -> list[dict]:
        all_edges: list[dict] = []
        seen: set = set()
        for eid in ids:
            for edge in stores.sqlite.get_edges_from(eid, depth=1):
                if edge["target_id"] in ids:
                    key = (edge["source_id"], edge["edge_type"], edge["target_id"])
                    if key not in seen:
                        seen.add(key)
                        all_edges.append(edge)
        return all_edges

    edges = await asyncio.to_thread(_fetch_edges, entity_ids)

    # Serialize datetimes in events
    def _serialize(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    events_serialized = [
        {k: _serialize(v) for k, v in row.items()}
        for row in events
    ]

    bundle = {
        "export_timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "case": case,
        "stats": {
            "entities": len(entities),
            "edges": len(edges),
            "detections": len(detections),
            "events": len(events_serialized),
        },
        "entities": entities,
        "edges": edges,
        "detections": detections,
        "events": events_serialized,
    }

    log.info(
        "Case bundle exported",
        case_id=case_id,
        entities=len(entities),
        events=len(events_serialized),
        detections=len(detections),
    )
    return JSONResponse(content=bundle)


# ---------------------------------------------------------------------------
# GET /export/case/{case_id}/notebook
# ---------------------------------------------------------------------------


def _serialize_value(obj: Any) -> Any:
    """Convert a value to a JSON-serializable form (datetimes -> ISO strings)."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def _duration_seconds(started_at: Any, completed_at: Any) -> Optional[float]:
    """
    Compute (completed_at - started_at) in seconds.

    Both inputs may be ISO-8601 strings or datetime objects.  Returns ``None``
    if either value is missing or cannot be parsed.
    """
    if not started_at or not completed_at:
        return None
    try:
        if isinstance(started_at, str):
            started_dt = datetime.fromisoformat(started_at)
        else:
            started_dt = started_at
        if isinstance(completed_at, str):
            completed_dt = datetime.fromisoformat(completed_at)
        else:
            completed_dt = completed_at
        return (completed_dt - started_dt).total_seconds()
    except (ValueError, TypeError):
        return None


@router.get("/case/{case_id}/notebook")
async def export_case_notebook(case_id: str, request: Request) -> JSONResponse:
    """
    Export a one-click incident notebook for post-incident review.

    Bundles: case metadata, summary stats (MTTR, counts), detections,
    playbook runs with durations, up to 50 most recent matched events, and
    graph entities linked to the case.

    Every section is wrapped in try/except so the endpoint never 500s when
    optional data is missing; it only raises 404 if the case itself is absent.
    """
    stores = request.app.state.stores

    # Case metadata — 404 if missing.  Return JSONResponse directly so the
    # app-level 404 handler (which rewrites `detail` to "Not found") does not
    # clobber our explicit error payload.
    case = await asyncio.to_thread(stores.sqlite.get_case, case_id)
    if not case:
        return JSONResponse(status_code=404, content={"detail": "Case not found"})

    # Detections
    try:
        detections = await asyncio.to_thread(
            stores.sqlite.get_detections_by_case, case_id
        )
    except Exception as exc:
        log.warning("Notebook: detections fetch failed", case_id=case_id, error=str(exc))
        detections = []

    # Playbook runs — filter by investigation_id (= case_id) OR active_case_id = case_id
    def _fetch_playbook_runs() -> list[dict]:
        sql = (
            "SELECT * FROM playbook_runs "
            "WHERE investigation_id = ? OR active_case_id = ? "
            "ORDER BY started_at DESC"
        )
        rows = stores.sqlite._conn.execute(sql, (case_id, case_id)).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            # Parse steps_completed JSON if present
            if isinstance(d.get("steps_completed"), str):
                try:
                    d["steps_completed"] = json.loads(d["steps_completed"])
                except (json.JSONDecodeError, TypeError):
                    d["steps_completed"] = []
            result.append(d)
        return result

    try:
        raw_runs = await asyncio.to_thread(_fetch_playbook_runs)
    except Exception as exc:
        log.warning("Notebook: playbook runs fetch failed", case_id=case_id, error=str(exc))
        raw_runs = []

    # Build playbook_runs with duration_seconds + step count
    playbook_runs: list[dict] = []
    durations: list[float] = []
    completed_count = 0
    failed_count = 0
    for run in raw_runs:
        duration = _duration_seconds(run.get("started_at"), run.get("completed_at"))
        status = run.get("status")
        steps = run.get("steps_completed") or []
        steps_completed_count = len(steps) if isinstance(steps, list) else 0
        if status == "completed":
            completed_count += 1
            if duration is not None:
                durations.append(duration)
        elif status == "failed":
            failed_count += 1
            if duration is not None:
                durations.append(duration)
        playbook_runs.append({
            "run_id": run.get("run_id"),
            "playbook_id": run.get("playbook_id"),
            "status": status,
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "duration_seconds": duration,
            "steps_completed": steps_completed_count,
            "analyst_notes": run.get("analyst_notes", ""),
        })

    mttr_seconds = (sum(durations) / len(durations)) if durations else None

    # Events sample — up to 50 most recent events referenced by detections
    event_ids: list[str] = []
    seen_ids: set = set()
    for det in detections:
        matched = det.get("matched_event_ids") or []
        if isinstance(matched, str):
            try:
                matched = json.loads(matched)
            except (json.JSONDecodeError, TypeError):
                matched = []
        for eid in matched:
            if eid not in seen_ids:
                seen_ids.add(eid)
                event_ids.append(eid)

    events_sample: list[dict] = []
    if event_ids:
        try:
            placeholders = ",".join(["?"] * len(event_ids))
            sql = (
                f"SELECT * FROM normalized_events "
                f"WHERE event_id IN ({placeholders}) "
                f"ORDER BY timestamp DESC LIMIT 50"
            )
            rows_df = await stores.duckdb.fetch_df(sql, event_ids)
            events_sample = [
                {k: _serialize_value(v) for k, v in row.items()}
                for row in rows_df
            ]
        except Exception as exc:
            log.warning(
                "Notebook: events sample fetch failed",
                case_id=case_id,
                error=str(exc),
            )
            events_sample = []

    # Total events count for the case
    try:
        total_events_rows = await stores.duckdb.fetch_all(
            "SELECT COUNT(*) FROM normalized_events WHERE case_id = ?",
            [case_id],
        )
        total_events = int(total_events_rows[0][0]) if total_events_rows else 0
    except Exception as exc:
        log.warning("Notebook: total events count failed", case_id=case_id, error=str(exc))
        total_events = 0

    # Graph entities linked to this case
    graph_entities: list[dict] = []
    try:
        graph_entities = await asyncio.to_thread(
            stores.sqlite.get_entities_by_case, case_id
        )
    except Exception as exc:
        log.warning("Notebook: graph entities fetch failed", case_id=case_id, error=str(exc))
        graph_entities = []

    # Normalise detections for JSON (datetimes -> iso strings)
    detections_serialized = [
        {k: _serialize_value(v) for k, v in det.items()}
        for det in detections
    ]

    notebook = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "case": case,
        "summary": {
            "total_detections": len(detections),
            "total_events": total_events,
            "total_playbook_runs": len(playbook_runs),
            "playbooks_completed": completed_count,
            "playbooks_failed": failed_count,
            "mttr_seconds": mttr_seconds,
        },
        "detections": detections_serialized,
        "playbook_runs": playbook_runs,
        "events_sample": events_sample,
        "graph_entities": graph_entities,
    }

    log.info(
        "Case notebook exported",
        case_id=case_id,
        detections=len(detections),
        playbook_runs=len(playbook_runs),
        events_sample=len(events_sample),
        mttr_seconds=mttr_seconds,
    )
    return JSONResponse(content=notebook)
