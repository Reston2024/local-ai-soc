"""Timeline reconstruction — aggregates DuckDB events + causality chain for a case."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone

# Deferred causality import (mirrors Phase 5/6 deferred import pattern)
try:
    from backend.causality.attack_chain_builder import find_causal_chain
    _CHAIN_BUILDER_AVAILABLE = True
except ImportError:
    _CHAIN_BUILDER_AVAILABLE = False

from backend.core.logging import get_logger
log = get_logger(__name__)


def _extract_entity_refs(row: dict) -> list[str]:
    """Extract canonical entity IDs from a normalized_events row dict."""
    refs = []
    if row.get("hostname"):
        refs.append(f"host:{row['hostname'].lower()}")
    if row.get("username"):
        refs.append(f"user:{row['username'].lower()}")
    if row.get("process_name"):
        refs.append(f"process:{row['process_name']}")
    if row.get("dst_ip"):
        refs.append(f"ip:{row['dst_ip']}")
    if row.get("domain"):
        refs.append(f"domain:{row['domain'].lower()}")
    return refs


def _score_confidence(row: dict, alert_ids: list[str]) -> float:
    """Assign confidence score to a timeline entry.

    1.0 — event is linked to an alert (event_id appears in alert_ids)
    0.8 — event has attack_technique (part of a causality chain)
    0.5 — default (event in case window)
    """
    event_id = str(row.get("event_id", ""))
    if event_id in alert_ids:
        return 1.0
    if row.get("attack_technique"):
        return 0.8
    return 0.5


def _safe_timestamp(row: dict) -> str:
    ts = row.get("timestamp")
    if ts is None:
        return ""
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)


async def build_timeline(case_id: str, duckdb_store, sqlite_store) -> list[dict]:
    """Reconstruct ordered timeline for a case from DuckDB normalized_events.

    Returns list of timeline entry dicts with required LOCKED fields.
    Returns [] if case not found, duckdb_store is None, or sqlite_store is None.
    """
    if duckdb_store is None or sqlite_store is None:
        return []

    # Get case metadata for alert IDs
    case = await asyncio.to_thread(sqlite_store.get_investigation_case, case_id)
    if case is None:
        log.warning("build_timeline: case %s not found", case_id)
        return []

    alert_ids: list[str] = case.get("related_alerts", [])
    if not isinstance(alert_ids, list):
        alert_ids = []

    # Fetch events for this case from DuckDB, ordered by timestamp
    try:
        rows = await duckdb_store.fetch_df(
            "SELECT * FROM normalized_events WHERE case_id = ? ORDER BY timestamp ASC",
            [case_id],
        )
    except Exception as exc:
        log.warning("build_timeline: DuckDB query failed: %s", exc)
        return []

    timeline: list[dict] = []
    for row in rows:
        entry: dict = {
            "timestamp": _safe_timestamp(row),
            "event_source": row.get("source_type") or "unknown",
            "entity_references": _extract_entity_refs(row),
            "related_alerts": [],
            "confidence_score": _score_confidence(row, alert_ids),
        }
        timeline.append(entry)

    return timeline
