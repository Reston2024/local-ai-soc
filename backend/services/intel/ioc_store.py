"""
IocStore — SQLite CRUD for the Phase 33 Threat Intelligence Platform.

Wraps a sqlite3.Connection (from SQLiteStore) and provides synchronous
methods for upserting IOCs, checking matches, decay, and status queries.
All methods are called via asyncio.to_thread() in production code.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from math import floor
from typing import Optional


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class IocStore:
    """
    Manages the ioc_store and ioc_hits tables in the shared SQLite database.

    Constructor accepts a sqlite3.Connection directly for testability —
    the SQLiteStore in sqlite_store.py holds the connection; IocStore wraps it.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert_ioc(
        self,
        value: str,
        ioc_type: str,
        confidence: int,
        first_seen: Optional[str],
        last_seen: Optional[str],
        malware_family: Optional[str],
        actor_tag: Optional[str],
        feed_source: str,
        extra_json: Optional[str],
        bare_ip: Optional[str] = None,
    ) -> bool:
        """
        Insert a new IOC or update an existing one (same value+type).

        Returns:
            True  — new row was inserted.
            False — existing row was updated.

        Used by feed_sync.py to trigger retroactive scans only for
        genuinely new IOCs (not updates to confidence/last_seen).
        """
        now = _now_iso()

        # Check if the IOC already exists before upserting
        cursor = self._conn.execute(
            "SELECT 1 FROM ioc_store WHERE ioc_value=? AND ioc_type=?",
            (value, ioc_type),
        )
        existing = cursor.fetchone()

        if existing:
            self._conn.execute(
                """
                UPDATE ioc_store
                SET confidence=?, last_seen=?, malware_family=?, actor_tag=?,
                    extra_json=?, updated_at=?, ioc_status='active'
                WHERE ioc_value=? AND ioc_type=?
                """,
                (confidence, last_seen, malware_family, actor_tag,
                 extra_json, now, value, ioc_type),
            )
            self._conn.commit()
            return False
        else:
            self._conn.execute(
                """
                INSERT INTO ioc_store
                    (ioc_value, ioc_type, bare_ip, confidence, first_seen, last_seen,
                     malware_family, actor_tag, feed_source, ioc_status,
                     extra_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (value, ioc_type, bare_ip, confidence, first_seen, last_seen,
                 malware_family, actor_tag, feed_source, extra_json, now, now),
            )
            self._conn.commit()
            return True

    # ------------------------------------------------------------------
    # Match check
    # ------------------------------------------------------------------

    def check_ioc_match(
        self,
        src_ip: Optional[str],
        dst_ip: Optional[str],
    ) -> tuple[bool, int, Optional[str]]:
        """
        Check if src_ip or dst_ip appears in the IOC store.

        Also supports bare_ip lookup for ThreatFox ip:port entries.

        Returns:
            (True, confidence, actor_tag)  — if a match found with confidence > 0
            (False, 0, None)               — if no match found
        """
        candidates = [ip for ip in (src_ip, dst_ip) if ip]

        for ip in candidates:
            # Exact match on ioc_value (ip type)
            cursor = self._conn.execute(
                """
                SELECT confidence, actor_tag FROM ioc_store
                WHERE ioc_value=? AND ioc_type='ip' AND confidence > 0
                ORDER BY confidence DESC
                LIMIT 1
                """,
                (ip,),
            )
            row = cursor.fetchone()
            if row:
                return (True, row[0], row[1])

            # bare_ip lookup (for ThreatFox ip:port entries)
            cursor = self._conn.execute(
                """
                SELECT confidence, actor_tag FROM ioc_store
                WHERE bare_ip=? AND confidence > 0
                ORDER BY confidence DESC
                LIMIT 1
                """,
                (ip,),
            )
            row = cursor.fetchone()
            if row:
                return (True, row[0], row[1])

        return (False, 0, None)

    # ------------------------------------------------------------------
    # Feed status
    # ------------------------------------------------------------------

    def get_feed_status(self) -> list[dict]:
        """
        Return status for each known feed.

        Status values:
          "ok"    — synced within the last 2 hours
          "stale" — last_sync > 2 hours ago
          "never" — no sync recorded
          "error" — (reserved for future use)
        """
        from datetime import timedelta

        feeds = ["feodo", "cisa_kev", "threatfox"]
        result = []

        now = datetime.now(tz=timezone.utc)
        stale_threshold = timedelta(hours=2)

        for feed in feeds:
            kv_key = f"intel.{feed}.last_sync"
            cursor = self._conn.execute(
                "SELECT value FROM system_kv WHERE key=?", (kv_key,)
            )
            row = cursor.fetchone()

            # Count IOCs for this feed
            count_cursor = self._conn.execute(
                "SELECT COUNT(*) FROM ioc_store WHERE feed_source=?", (feed,)
            )
            count_row = count_cursor.fetchone()
            ioc_count = count_row[0] if count_row else 0

            if row is None:
                status = "never"
                last_sync = None
            else:
                last_sync = row[0]
                try:
                    last_sync_dt = datetime.fromisoformat(last_sync)
                    if last_sync_dt.tzinfo is None:
                        last_sync_dt = last_sync_dt.replace(tzinfo=timezone.utc)
                    age = now - last_sync_dt
                    status = "ok" if age <= stale_threshold else "stale"
                except (ValueError, TypeError):
                    status = "error"

            result.append({
                "feed": feed,
                "last_sync": last_sync,
                "ioc_count": ioc_count,
                "status": status,
            })

        return result

    # ------------------------------------------------------------------
    # Decay
    # ------------------------------------------------------------------

    def decay_confidence(self) -> None:
        """
        Apply daily confidence decay — subtract 1 pt per call (approximates 5 pts/week).

        Floor at 0. Sets ioc_status='expired' where confidence hits 0.
        Called by the APScheduler daily cron job at 00:05.
        """
        # Decay all active IOCs: confidence = max(0, confidence - 1)
        self._conn.execute(
            """
            UPDATE ioc_store
            SET confidence = MAX(0, confidence - 1),
                updated_at = ?
            WHERE ioc_status = 'active'
            """,
            (_now_iso(),),
        )
        # Mark expired where confidence reached 0
        self._conn.execute(
            """
            UPDATE ioc_store
            SET ioc_status = 'expired'
            WHERE confidence = 0 AND ioc_status = 'active'
            """,
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # List hits
    # ------------------------------------------------------------------

    def list_hits(self, limit: int = 100) -> list[dict]:
        """
        Return IOC hit records sorted by risk_score DESC.

        The ioc_hits table is populated by Plan 02 (at-ingest matching).
        Returns empty list if no hits recorded yet.
        """
        cursor = self._conn.execute(
            """
            SELECT id, event_timestamp, hostname, src_ip, dst_ip,
                   ioc_value, ioc_type, ioc_source, risk_score,
                   actor_tag, malware_family, matched_at
            FROM ioc_hits
            ORDER BY risk_score DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        columns = [
            "id", "event_timestamp", "hostname", "src_ip", "dst_ip",
            "ioc_value", "ioc_type", "ioc_source", "risk_score",
            "actor_tag", "malware_family", "matched_at",
        ]
        return [dict(zip(columns, row)) for row in rows]
