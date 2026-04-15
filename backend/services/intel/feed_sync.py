"""
Phase 33: Threat Intelligence feed worker classes.

FeodoWorker, CisaKevWorker, ThreatFoxWorker — asyncio background tasks that
periodically fetch public threat feeds and upsert IOCs into the SQLite store.

All workers follow the MalcolmCollector.run() pattern:
- Exponential backoff on failure (capped at 3600s)
- asyncio.CancelledError re-raised on shutdown
- Synchronous HTTP calls via asyncio.to_thread(httpx.get, url, timeout=30)

Constructor: __init__(self, ioc_store, sqlite_store_conn, interval_sec=3600, duckdb_store=None)
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from backend.services.intel.ioc_store import IocStore
    from backend.stores.duckdb_store import DuckDBStore

log = logging.getLogger(__name__)

_FEODO_URL = "https://feodotracker.abuse.ch/downloads/ipblocklist.csv"
_CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
_THREATFOX_URL = "https://threatfox.abuse.ch/export/csv/ip-port/recent/"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _kv_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Update system_kv table with last_sync timestamp."""
    conn.execute(
        "INSERT OR REPLACE INTO system_kv (key, value, updated_at) VALUES (?, ?, ?)",
        (key, value, _now_iso()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Base worker mixin (internal)
# ---------------------------------------------------------------------------

class _BaseWorker:
    """Shared run() + backoff logic for all feed workers."""

    _kv_key: str = ""
    _feed_name: str = ""

    def __init__(
        self,
        ioc_store: "IocStore",
        sqlite_store_conn: sqlite3.Connection,
        interval_sec: int = 3600,
        duckdb_store: Optional["DuckDBStore"] = None,
    ) -> None:
        self._ioc_store = ioc_store
        self._conn = sqlite_store_conn
        self._interval = interval_sec
        self._duckdb_store = duckdb_store
        self._running = False
        self._consecutive_failures = 0

    async def run(self) -> None:
        """Main loop with exponential backoff on failure."""
        self._running = True
        backoff = self._interval
        try:
            while True:
                await asyncio.sleep(backoff)
                success = await self._sync()
                if success:
                    self._consecutive_failures = 0
                    backoff = self._interval
                else:
                    self._consecutive_failures += 1
                    backoff = min(self._interval * (2 ** self._consecutive_failures), 3600)
        except asyncio.CancelledError:
            self._running = False
            raise

    async def _sync(self) -> bool:
        raise NotImplementedError

    async def _trigger_retroactive_scan(
        self,
        ioc_value: str,
        ioc_type: str,
        bare_ip: Optional[str],
        confidence: int,
    ) -> None:
        """Trigger retroactive DuckDB scan for a newly inserted IOC."""
        if self._duckdb_store is None:
            return
        try:
            from ingestion.loader import retroactive_ioc_scan
            asyncio.create_task(
                retroactive_ioc_scan(
                    ioc_value=ioc_value,
                    ioc_type=ioc_type,
                    bare_ip=bare_ip,
                    confidence=confidence,
                    ioc_store=self._ioc_store,
                    duckdb_store=self._duckdb_store,
                )
            )
        except (ImportError, AttributeError):
            pass  # retroactive_ioc_scan added in Plan 02; graceful degradation


# ---------------------------------------------------------------------------
# Feodo Tracker Worker
# ---------------------------------------------------------------------------

class FeodoWorker(_BaseWorker):
    """
    Fetches Feodo Tracker IP blocklist CSV and upserts into ioc_store.

    Feed: https://feodotracker.abuse.ch/downloads/ipblocklist.csv
    Columns: first_seen_utc, dst_ip, dst_port, c2_status, last_online, malware
    """

    _kv_key = "intel.feodo.last_sync"
    _feed_name = "feodo"

    def _parse_feodo_csv(self, text: str) -> list[dict]:
        """Parse Feodo CSV text.

        The Feodo blocklist uses commented-out headers (lines starting with '#').
        The actual column header is embedded in the first comment line:
          # first_seen_utc,dst_ip,dst_port,c2_status,last_online,malware

        Data rows are NOT prefixed with '#'.
        """
        results = []
        # Extract field names from the last comment line before data rows
        fieldnames = ["first_seen_utc", "dst_ip", "dst_port", "c2_status", "last_online", "malware"]
        for line in text.splitlines():
            if line.startswith("#"):
                stripped = line.lstrip("# ").strip()
                if "dst_ip" in stripped:
                    fieldnames = [f.strip() for f in stripped.split(",")]

        reader = csv.DictReader(
            (line for line in text.splitlines() if not line.startswith("#")),
            fieldnames=fieldnames,
        )
        for row in reader:
            dst_ip = row.get("dst_ip", "").strip()
            malware = row.get("malware", "").strip()
            first_seen = row.get("first_seen_utc", "").strip()
            last_online = row.get("last_online", "").strip()
            if not dst_ip:
                continue
            results.append({
                "ioc_value": dst_ip,
                "ioc_type": "ip",
                "malware_family": malware or None,
                "first_seen": first_seen or None,
                "last_seen": last_online or None,
            })
        return results

    async def _sync(self) -> bool:
        try:
            response = await asyncio.to_thread(
                httpx.get, _FEODO_URL, timeout=30
            )
            response.raise_for_status()
        except (httpx.HTTPError, Exception) as exc:
            log.warning("Feodo feed fetch failed: %s", exc)
            return False

        try:
            rows = self._parse_feodo_csv(response.text)
            now = _now_iso()
            for row in rows:
                is_new = self._ioc_store.upsert_ioc(
                    value=row["ioc_value"],
                    ioc_type=row["ioc_type"],
                    confidence=50,
                    first_seen=row["first_seen"],
                    last_seen=row["last_seen"],
                    malware_family=row["malware_family"],
                    actor_tag=None,
                    feed_source=self._feed_name,
                    extra_json=None,
                )
                if is_new:
                    await self._trigger_retroactive_scan(
                        ioc_value=row["ioc_value"],
                        ioc_type=row["ioc_type"],
                        bare_ip=None,
                        confidence=50,
                    )
            _kv_set(self._conn, self._kv_key, now)
            log.info("Feodo feed synced: %d IOCs", len(rows))
            return True
        except Exception as exc:
            log.warning("Feodo feed parse failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# CISA KEV Worker
# ---------------------------------------------------------------------------

class CisaKevWorker(_BaseWorker):
    """
    Fetches CISA Known Exploited Vulnerabilities JSON and upserts CVE IOCs.

    Feed: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
    Schema: {"vulnerabilities": [{"cveID": ..., "dateAdded": ..., "vulnerabilityName": ...}]}
    """

    _kv_key = "intel.cisa_kev.last_sync"
    _feed_name = "cisa_kev"

    def _parse_kev_json(self, text: str) -> list[dict]:
        """Parse CISA KEV JSON response."""
        data = json.loads(text)
        vulns = data.get("vulnerabilities", [])
        results = []
        for vuln in vulns:
            cve_id = vuln.get("cveID", "").strip()
            date_added = vuln.get("dateAdded", "").strip()
            name = vuln.get("vulnerabilityName", "").strip()
            if not cve_id:
                continue
            results.append({
                "ioc_value": cve_id,
                "ioc_type": "cve",
                "confidence": 40,
                "actor_tag": name or None,
                "first_seen": date_added or None,
            })
        return results

    async def _sync(self) -> bool:
        try:
            response = await asyncio.to_thread(
                httpx.get, _CISA_KEV_URL, timeout=30
            )
            response.raise_for_status()
        except (httpx.HTTPError, Exception) as exc:
            log.warning("CISA KEV feed fetch failed: %s", exc)
            return False

        try:
            rows = self._parse_kev_json(response.text)
            now = _now_iso()
            for row in rows:
                self._ioc_store.upsert_ioc(
                    value=row["ioc_value"],
                    ioc_type=row["ioc_type"],
                    confidence=row["confidence"],
                    first_seen=row["first_seen"],
                    last_seen=None,
                    malware_family=None,
                    actor_tag=row["actor_tag"],
                    feed_source=self._feed_name,
                    extra_json=None,
                )
            _kv_set(self._conn, self._kv_key, now)
            log.info("CISA KEV feed synced: %d CVEs", len(rows))
            return True
        except Exception as exc:
            log.warning("CISA KEV feed parse failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# ThreatFox Worker
# ---------------------------------------------------------------------------

class ThreatFoxWorker(_BaseWorker):
    """
    Fetches ThreatFox IP:Port CSV export and upserts into ioc_store.

    Feed: https://threatfox.abuse.ch/export/csv/ip-port/recent/
    Columns (15): first_seen_utc, ioc_id, ioc_value (ip:port), ioc_type,
                  malware_printable, confidence_level, tags, ...
    """

    _kv_key = "intel.threatfox.last_sync"
    _feed_name = "threatfox"

    def _parse_threatfox_csv(self, text: str) -> list[dict]:
        """Parse ThreatFox CSV, skip comment lines starting with '#'."""
        results = []
        reader = csv.reader(
            line for line in text.splitlines()
            if not line.startswith("#")
        )
        for row in reader:
            if len(row) < 6:
                continue
            ioc_value = row[2].strip().strip('"')
            ioc_type = row[3].strip().strip('"')
            malware_printable = row[4].strip().strip('"') if len(row) > 4 else None
            confidence_level_str = row[5].strip().strip('"') if len(row) > 5 else "0"
            tags = row[6].strip().strip('"') if len(row) > 6 else None
            first_seen = row[0].strip().strip('"')

            if not ioc_value:
                continue

            # Extract bare_ip from "ip:port" format
            bare_ip: Optional[str] = None
            if ":" in ioc_value:
                bare_ip = ioc_value.rsplit(":", 1)[0]

            # Use 50 as base score for scoring consistency with Feodo
            confidence = 50

            results.append({
                "ioc_value": ioc_value,
                "ioc_type": ioc_type,
                "bare_ip": bare_ip,
                "confidence": confidence,
                "malware_family": malware_printable or None,
                "actor_tag": tags or None,
                "first_seen": first_seen or None,
            })
        return results

    async def _sync(self) -> bool:
        try:
            response = await asyncio.to_thread(
                httpx.get, _THREATFOX_URL, timeout=30
            )
            response.raise_for_status()
        except (httpx.HTTPError, Exception) as exc:
            log.warning("ThreatFox feed fetch failed: %s", exc)
            return False

        try:
            rows = self._parse_threatfox_csv(response.text)
            now = _now_iso()
            for row in rows:
                is_new = self._ioc_store.upsert_ioc(
                    value=row["ioc_value"],
                    ioc_type=row["ioc_type"],
                    confidence=row["confidence"],
                    first_seen=row["first_seen"],
                    last_seen=None,
                    malware_family=row["malware_family"],
                    actor_tag=row["actor_tag"],
                    feed_source=self._feed_name,
                    extra_json=None,
                    bare_ip=row.get("bare_ip"),
                )
                if is_new:
                    await self._trigger_retroactive_scan(
                        ioc_value=row["ioc_value"],
                        ioc_type=row["ioc_type"],
                        bare_ip=row.get("bare_ip"),
                        confidence=row["confidence"],
                    )
            _kv_set(self._conn, self._kv_key, now)
            log.info("ThreatFox feed synced: %d IOCs", len(rows))
            return True
        except Exception as exc:
            log.warning("ThreatFox feed parse failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Phase 50: MISP Worker
# ---------------------------------------------------------------------------

class MispWorker(_BaseWorker):
    """
    Syncs IOC attributes from a self-hosted MISP instance via PyMISP.

    MISP must be deployed and reachable before this worker starts.
    Set MISP_ENABLED=True in settings to activate.
    PyMISP uses the blocking ``requests`` library — all calls via asyncio.to_thread().
    """

    _kv_key = "intel.misp.last_sync"
    _feed_name = "misp"

    def __init__(
        self,
        ioc_store: "IocStore",
        sqlite_store_conn: sqlite3.Connection,
        interval_sec: int = 21600,       # 6 hours default
        duckdb_store: Optional["DuckDBStore"] = None,
        misp_url: str = "",
        misp_key: str = "",
        misp_ssl: bool = False,
        last_hours: int = 24,
    ) -> None:
        super().__init__(ioc_store, sqlite_store_conn, interval_sec, duckdb_store)
        self._misp_url = misp_url
        self._misp_key = misp_key
        self._misp_ssl = misp_ssl
        self._last_hours = last_hours

    async def _sync(self) -> bool:
        from backend.services.intel.misp_sync import MispSyncService

        svc = MispSyncService(self._misp_url, self._misp_key, ssl=self._misp_ssl)
        last_param = f"{self._last_hours}h"
        try:
            attributes = await asyncio.to_thread(
                svc.fetch_ioc_attributes,
                to_ids=True,
                limit=5000,
                last=last_param,
            )
        except Exception as exc:
            log.warning("MISP sync failed: %s", exc)
            return False

        for attr in attributes:
            is_new = self._ioc_store.upsert_ioc(
                value=attr["value"],
                ioc_type=attr["ioc_type"],
                confidence=attr["confidence"],
                first_seen=attr["first_seen"],
                last_seen=attr["last_seen"],
                malware_family=attr["malware_family"],
                actor_tag=attr["actor_tag"],
                feed_source="misp",
                extra_json=attr["extra_json"],
            )
            if is_new:
                await self._trigger_retroactive_scan(
                    ioc_value=attr["value"],
                    ioc_type=attr["ioc_type"],
                    bare_ip=None,
                    confidence=attr["confidence"],
                )

        _kv_set(self._conn, self._kv_key, _now_iso())
        log.info("MISP sync complete: %d attributes processed", len(attributes))
        return True
