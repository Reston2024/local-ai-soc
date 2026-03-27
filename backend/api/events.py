"""
Events API — query and search normalized security events from DuckDB.

Endpoints:
  GET  /events               — paginated event list with filters
  GET  /events/search        — full-text search (MUST be before /{event_id})
  GET  /events/{event_id}    — single event by ID
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger
from backend.models.event import EventListResponse, NormalizedEvent

log = get_logger(__name__)
router = APIRouter(prefix="/events", tags=["events"])

# DuckDB column order — must match NormalizedEvent.to_duckdb_row()
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


def _rows_to_events(rows: list[dict[str, Any]]) -> list[NormalizedEvent]:
    """Convert a list of dicts (from DuckDB fetch_df) to NormalizedEvent objects."""
    events: list[NormalizedEvent] = []
    for row in rows:
        try:
            events.append(NormalizedEvent(**row))
        except Exception as exc:
            log.warning(
                "Failed to parse event row",
                event_id=row.get("event_id"),
                error=str(exc),
            )
    return events


# ---------------------------------------------------------------------------
# GET /events
# ---------------------------------------------------------------------------


@router.get("", response_model=EventListResponse)
async def list_events(
    request: Request,
    # Filters
    hostname: Optional[str] = Query(None, description="Filter by hostname (exact match)"),
    process_name: Optional[str] = Query(None, description="Filter by process name (ILIKE)"),
    case_id: Optional[str] = Query(None, description="Filter by case ID"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    timestamp_from: Optional[datetime] = Query(None, description="Start of time range (ISO-8601)"),
    timestamp_to: Optional[datetime] = Query(None, description="End of time range (ISO-8601)"),
    # Pagination
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Events per page"),
) -> EventListResponse:
    """
    Return a paginated list of normalized events with optional filters.

    All filters are additive (AND logic).  String filters use case-insensitive
    ILIKE matching where indicated.
    """
    stores = request.app.state.stores
    offset = (page - 1) * page_size

    # Build WHERE clauses dynamically
    conditions: list[str] = []
    params: list[Any] = []

    if hostname:
        conditions.append("hostname ILIKE ?")
        params.append(f"%{hostname}%")
    if process_name:
        conditions.append("process_name ILIKE ?")
        params.append(f"%{process_name}%")
    if case_id:
        conditions.append("case_id = ?")
        params.append(case_id)
    if severity:
        conditions.append("severity ILIKE ?")
        params.append(severity)
    if event_type:
        conditions.append("event_type ILIKE ?")
        params.append(f"%{event_type}%")
    if timestamp_from:
        conditions.append("timestamp >= ?")
        params.append(timestamp_from)
    if timestamp_to:
        conditions.append("timestamp <= ?")
        params.append(timestamp_to)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Count query
    count_sql = f"SELECT COUNT(*) FROM normalized_events {where_clause}"
    count_rows = await stores.duckdb.fetch_all(count_sql, params if params else None)
    total = count_rows[0][0] if count_rows else 0

    # Data query
    data_sql = f"""
        SELECT * FROM normalized_events
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """
    data_params = (params or []) + [page_size, offset]
    rows = await stores.duckdb.fetch_df(data_sql, data_params)

    events = _rows_to_events(rows)

    log.debug(
        "Events listed",
        total=total,
        returned=len(events),
        page=page,
        filters=conditions,
    )

    return EventListResponse(
        events=events,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + len(events)) < total,
    )


# ---------------------------------------------------------------------------
# GET /events/search  (must be before /{event_id} to avoid routing conflict)
# ---------------------------------------------------------------------------


@router.get("/search")
async def search_events(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500, description="Search query string"),
    case_id: Optional[str] = Query(None, description="Restrict search to a specific case"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> JSONResponse:
    """
    Full-text search across key event fields using DuckDB ILIKE.

    Searches: hostname, username, process_name, command_line, file_path,
              domain, url, attack_technique, attack_tactic, raw_event.

    For production-scale deployments consider DuckDB's full-text search
    extension (fts) or pushing to Chroma vector search.
    """
    stores = request.app.state.stores

    search_term = f"%{q}%"

    conditions: list[str] = [
        """(
            hostname        ILIKE ?
            OR username     ILIKE ?
            OR process_name ILIKE ?
            OR command_line ILIKE ?
            OR file_path    ILIKE ?
            OR domain       ILIKE ?
            OR url          ILIKE ?
            OR attack_technique ILIKE ?
            OR attack_tactic    ILIKE ?
            OR raw_event    ILIKE ?
        )"""
    ]
    # 10 params for the ILIKE clauses above
    params: list[Any] = [search_term] * 10

    if case_id:
        conditions.append("case_id = ?")
        params.append(case_id)

    where_clause = "WHERE " + " AND ".join(conditions)

    # Count
    count_sql = f"SELECT COUNT(*) FROM normalized_events {where_clause}"
    count_rows = await stores.duckdb.fetch_all(count_sql, params)
    total = count_rows[0][0] if count_rows else 0

    # Data
    data_sql = f"""
        SELECT * FROM normalized_events
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """
    data_params = params + [limit, offset]
    rows = await stores.duckdb.fetch_df(data_sql, data_params)

    events = _rows_to_events(rows)

    log.debug(
        "Event search",
        query=q,
        total=total,
        returned=len(events),
    )

    return JSONResponse(
        content={
            "events": [e.model_dump(mode="json") for e in events],
            "total": total,
            "query": q,
            "limit": limit,
            "offset": offset,
        }
    )


# ---------------------------------------------------------------------------
# GET /events/{event_id}
# ---------------------------------------------------------------------------


@router.get("/{event_id}")
async def get_event(event_id: str, request: Request) -> JSONResponse:
    """
    Return a single event by its event_id.

    Returns 404 if the event does not exist.
    """
    stores = request.app.state.stores

    rows = await stores.duckdb.fetch_df(
        "SELECT * FROM normalized_events WHERE event_id = ?",
        [event_id],
    )

    if not rows:
        raise HTTPException(status_code=404, detail=f"Event {event_id!r} not found")

    try:
        event = NormalizedEvent(**rows[0])
    except Exception as exc:
        log.error("Failed to parse event", event_id=event_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to deserialize event") from exc

    log.debug("Event fetched", event_id=event_id)
    return JSONResponse(content=event.model_dump(mode="json"))
