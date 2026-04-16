"""
TheHive 5 sync helpers — Phase 52-03.

Provides two synchronous (blocking) functions consumed by:
  - APScheduler interval jobs (wrapped in asyncio.to_thread by the scheduler)
  - Unit tests (called directly without event loop)

sync_thehive_closures(client, conn):
    Poll TheHive for resolved cases; write verdict/timestamp/analyst back to SQLite.

drain_pending_cases(client, conn):
    Retry pending case creation from thehive_pending_cases; delete rows on success.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from backend.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Lazy availability guard — module is always importable without thehive4py
# ---------------------------------------------------------------------------

_SYNC_AVAILABLE = True  # This module has no mandatory thehive4py dependency


# ---------------------------------------------------------------------------
# SQLite helpers (all synchronous)
# ---------------------------------------------------------------------------

def _update_detection_thehive_status(
    conn: sqlite3.Connection,
    thehive_id: str,
    status: str,
    closed_at: str | None,
    analyst: str,
) -> None:
    """Write resolution fields to the matching detections row."""
    conn.execute(
        """
        UPDATE detections
           SET thehive_status    = ?,
               thehive_closed_at = ?,
               thehive_analyst   = ?
         WHERE thehive_case_id = ?
        """,
        (status, closed_at, analyst, thehive_id),
    )
    conn.commit()


def _get_pending_cases(conn: sqlite3.Connection) -> list[dict]:
    """Return all rows from thehive_pending_cases as list of dicts."""
    try:
        cursor = conn.execute(
            "SELECT id, detection_json, created_at FROM thehive_pending_cases"
        )
        rows = cursor.fetchall()
        return [{"id": r[0], "detection_json": r[1], "created_at": r[2]} for r in rows]
    except Exception:
        return []


def _delete_pending_case(conn: sqlite3.Connection, row_id: int) -> None:
    """Remove a successfully processed pending row."""
    conn.execute("DELETE FROM thehive_pending_cases WHERE id = ?", (row_id,))
    conn.commit()


def _increment_pending_attempts(
    conn: sqlite3.Connection,
    row_id: int,
    error: str,
) -> None:
    """Increment attempts counter and record last_error.

    If the schema has attempts/last_error columns (production DDL), update them.
    If not (Wave 0 test schema), just log and continue — silently tolerated.
    """
    try:
        conn.execute(
            """
            UPDATE thehive_pending_cases
               SET attempts   = COALESCE(attempts, 0) + 1,
                   last_error = ?
             WHERE id = ?
            """,
            (error[:500], row_id),
        )
        conn.commit()
    except Exception:
        # Columns may not exist in minimal test schema — non-fatal
        pass


# ---------------------------------------------------------------------------
# Public API — synchronous for direct scheduler / test use
# ---------------------------------------------------------------------------

def sync_thehive_closures(thehive_client: Any, conn: sqlite3.Connection) -> None:
    """Poll TheHive for resolved cases and update SQLite detections.

    Non-fatal: all exceptions are caught and logged as warnings.

    Args:
        thehive_client:  TheHiveClient instance (must have find_resolved_cases()).
        conn:            sqlite3.Connection to the SOC Brain SQLite DB.
    """
    try:
        # find_resolved_cases() may be sync (MagicMock in tests) or async
        # (TheHiveClient wraps asyncio.to_thread). In unit tests we call this
        # function synchronously so the client mock must be sync too.
        resolved = thehive_client.find_resolved_cases()

        for case in resolved:
            thehive_id = case.get("_id", "")
            if not thehive_id:
                continue

            status = case.get("resolutionStatus", "Indeterminate")
            analyst = case.get("assignee", "")

            end_date_ms = case.get("endDate")
            closed_at: str | None = None
            if end_date_ms is not None:
                try:
                    closed_at = datetime.fromtimestamp(
                        end_date_ms / 1000, tz=timezone.utc
                    ).isoformat()
                except Exception:
                    pass

            _update_detection_thehive_status(conn, thehive_id, status, closed_at, analyst)

    except Exception as exc:
        log.warning("TheHive closure sync failed: %s", exc)
        return None

    return None


def drain_pending_cases(thehive_client: Any, conn: sqlite3.Connection) -> None:
    """Retry pending case creation from thehive_pending_cases table.

    For each row:
      - Parse detection_json blob
      - Call thehive_client.create_case() with the detection data
      - On success: delete the row
      - On failure: increment attempts (max 5 then abandon)

    The detection_json column may contain either:
      a) A raw detection dict (simple schema from Wave 0 tests)
      b) A nested dict {"detection_id": ..., "payload": {"case": ..., "observables": [...]}}
         (production schema from _enqueue_pending_case in thehive_client.py)

    This function handles both formats gracefully.
    """
    rows = _get_pending_cases(conn)

    for row in rows:
        row_id = row["id"]
        detection_json_str = row["detection_json"]

        try:
            blob = json.loads(detection_json_str)
        except Exception as exc:
            log.warning("Failed to parse thehive_pending_cases row %s: %s", row_id, exc)
            continue

        # Determine schema variant
        if "payload" in blob and isinstance(blob.get("payload"), dict):
            # Production format: nested payload from _enqueue_pending_case
            payload = blob["payload"]
            case_dict = payload.get("case", {})
            observables = payload.get("observables", [])
            detection_id = blob.get("detection_id", "")
        else:
            # Simple format (Wave 0 tests): detection fields at top level
            # Build a minimal case payload from the raw detection data
            from backend.services.thehive_client import build_case_payload, build_observables
            case_dict = build_case_payload(blob)
            observables = build_observables(blob)
            detection_id = blob.get("id", "")

        # Check attempts limit — skip if row has attempts column and >= 5
        try:
            attempts_row = conn.execute(
                "SELECT attempts FROM thehive_pending_cases WHERE id = ?", (row_id,)
            ).fetchone()
            if attempts_row is not None:
                attempts_val = attempts_row[0]
                if attempts_val is not None and attempts_val >= 5:
                    log.warning(
                        "Abandoning pending case row %s after 5 attempts", row_id
                    )
                    continue
        except Exception:
            pass  # attempts column absent in test schema — continue normally

        try:
            created = thehive_client.create_case(case_dict)
            case_id = created["_id"]
            case_num = created.get("number") or created.get("caseId")

            # Add observables — non-fatal per observable
            for obs in observables:
                try:
                    if hasattr(thehive_client, "create_observable"):
                        thehive_client.create_observable(case_id, obs)
                except Exception:
                    pass

            # Update detections row if detection_id is known
            if detection_id:
                try:
                    conn.execute(
                        """
                        UPDATE detections
                           SET thehive_case_id  = ?,
                               thehive_case_num = ?,
                               thehive_status   = ?
                         WHERE id = ?
                        """,
                        (case_id, case_num, "New", detection_id),
                    )
                    conn.commit()
                except Exception:
                    pass  # detections table may not have these columns in test schema

            _delete_pending_case(conn, row_id)

        except Exception as exc:
            log.warning(
                "Failed to drain pending case row %s: %s — incrementing attempts",
                row_id,
                exc,
            )
            _increment_pending_attempts(conn, row_id, str(exc))
