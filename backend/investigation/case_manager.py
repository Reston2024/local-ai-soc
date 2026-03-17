"""Investigation case CRUD — operates on a raw sqlite3 connection.

CaseManager methods accept a sqlite3.Connection as the first argument so that
callers can pass either a real on-disk connection (via SQLiteStore._conn) or an
in-memory :memory: connection in tests.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


_ARRAY_FIELDS = {
    "related_alerts", "related_entities", "timeline_events", "tags", "artifacts"
}


def _parse_case(d: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON array fields in an investigation case dict."""
    for field in _ARRAY_FIELDS:
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except json.JSONDecodeError:
                d[field] = []
    return d


class CaseManager:
    """CRUD operations for investigation_cases table.

    Each method takes a sqlite3.Connection as its first argument so that the
    caller controls the database lifecycle.  This makes unit testing with
    :memory: databases trivial.
    """

    def create_investigation_case(
        self,
        conn: sqlite3.Connection,
        title: str,
        description: str = "",
        case_id: Optional[str] = None,
    ) -> str:
        """Create a new investigation case and return its case_id."""
        cid = case_id or str(uuid4())
        now = _now_iso()
        empty = json.dumps([])
        conn.execute(
            """
            INSERT OR IGNORE INTO investigation_cases
                (case_id, title, description, case_status,
                 related_alerts, related_entities, timeline_events,
                 analyst_notes, tags, artifacts, created_at, updated_at)
            VALUES (?, ?, ?, 'open', ?, ?, ?, '', ?, ?, ?, ?)
            """,
            (cid, title, description, empty, empty, empty, empty, empty, now, now),
        )
        conn.commit()
        return cid

    def get_investigation_case(
        self,
        conn: sqlite3.Connection,
        case_id: str,
    ) -> dict[str, Any] | None:
        """Return an investigation case dict, or None if not found."""
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM investigation_cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if not row:
            return None
        return _parse_case(dict(row))

    def list_investigation_cases(
        self,
        conn: sqlite3.Connection,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List investigation cases, optionally filtered by status."""
        conn.row_factory = sqlite3.Row
        if status:
            rows = conn.execute(
                "SELECT * FROM investigation_cases WHERE case_status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM investigation_cases ORDER BY created_at DESC"
            ).fetchall()
        return [_parse_case(dict(r)) for r in rows]

    def update_investigation_case(
        self,
        conn: sqlite3.Connection,
        case_id: str,
        updates: dict[str, Any],
    ) -> None:
        """Partially update an investigation case.

        Only fields present in *updates* are written; unmentioned fields are
        unchanged.  Array fields supplied as Python lists are serialized to JSON
        automatically.
        """
        serialized: dict[str, Any] = {}
        for k, v in updates.items():
            if k in _ARRAY_FIELDS and isinstance(v, list):
                serialized[k] = json.dumps(v)
            else:
                serialized[k] = v

        set_clause = ", ".join(f"{k} = ?" for k in serialized)
        values = list(serialized.values())
        values.append(_now_iso())   # updated_at
        values.append(case_id)

        conn.execute(
            f"UPDATE investigation_cases SET {set_clause}, updated_at = ? WHERE case_id = ?",
            values,
        )
        conn.commit()
