"""Tag management for investigation cases.

Operates on a raw sqlite3.Connection so callers can use either an on-disk
database (via SQLiteStore._conn) or an in-memory :memory: connection in tests.

Route handlers should wrap these functions in asyncio.to_thread():
    await asyncio.to_thread(tagging.add_tag, sqlite_store._conn, case_id, tag)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def add_tag(conn: sqlite3.Connection, case_id: str, tag: str) -> None:
    """Add *tag* to *case_id*.  Idempotent — duplicate inserts are silently ignored."""
    conn.execute(
        "INSERT OR IGNORE INTO case_tags (case_id, tag, created_at) VALUES (?, ?, ?)",
        (case_id, tag, _now_iso()),
    )
    conn.commit()


def remove_tag(conn: sqlite3.Connection, case_id: str, tag: str) -> None:
    """Remove *tag* from *case_id*.  No-op if the tag does not exist."""
    conn.execute(
        "DELETE FROM case_tags WHERE case_id = ? AND tag = ?",
        (case_id, tag),
    )
    conn.commit()


def list_tags(conn: sqlite3.Connection, case_id: str) -> list[str]:
    """Return all tags for *case_id* ordered by creation time."""
    cursor = conn.execute(
        "SELECT tag FROM case_tags WHERE case_id = ? ORDER BY created_at",
        (case_id,),
    )
    return [row[0] for row in cursor.fetchall()]


def add_tags_to_case(conn: sqlite3.Connection, case_id: str, tags: list[str]) -> None:
    """Convenience wrapper — add multiple tags in one call."""
    for tag in tags:
        add_tag(conn, case_id, tag)
