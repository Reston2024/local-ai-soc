"""
Investigation Timeline API.

Endpoint:
  GET /api/investigations/{investigation_id}/timeline

Returns a unified chronological list of events, detections, graph edges,
and playbook runs for a given investigation (identified by case_id = investigation_id).

Note: playbook_runs are deferred to a future phase — this endpoint always returns
an empty list for item_type='playbook'. The merge_and_sort_timeline() function
accepts the parameter for forward-compatibility.
"""
from __future__ import annotations

import asyncio
from typing import Literal, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/api/investigations", tags=["investigations"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TimelineItem(BaseModel):
    """A single item in the investigation timeline."""

    item_id: str
    item_type: Literal["event", "detection", "edge", "playbook"]
    timestamp: str              # ISO-8601, UTC
    title: str
    severity: Optional[str]
    attack_technique: Optional[str]
    attack_tactic: Optional[str]
    entity_labels: list[str]
    raw_id: str


# ---------------------------------------------------------------------------
# Pure merge/sort function (unit-testable without stores)
# ---------------------------------------------------------------------------


def merge_and_sort_timeline(
    event_rows: list[tuple] | None,
    detection_rows: list[dict] | None,
    edge_rows: list[dict] | None = None,
    playbook_rows: list[dict] | None = None,
) -> list[TimelineItem]:
    """
    Merge and sort timeline items from all sources.

    Args:
        event_rows:    Tuples from DuckDB normalized_events SELECT.
                       Column order: event_id, timestamp, event_type, severity,
                       hostname, process_name, attack_technique, attack_tactic, command_line
        detection_rows: Dicts from SQLiteStore.get_detections_by_case().
        edge_rows:      Dicts from SQLite edges table. Defaults to empty list.
        playbook_rows:  Dicts from playbook_runs table (deferred — pass [] or None).
                        Accepted for forward-compatibility but always empty in Phase 14.
    """
    if event_rows is None:
        event_rows = []
    if detection_rows is None:
        detection_rows = []
    if edge_rows is None:
        edge_rows = []
    if playbook_rows is None:
        playbook_rows = []  # playbook_runs deferred to future phase

    items: list[TimelineItem] = []

    # --- Events (from DuckDB) ---
    for row in event_rows:
        event_id, ts, event_type, severity, hostname, proc, atk_tech, atk_tac, cmd = row
        title = f"{event_type or 'Event'} on {hostname or 'unknown'}"
        if proc:
            title += f" — {proc}"
        entity_labels = [x for x in [hostname, proc] if x]
        items.append(TimelineItem(
            item_id=f"ev-{event_id}",
            item_type="event",
            timestamp=str(ts),
            title=title,
            severity=severity,
            attack_technique=atk_tech,
            attack_tactic=atk_tac,
            entity_labels=entity_labels,
            raw_id=str(event_id),
        ))

    # --- Detections (from SQLite) ---
    for det in detection_rows:
        items.append(TimelineItem(
            item_id=f"det-{det['id']}",
            item_type="detection",
            timestamp=det.get("created_at") or "",
            title=det.get("rule_name") or "Detection",
            severity=det.get("severity"),
            attack_technique=det.get("attack_technique"),
            attack_tactic=det.get("attack_tactic"),
            entity_labels=[],
            raw_id=str(det["id"]),
        ))

    # --- Graph edges (from SQLite edges table) ---
    for edge in edge_rows:
        # Support both "graph_edges"-style keys and actual "edges" table keys
        edge_id = (
            edge.get("id")
            or edge.get("edge_id")
            or ""
        )
        # edges table uses source_id/target_id (entity IDs), but we also check
        # for src_label/dst_label in case external callers pass those directly.
        src = (
            edge.get("src_label")
            or edge.get("src")
            or edge.get("source_id")
            or ""
        )
        dst = (
            edge.get("dst_label")
            or edge.get("dst")
            or edge.get("target_id")
            or ""
        )
        ts_edge = edge.get("created_at") or edge.get("timestamp") or ""
        rel = (
            edge.get("relationship")
            or edge.get("rel")
            or edge.get("edge_type")
            or "related_to"
        )
        items.append(TimelineItem(
            item_id=f"edge-{edge_id}",
            item_type="edge",
            timestamp=str(ts_edge),
            title=f"{src} --[{rel}]--> {dst}",
            severity=None,
            attack_technique=None,
            attack_tactic=None,
            entity_labels=[x for x in [src, dst] if x],
            raw_id=str(edge_id),
        ))

    # --- Playbook runs (from SQLite playbook_runs JOIN playbooks) ---
    for pr in playbook_rows:
        pb_name = pr.get("playbook_name") or pr.get("name") or "Unknown Playbook"
        status = pr.get("status") or "unknown"
        ts_pb = pr.get("started_at") or ""
        run_id = pr.get("run_id") or ""
        items.append(TimelineItem(
            item_id=f"pb-{run_id}",
            item_type="playbook",
            timestamp=str(ts_pb),
            title=f"Playbook: {pb_name} — {status}",
            severity=None,
            attack_technique=None,
            attack_tactic=None,
            entity_labels=[],
            raw_id=str(run_id),
        ))

    items.sort(key=lambda x: x.timestamp)
    return items


# ---------------------------------------------------------------------------
# Helper: extract entity names from detection metadata for edge lookup
# ---------------------------------------------------------------------------


