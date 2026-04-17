"""Phase 53: Privacy blocklist store + background worker.

Follows IocStore + _BaseWorker patterns from feed_sync.py.
"""
from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.core.logging import get_logger

logger = get_logger(__name__)

_EASYPRIVACY_URL = "https://easylist.to/easylist/easyprivacy.txt"
_DISCONNECT_URL = (
    "https://raw.githubusercontent.com/disconnectme/"
    "disconnect-tracking-protection/master/services.json"
)
_DOMAIN_RULE = re.compile(r"^\|\|([a-z0-9.\-]+)\^")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_easyprivacy(text: str) -> list[str]:
    """Extract domains from EasyPrivacy Adblock+ format (~22K domains).

    Returns a list of domain strings stripped of comment and blank lines.
    """
    domains = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("!"):
            continue
        m = _DOMAIN_RULE.match(line)
        if m:
            domains.append(m.group(1).lower())
    return domains


def _parse_disconnect(text: str) -> list[tuple[str, str]]:
    """Returns list of (domain, category) from Disconnect services.json.

    Structure: {categories: {Email: [{CompanyName: {url: [domains]}}]}}
    Returns 2-tuples of (domain, category).
    """
    data = json.loads(text)
    results: list[tuple[str, str]] = []
    for category, companies in data.get("categories", {}).items():
        for company_dict in companies:
            for company_name, company_data in company_dict.items():
                for url, domains in company_data.items():
                    if url == "dnt":  # skip metadata key
                        continue
                    for d in domains:
                        if isinstance(d, str):
                            results.append((d.lower(), category))
    return results


class PrivacyBlocklistStore:
    """SQLite store for privacy blocklist domains. Follows IocStore pattern."""

    _DDL = """
    CREATE TABLE IF NOT EXISTS privacy_blocklist (
        domain      TEXT PRIMARY KEY,
        category    TEXT NOT NULL,
        company     TEXT,
        updated_at  TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_privacy_domain ON privacy_blocklist (domain);
    CREATE TABLE IF NOT EXISTS privacy_feed_meta (
        feed         TEXT PRIMARY KEY,
        last_sync    TEXT,
        domain_count INTEGER DEFAULT 0
    );
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.executescript(self._DDL)
        self._conn.commit()

    def upsert_domain(self, domain: str, category: str, company: Optional[str] = None) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO privacy_blocklist (domain, category, company, updated_at)"
            " VALUES (?, ?, ?, ?)",
            (domain.lower().strip("."), category, company, _now_iso()),
        )
        self._conn.commit()

    def upsert_domains_batch(
        self, rows: list[tuple[str, str, Optional[str]]]
    ) -> None:
        """Bulk upsert. rows: list of (domain, category, company)."""
        now = _now_iso()
        self._conn.executemany(
            "INSERT OR REPLACE INTO privacy_blocklist (domain, category, company, updated_at)"
            " VALUES (?, ?, ?, ?)",
            [(d.lower().strip("."), cat, co, now) for d, cat, co in rows],
        )
        self._conn.commit()

    def is_tracker(self, domain: str) -> bool:
        """Return True if domain (or a parent domain) is in the blocklist."""
        if not domain:
            return False
        domain = domain.lower().strip(".")
        # Check exact + parent domains (e.g. sub.tracker.com → tracker.com)
        parts = domain.split(".")
        for i in range(len(parts) - 1):
            candidate = ".".join(parts[i:])
            row = self._conn.execute(
                "SELECT 1 FROM privacy_blocklist WHERE domain = ? LIMIT 1", (candidate,)
            ).fetchone()
            if row:
                return True
        return False

    def get_category(self, domain: str) -> Optional[str]:
        domain = domain.lower().strip(".")
        row = self._conn.execute(
            "SELECT category FROM privacy_blocklist WHERE domain = ? LIMIT 1", (domain,)
        ).fetchone()
        return row[0] if row else None

    def get_domain_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM privacy_blocklist").fetchone()
        return row[0] if row else 0

    def update_feed_meta(self, feed: str, domain_count: int) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO privacy_feed_meta (feed, last_sync, domain_count)"
            " VALUES (?, ?, ?)",
            (feed, _now_iso(), domain_count),
        )
        self._conn.commit()

    def get_feed_status(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT feed, last_sync, domain_count FROM privacy_feed_meta"
        ).fetchall()
        return [{"feed": r[0], "last_sync": r[1], "domain_count": r[2]} for r in rows]


class PrivacyWorker:
    """Fetches EasyPrivacy + Disconnect.me and populates PrivacyBlocklistStore.

    Does NOT extend _BaseWorker (no ioc_store dependency). Follows the same
    loop-and-backoff pattern manually.

    _sync() is synchronous to allow direct calls in tests. Use run() for the
    async background loop.
    """

    def __init__(self, store: PrivacyBlocklistStore, interval_sec: int = 86400) -> None:
        self._store = store
        self._interval = interval_sec
        self._running = False

    def _sync(self) -> bool:
        """Synchronously fetch EasyPrivacy + Disconnect.me and upsert into store.

        Returns True on success, False on error.
        """
        try:
            logger.info("privacy_worker: fetching EasyPrivacy + Disconnect.me")
            ep_resp = httpx.get(_EASYPRIVACY_URL, timeout=30, follow_redirects=True)
            ep_resp.raise_for_status()
            ep_domains = _parse_easyprivacy(ep_resp.text)

            dc_resp = httpx.get(_DISCONNECT_URL, timeout=30, follow_redirects=True)
            dc_resp.raise_for_status()
            dc_rows = _parse_disconnect(dc_resp.text)

            # Upsert EasyPrivacy domains
            for domain in ep_domains:
                self._store.upsert_domain(domain, "easyprivacy", None)

            # Upsert Disconnect.me domains
            for domain, category in dc_rows:
                self._store.upsert_domain(domain, category, None)

            self._store.update_feed_meta("easyprivacy", len(ep_domains))
            self._store.update_feed_meta("disconnect", len(dc_rows))
            logger.info(
                "privacy_worker: sync complete easyprivacy=%d disconnect=%d",
                len(ep_domains), len(dc_rows),
            )
            return True
        except Exception as exc:
            logger.warning("privacy_worker: sync failed: %s", exc)
            return False

    async def run(self) -> None:
        """Async background loop — sleeps interval_sec then syncs."""
        self._running = True
        backoff = self._interval
        try:
            while True:
                await asyncio.sleep(backoff)
                success = await asyncio.to_thread(self._sync)
                if success:
                    backoff = self._interval
                else:
                    backoff = min(backoff * 2, 3600)
        except asyncio.CancelledError:
            self._running = False
            raise
