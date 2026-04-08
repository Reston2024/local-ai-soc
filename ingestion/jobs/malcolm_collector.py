"""
Malcolm NSM OpenSearch collector — polls Suricata alert and IPFire syslog indices.

Mirrors the FirewallCollector pattern:
- asyncio polling loop with exponential backoff (max 300s)
- Heartbeat via SQLiteStore.set_kv("malcolm.last_heartbeat", iso_str)
- Timestamp-cursor tracking per index in system_kv
- Ingest via IngestionLoader.ingest_events()
- status() method returns dict matching FirewallCollector.status() shape

OpenSearch HTTP calls use httpx with verify=False (intentional — Malcolm uses self-signed TLS).
Do NOT use opensearch-py — httpx is already a project dependency.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx

from backend.core.logging import get_logger
from backend.models.event import NormalizedEvent

log = get_logger(__name__)


class MalcolmCollector:
    """Background asyncio task: poll Malcolm OpenSearch indices and ingest events."""

    def __init__(
        self,
        loader=None,
        sqlite_store=None,
        interval_sec: int = 30,
        opensearch_url: str = "https://192.168.1.22:9200",
        opensearch_user: str = "malcolm_internal",
        opensearch_pass: str = "",
        verify_ssl: bool = False,
    ) -> None:
        self._loader = loader
        self._sqlite = sqlite_store
        self._interval = interval_sec
        self._url = opensearch_url.rstrip("/")
        self._auth = (opensearch_user, opensearch_pass)
        self._verify_ssl = verify_ssl
        self._consecutive_failures: int = 0
        self._running: bool = False
        self._alerts_ingested: int = 0
        self._syslog_ingested: int = 0

    # ------------------------------------------------------------------
    # HTTP helpers (synchronous — run in asyncio.to_thread)
    # ------------------------------------------------------------------

    def _http_search(self, index: str, body: dict) -> dict:
        """POST /{index}/_search — synchronous; call via asyncio.to_thread."""
        url = f"{self._url}/{index}/_search"
        r = httpx.post(url, json=body, auth=self._auth, verify=self._verify_ssl, timeout=30.0)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Query DSL
    # ------------------------------------------------------------------

    @staticmethod
    def _build_query(last_ts, event_dataset_filter: bool = False) -> dict:
        """
        Build OpenSearch range query for new documents since last_ts.
        Falls back to last 5 minutes on first run to avoid bulk-ingesting history.
        """
        if last_ts is None:
            since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        else:
            since = str(last_ts)

        must_clauses: list[dict] = [{"range": {"@timestamp": {"gt": since}}}]
        if event_dataset_filter:
            must_clauses.append({"term": {"event.dataset": "alert"}})

        return {
            "query": {"bool": {"must": must_clauses}},
            "sort": [{"@timestamp": "asc"}],
            "size": 500,
        }

    # ------------------------------------------------------------------
    # Index polling helpers
    # ------------------------------------------------------------------

    async def _fetch_index(self, index_pattern: str, cursor_key: str, event_dataset_filter: bool) -> list[dict]:
        """Fetch new documents from an OpenSearch index since the stored cursor."""
        last_ts = await asyncio.to_thread(self._sqlite.get_kv, cursor_key)
        query = self._build_query(last_ts, event_dataset_filter)
        try:
            result = await asyncio.to_thread(self._http_search, index_pattern, query)
        except Exception as exc:
            log.warning("MalcolmCollector: OpenSearch fetch failed", index=index_pattern, error=str(exc))
            return []
        hits = result.get("hits", {}).get("hits", [])
        if hits:
            max_ts = hits[-1].get("_source", {}).get("@timestamp", "")
            if max_ts:
                await asyncio.to_thread(self._sqlite.set_kv, cursor_key, max_ts)
        return hits

    # ------------------------------------------------------------------
    # Normalization stubs (implemented in plan 27-03)
    # ------------------------------------------------------------------

    def _normalize_alert(self, doc: dict) -> NormalizedEvent | None:
        """Normalize arkime_sessions3-* alert doc to NormalizedEvent. Implemented in plan 27-03."""
        return None

    def _normalize_syslog(self, doc: dict) -> NormalizedEvent | None:
        """Normalize malcolm_beats_syslog_* doc to NormalizedEvent. Implemented in plan 27-03."""
        return None

    # ------------------------------------------------------------------
    # Poll cycle
    # ------------------------------------------------------------------

    async def _poll_and_ingest(self) -> bool:
        """Fetch new events from both index patterns, normalize, and ingest. Returns True on success."""
        try:
            # --- Suricata alerts ---
            alert_hits = await self._fetch_index(
                "arkime_sessions3-*",
                "malcolm.alerts.last_timestamp",
                event_dataset_filter=True,
            )
            alert_batch: list[NormalizedEvent] = []
            for hit in alert_hits:
                event = self._normalize_alert(hit.get("_source", {}))
                if event is not None:
                    alert_batch.append(event)
            if alert_batch and self._loader is not None:
                await self._loader.ingest_events(alert_batch)
                self._alerts_ingested += len(alert_batch)

            # --- IPFire syslog ---
            syslog_hits = await self._fetch_index(
                "malcolm_beats_syslog_*",
                "malcolm.syslog.last_timestamp",
                event_dataset_filter=False,
            )
            syslog_batch: list[NormalizedEvent] = []
            for hit in syslog_hits:
                event = self._normalize_syslog(hit.get("_source", {}))
                if event is not None:
                    syslog_batch.append(event)
            if syslog_batch and self._loader is not None:
                await self._loader.ingest_events(syslog_batch)
                self._syslog_ingested += len(syslog_batch)

            # Heartbeat (proves collector loop is alive)
            iso_str = datetime.now(timezone.utc).isoformat()
            await asyncio.to_thread(self._sqlite.set_kv, "malcolm.last_heartbeat", iso_str)
            return True

        except Exception as exc:
            log.warning("MalcolmCollector poll error", error=str(exc))
            return False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Main polling loop. Cancellation propagates via CancelledError."""
        self._running = True
        backoff = self._interval
        try:
            while True:
                await asyncio.sleep(backoff)
                success = await self._poll_and_ingest()
                if success:
                    self._consecutive_failures = 0
                    backoff = self._interval
                else:
                    self._consecutive_failures += 1
                    backoff = min(self._interval * (2 ** self._consecutive_failures), 300)
        except asyncio.CancelledError:
            self._running = False
            raise

    def status(self) -> dict:
        """Return current collector status dict."""
        return {
            "running": self._running,
            "alerts_ingested": self._alerts_ingested,
            "syslog_ingested": self._syslog_ingested,
            "consecutive_failures": self._consecutive_failures,
        }