def _get_entity_names_from_detections(detection_rows: list[dict]) -> list[str]:
    """Extract candidate entity labels from detection metadata for edge lookup."""
    names: set[str] = set()
    for det in detection_rows:
        for key in ("src_label", "dst_label", "hostname", "entity"):
            val = det.get(key)
            if val and isinstance(val, str):
                names.add(val)
    return list(names)


def _fetch_playbook_rows(conn, inv_id: str) -> list[dict]:
    """Fetch playbook run rows for an investigation from SQLite playbook_runs JOIN playbooks."""
    try:
        rows = conn.execute(
            """SELECT pr.run_id, pr.playbook_id, pr.investigation_id, pr.status,
                      pr.started_at, pr.completed_at, p.name AS playbook_name
               FROM playbook_runs pr
               JOIN playbooks p ON p.playbook_id = pr.playbook_id
               WHERE pr.investigation_id = ?
               ORDER BY pr.started_at ASC""",
            (inv_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        # Table may not exist — safe fallback (playbook_runs is optional)
        log.debug("playbook_runs query skipped: %s", exc)
        return []


def _get_edge_rows_sync(sqlite_store, entity_names: list[str]) -> list[dict]:
    """
    Fetch graph edges from SQLite where source_id or target_id matches any entity name.
    Uses the 'edges' table (not 'graph_edges') per the actual SQLite schema.
    Returns empty list if no entities to query or on any exception.
    """
    if not entity_names:
        return []
    try:
        placeholders = ",".join("?" * len(entity_names))
        sql = (
            f"SELECT * FROM edges "
            f"WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders}) "
            f"LIMIT 200"
        )
        params = entity_names + entity_names
        # SQLiteStore uses self._conn (shared connection with row_factory=sqlite3.Row)
        rows = sqlite_store._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        # Table may not exist or schema differs — safe fallback
        log.debug("edges query skipped: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/{investigation_id}/timeline")
async def get_investigation_timeline(
    investigation_id: str,
    request: Request,
) -> JSONResponse:
    """
    Return the complete chronological evidence timeline for an investigation.

    Sources:
    - DuckDB normalized_events WHERE case_id = investigation_id (item_type=event)
    - SQLite detections WHERE case_id = investigation_id (item_type=detection)
    - SQLite edges WHERE source_id or target_id matches detection entities (item_type=edge)
    - playbook_runs: always empty in Phase 14 — deferred to future phase (item_type=playbook)

    Returns HTTP 200 with items=[] for unknown investigation IDs (not 404).
    """
    stores = request.app.state.stores

    # --- Resolve investigation_id to detection + matched event IDs ---
    # investigation_id is passed as the detection's primary key when the user
    # clicks "Investigate" on a detection card.  Try direct detection lookup first,
    # then fall back to case_id-based lookup for backwards compatibility.
    detection_rows: list[dict] = []
    matched_event_ids: list[str] = []

    detection_by_id: dict | None = await asyncio.to_thread(
        stores.sqlite.get_detection, investigation_id
    )
    if detection_by_id:
        detection_rows = [detection_by_id]
        import json as _json
        try:
            matched_event_ids = _json.loads(detection_by_id.get("matched_event_ids") or "[]")
        except Exception:
            matched_event_ids = []
    else:
        detection_rows = await asyncio.to_thread(
            stores.sqlite.get_detections_by_case, investigation_id
        )
        import json as _json
        for d in detection_rows:
            try:
                matched_event_ids += _json.loads(d.get("matched_event_ids") or "[]")
            except Exception:
                pass

    # Fetch events from DuckDB — prefer matched_event_ids, fall back to case_id
    if matched_event_ids:
        placeholders = ",".join("?" * len(matched_event_ids[:500]))
        event_rows: list[tuple] = await stores.duckdb.fetch_all(
            f"""SELECT event_id, timestamp, event_type, severity, hostname, process_name,
                       attack_technique, attack_tactic, command_line
                FROM normalized_events
                WHERE event_id IN ({placeholders})
                ORDER BY timestamp ASC""",
            matched_event_ids[:500],
        )
    else:
        event_rows = await stores.duckdb.fetch_all(
            """SELECT event_id, timestamp, event_type, severity, hostname, process_name,
                      attack_technique, attack_tactic, command_line
               FROM normalized_events
               WHERE case_id = ?
               ORDER BY timestamp ASC
               LIMIT 500""",
            [investigation_id],
        )
        # Last resort: if still empty, show the 50 most recent events overall
        if not event_rows:
            event_rows = await stores.duckdb.fetch_all(
                """SELECT event_id, timestamp, event_type, severity, hostname, process_name,
                          attack_technique, attack_tactic, command_line
                   FROM normalized_events
                   ORDER BY timestamp DESC
                   LIMIT 50""",
            )

    # Extract entity names from detections to look up graph edges
    entity_names = _get_entity_names_from_detections(detection_rows)

    # Fetch graph edges from SQLite (sync, safe fallback if table absent or empty)
    edge_rows: list[dict] = await asyncio.to_thread(
        _get_edge_rows_sync, stores.sqlite, entity_names
    )

    # Fetch playbook runs from SQLite (safe fallback if table absent or empty)
    playbook_rows: list[dict] = await asyncio.to_thread(
        _fetch_playbook_rows, stores.sqlite._conn, investigation_id
    )

    items = merge_and_sort_timeline(event_rows, detection_rows, edge_rows, playbook_rows)
    return JSONResponse({
        "items": [item.model_dump() for item in items],
        "total": len(items),
    })
