"""
AssetStore — SQLite CRUD for the Phase 34 asset inventory.

Provides:
- AssetStore: SQLite CRUD for the assets table (IP classification, upsert, list, get, tag).
- _classify_ip(): RFC1918 + loopback → "internal", else "external".
- _apply_asset_upsert(): Synchronous helper for ingestion pipeline — called inside
  asyncio.to_thread() block, never wraps its own to_thread.

All AssetStore methods are synchronous — call via asyncio.to_thread() from async handlers.
"""

from __future__ import annotations

import ipaddress
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from backend.models.event import NormalizedEvent

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS assets (
    ip         TEXT PRIMARY KEY,
    hostname   TEXT,
    tag        TEXT NOT NULL,
    risk_score INTEGER DEFAULT 0,
    last_seen  TEXT NOT NULL,
    first_seen TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_tag       ON assets (tag);
CREATE INDEX IF NOT EXISTS idx_assets_last_seen ON assets (last_seen);
"""

# ---------------------------------------------------------------------------
# IP classification
# ---------------------------------------------------------------------------


def _classify_ip(ip: str) -> str:
    """
    Classify IP as 'internal' (RFC1918 + loopback) or 'external'.

    Loopback is checked before private because both overlap in Python's
    ipaddress module (127.x.x.x is both loopback AND not private, but the
    is_private check in Python 3.11+ considers 127/8 private — check loopback
    explicitly first for clarity and consistency).

    Malformed IP strings return 'external' (safe default).
    """
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_loopback or addr.is_private:
            return "internal"
        return "external"
    except ValueError:
        return "external"


# ---------------------------------------------------------------------------
# AssetStore
# ---------------------------------------------------------------------------


class AssetStore:
    """
    Manages the assets table in the shared SQLite database.

    Constructor accepts a sqlite3.Connection directly for testability —
    the SQLiteStore in sqlite_store.py holds the connection; AssetStore wraps it.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.executescript(_DDL)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert_asset(
        self,
        ip: str,
        hostname: Optional[str],
        tag: str,
        last_seen: str,
    ) -> None:
        """
        Insert or update an asset record.

        On conflict (same IP), updates hostname (if not None), tag, and last_seen.
        first_seen is preserved from the original INSERT — never overwritten.
        """
        self._conn.execute(
            """
            INSERT INTO assets (ip, hostname, tag, last_seen, first_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                hostname  = COALESCE(excluded.hostname, assets.hostname),
                tag       = excluded.tag,
                last_seen = excluded.last_seen
            """,
            (ip, hostname, tag, last_seen, last_seen),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_assets(self, limit: int = 200) -> list[dict]:
        """
        Return assets ordered by last_seen DESC with alert_count and risk_score.

        alert_count: always 0 for Phase 34 — the detections table does not carry
        src_ip/dst_ip columns (it stores matched_event_ids as a JSON array).
        risk_score: MIN(100, alert_count * 5) = 0 until detections schema is extended.
        Both fields are returned for API compatibility with Plans 03/04.
        """
        cursor = self._conn.execute(
            """
            SELECT
                ip,
                hostname,
                tag,
                last_seen,
                first_seen,
                0   AS alert_count,
                0   AS risk_score
            FROM assets
            ORDER BY last_seen DESC
            LIMIT ?
            """,
            (limit,),
        )
        columns = ["ip", "hostname", "tag", "last_seen", "first_seen", "alert_count", "risk_score"]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_asset(self, ip: str) -> Optional[dict]:
        """Return a single asset dict by IP, or None if not found."""
        cursor = self._conn.execute(
            """
            SELECT
                ip,
                hostname,
                tag,
                last_seen,
                first_seen,
                0 AS alert_count,
                0 AS risk_score
            FROM assets
            WHERE ip = ?
            """,
            (ip,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        columns = ["ip", "hostname", "tag", "last_seen", "first_seen", "alert_count", "risk_score"]
        return dict(zip(columns, row))

    def asset_count(self) -> int:
        """Return total number of assets in the table."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM assets")
        row = cursor.fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def set_tag(self, ip: str, tag: str) -> None:
        """Manually override the tag for an asset."""
        self._conn.execute(
            "UPDATE assets SET tag = ? WHERE ip = ?",
            (tag, ip),
        )
        self._conn.commit()


# ---------------------------------------------------------------------------
# Ingestion pipeline helper
# ---------------------------------------------------------------------------


def _apply_asset_upsert(event: NormalizedEvent, asset_store: AssetStore) -> None:
    """
    Upsert src_ip and dst_ip from a normalized event into the asset store.

    Silently skips None/empty IPs. Synchronous — called inside asyncio.to_thread()
    block alongside _apply_ioc_matching(). Do NOT wrap in another to_thread.

    Args:
        event:       NormalizedEvent with optional src_ip/dst_ip/hostname.
        asset_store: AssetStore instance backed by the shared SQLite connection.
    """
    now = datetime.now(timezone.utc).isoformat()

    for ip in filter(None, [event.src_ip, event.dst_ip]):
        tag = _classify_ip(ip)
        asset_store.upsert_asset(
            ip=ip,
            hostname=event.hostname,
            tag=tag,
            last_seen=now,
        )
