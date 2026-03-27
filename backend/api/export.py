"""
Export API — export events, detections, and graph data for analyst use.

Endpoints:
  GET /export/events/csv            — export filtered events as CSV
  GET /export/events/json           — export filtered events as JSON
  GET /export/case/{case_id}/bundle — export full case bundle as JSON
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
