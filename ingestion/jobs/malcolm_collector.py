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
        self._tls_ingested: int = 0
        self._dns_ingested: int = 0
        self._fileinfo_ingested: int = 0
        self._anomaly_ingested: int = 0

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
    def _build_query(
        last_ts,
        event_dataset_filter: bool = False,
        event_type_filter: str | None = None,
    ) -> dict:
        """
        Build OpenSearch range query for new documents since last_ts.
        Falls back to last 5 minutes on first run to avoid bulk-ingesting history.
        event_dataset_filter and event_type_filter are independent — both may be set.
        """
        if last_ts is None:
            since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        else:
            since = str(last_ts)

        must_clauses: list[dict] = [{"range": {"@timestamp": {"gt": since}}}]
        if event_dataset_filter:
            must_clauses.append({"term": {"event.dataset": "alert"}})
        if event_type_filter is not None:
            must_clauses.append({"term": {"event.type": event_type_filter}})

        return {
            "query": {"bool": {"must": must_clauses}},
            "sort": [{"@timestamp": "asc"}],
            "size": 500,
        }

    # ------------------------------------------------------------------
    # Index polling helpers
    # ------------------------------------------------------------------

    async def _fetch_index(
        self,
        index_pattern: str,
        cursor_key: str,
        event_dataset_filter: bool = False,
        event_type_filter: str | None = None,
    ) -> list[dict]:
        """Fetch new documents from an OpenSearch index since the stored cursor."""
        last_ts = await asyncio.to_thread(self._sqlite.get_kv, cursor_key)
        query = self._build_query(last_ts, event_dataset_filter, event_type_filter)
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
        """
        Normalize an arkime_sessions3-* alert document to NormalizedEvent.

        Returns None if src_ip cannot be extracted (incomplete event — drop silently).
        source_type is always "suricata_eve".
        """
        src_ip = (
            (doc.get("source") or {}).get("ip")
            or doc.get("src_ip")
            or doc.get("srcip")
        )
        if not src_ip:
            return None  # Drop incomplete alerts with no source IP

        dst_ip = (
            (doc.get("destination") or {}).get("ip")
            or doc.get("dst_ip")
            or doc.get("dstip")
        )
        src_port_raw = (
            (doc.get("source") or {}).get("port")
            or doc.get("src_port")
        )
        dst_port_raw = (
            (doc.get("destination") or {}).get("port")
            or doc.get("dst_port")
        )

        severity = (
            (doc.get("event") or {}).get("severity")
            or (doc.get("alert") or {}).get("severity")
            or "info"
        )
        detection_source = (
            (doc.get("rule") or {}).get("name")
            or (doc.get("alert") or {}).get("signature")
            or "malcolm_alert"
        )
        hostname = (
            (doc.get("observer") or {}).get("hostname")
            or (doc.get("agent") or {}).get("hostname")
            or "malcolm"
        )

        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)

        raw_event = json.dumps(doc)[:8192]

        return NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=ts,
            ingested_at=datetime.now(timezone.utc),
            source_type="suricata_eve",
            hostname=hostname,
            event_type="alert",
            severity=str(severity).lower() if severity else "info",
            detection_source=detection_source,
            raw_event=raw_event,
            src_ip=str(src_ip),
            dst_ip=str(dst_ip) if dst_ip else None,
            src_port=int(src_port_raw) if src_port_raw else None,
            dst_port=int(dst_port_raw) if dst_port_raw else None,
        )

    def _normalize_syslog(self, doc: dict) -> NormalizedEvent | None:
        """
        Normalize a malcolm_beats_syslog_* document to NormalizedEvent.

        Syslog events are informational — never dropped for missing IPs.
        source_type is always "ipfire_syslog".
        Accepts a dict (OpenSearch _source) or a raw string (plain syslog line).
        """
        if isinstance(doc, str):
            # Plain syslog line — wrap as raw event, no structured fields
            raw_event = doc[:8192]
            return NormalizedEvent(
                event_id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                ingested_at=datetime.now(timezone.utc),
                source_type="ipfire_syslog",
                hostname="ipfire",
                event_type="syslog",
                severity="info",
                detection_source="ipfire_syslog",
                raw_event=raw_event,
            )

        hostname = (
            (doc.get("host") or {}).get("name")
            or doc.get("hostname")
            or "ipfire"
        )

        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)

        src_ip = (
            (doc.get("source") or {}).get("ip")
            or doc.get("src_ip")
            or doc.get("srcip")
        )
        dst_ip = (
            (doc.get("destination") or {}).get("ip")
            or doc.get("dst_ip")
            or doc.get("dstip")
        )

        raw_event = json.dumps(doc)[:8192]

        return NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=ts,
            ingested_at=datetime.now(timezone.utc),
            source_type="ipfire_syslog",
            hostname=hostname,
            event_type="syslog",
            severity="info",
            detection_source="ipfire_syslog",
            raw_event=raw_event,
            src_ip=str(src_ip) if src_ip else None,
            dst_ip=str(dst_ip) if dst_ip else None,
        )

    def _normalize_tls(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (
            (doc.get("source") or {}).get("ip")
            or doc.get("src_ip")
            or doc.get("srcip")
        )
        if not src_ip:
            return None

        dst_ip = (
            (doc.get("destination") or {}).get("ip")
            or doc.get("dst_ip")
            or doc.get("dstip")
        )
        src_port_raw = (doc.get("source") or {}).get("port") or doc.get("src_port")
        dst_port_raw = (doc.get("destination") or {}).get("port") or doc.get("dst_port")

        tls_obj = doc.get("tls") or {}
        tls_version = (
            tls_obj.get("version")
            or doc.get("tls.version")
            or doc.get("tls.version_string")
        )
        ja3_obj = tls_obj.get("ja3") or {}
        tls_ja3 = (
            ja3_obj.get("hash")
            or doc.get("tls.ja3.hash")
            or doc.get("ja3")
        )
        ja3s_obj = tls_obj.get("ja3s") or {}
        tls_ja3s = (
            ja3s_obj.get("hash")
            or doc.get("tls.ja3s.hash")
            or doc.get("ja3s")
        )
        tls_sni = (
            tls_obj.get("sni")
            or doc.get("tls.sni")
            or (doc.get("host") or {}).get("name")
        )
        tls_cipher = tls_obj.get("cipher") or doc.get("tls.cipher")
        server_x509 = (((tls_obj.get("server") or {}).get("x509") or {}).get("subject") or {})
        tls_cert_subject = (
            server_x509.get("common_name")
            or doc.get("tls.server.x509.subject.common_name")
        )
        established = tls_obj.get("established")
        tls_validation_status = (
            "valid" if established is True
            else "failed" if established is False
            else None
        )

        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)

        hostname = (
            (doc.get("observer") or {}).get("hostname")
            or (doc.get("agent") or {}).get("hostname")
            or "malcolm"
        )

        return NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=ts,
            ingested_at=datetime.now(timezone.utc),
            source_type="suricata_eve",
            hostname=hostname,
            event_type="tls",
            severity="info",
            detection_source="suricata_tls",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str(dst_ip) if dst_ip else None,
            src_port=int(src_port_raw) if src_port_raw else None,
            dst_port=int(dst_port_raw) if dst_port_raw else None,
            tls_version=str(tls_version) if tls_version else None,
            tls_ja3=str(tls_ja3) if tls_ja3 else None,
            tls_ja3s=str(tls_ja3s) if tls_ja3s else None,
            tls_sni=str(tls_sni) if tls_sni else None,
            tls_cipher=str(tls_cipher) if tls_cipher else None,
            tls_cert_subject=str(tls_cert_subject) if tls_cert_subject else None,
            tls_validation_status=tls_validation_status,
        )

    def _normalize_dns(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (
            (doc.get("source") or {}).get("ip")
            or doc.get("src_ip")
            or doc.get("srcip")
        )
        if not src_ip:
            return None

        dst_ip = (doc.get("destination") or {}).get("ip") or doc.get("dst_ip")
        src_port_raw = (doc.get("source") or {}).get("port") or doc.get("src_port")
        dst_port_raw = (doc.get("destination") or {}).get("port") or doc.get("dst_port")

        dns_obj = doc.get("dns") or {}
        question_obj = dns_obj.get("question") or {}
        dns_query = (
            question_obj.get("name")
            or doc.get("dns.question.name")
            or doc.get("dns.query")
        )
        dns_query_type = (
            question_obj.get("type")
            or doc.get("dns.question.type")
            or doc.get("dns.type")
        )
        dns_rcode = (
            dns_obj.get("response_code")
            or doc.get("dns.response_code")
            or doc.get("dns.rcode")
        )
        raw_answers = dns_obj.get("answers") or doc.get("dns.answers")
        dns_answers_json: str | None = None
        dns_ttl: int | None = None
        if isinstance(raw_answers, list) and raw_answers:
            dns_answers_json = json.dumps(raw_answers)
            first = raw_answers[0]
            if isinstance(first, dict):
                dns_ttl = int(first["ttl"]) if first.get("ttl") is not None else None

        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)

        hostname = (
            (doc.get("observer") or {}).get("hostname")
            or (doc.get("agent") or {}).get("hostname")
            or "malcolm"
        )

        return NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=ts,
            ingested_at=datetime.now(timezone.utc),
            source_type="suricata_eve",
            hostname=hostname,
            event_type="dns_query",
            severity="info",
            detection_source="suricata_dns",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str(dst_ip) if dst_ip else None,
            src_port=int(src_port_raw) if src_port_raw else None,
            dst_port=int(dst_port_raw) if dst_port_raw else None,
            dns_query=str(dns_query) if dns_query else None,
            dns_query_type=str(dns_query_type) if dns_query_type else None,
            dns_rcode=str(dns_rcode) if dns_rcode else None,
            dns_answers=dns_answers_json,
            dns_ttl=dns_ttl,
        )

    def _normalize_fileinfo(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (
            (doc.get("source") or {}).get("ip")
            or doc.get("src_ip")
            or doc.get("srcip")
        )
        if not src_ip:
            return None

        dst_ip = (doc.get("destination") or {}).get("ip") or doc.get("dst_ip")
        src_port_raw = (doc.get("source") or {}).get("port") or doc.get("src_port")
        dst_port_raw = (doc.get("destination") or {}).get("port") or doc.get("dst_port")

        file_obj = (doc.get("file") or {})
        hash_obj = file_obj.get("hash") or {}
        file_md5 = (
            hash_obj.get("md5")
            or doc.get("file.hash.md5")
            or doc.get("md5")
        )
        file_sha256_eve = (
            hash_obj.get("sha256")
            or doc.get("file.hash.sha256")
        )
        file_mime_type = (
            file_obj.get("type")
            or doc.get("file.mime_type")
            or doc.get("file.type")
        )
        raw_size = file_obj.get("size") or doc.get("file.size")
        file_size_bytes = int(raw_size) if raw_size is not None else None

        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)

        hostname = (
            (doc.get("observer") or {}).get("hostname")
            or (doc.get("agent") or {}).get("hostname")
            or "malcolm"
        )

        return NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=ts,
            ingested_at=datetime.now(timezone.utc),
            source_type="suricata_eve",
            hostname=hostname,
            event_type="file_transfer",
            severity="info",
            detection_source="suricata_fileinfo",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str(dst_ip) if dst_ip else None,
            src_port=int(src_port_raw) if src_port_raw else None,
            dst_port=int(dst_port_raw) if dst_port_raw else None,
            file_md5=str(file_md5) if file_md5 else None,
            file_sha256_eve=str(file_sha256_eve) if file_sha256_eve else None,
            file_mime_type=str(file_mime_type) if file_mime_type else None,
            file_size_bytes=file_size_bytes,
        )

    def _normalize_anomaly(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (
            (doc.get("source") or {}).get("ip")
            or doc.get("src_ip")
            or doc.get("srcip")
        )
        if not src_ip:
            return None

        dst_ip = (doc.get("destination") or {}).get("ip") or doc.get("dst_ip")
        src_port_raw = (doc.get("source") or {}).get("port") or doc.get("src_port")
        dst_port_raw = (doc.get("destination") or {}).get("port") or doc.get("dst_port")

        severity = (
            (doc.get("event") or {}).get("severity")
            or (doc.get("alert") or {}).get("severity")
            or "high"
        )
        detection_source = (
            (doc.get("event") or {}).get("action")
            or (doc.get("anomaly") or {}).get("type")
            or "malcolm_anomaly"
        )
        hostname = (
            (doc.get("observer") or {}).get("hostname")
            or (doc.get("agent") or {}).get("hostname")
            or "malcolm"
        )

        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)

        return NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=ts,
            ingested_at=datetime.now(timezone.utc),
            source_type="suricata_eve",
            hostname=hostname,
            event_type="anomaly",
            severity=str(severity).lower(),
            detection_source=str(detection_source),
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str(dst_ip) if dst_ip else None,
            src_port=int(src_port_raw) if src_port_raw else None,
            dst_port=int(dst_port_raw) if dst_port_raw else None,
        )

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

            # --- TLS events ---
            tls_hits = await self._fetch_index(
                "arkime_sessions3-*",
                "malcolm.tls.last_timestamp",
                event_dataset_filter=False,
                event_type_filter="tls",
            )
            tls_batch: list[NormalizedEvent] = []
            for hit in tls_hits:
                event = self._normalize_tls(hit.get("_source", {}))
                if event is not None:
                    tls_batch.append(event)
            if tls_batch and self._loader is not None:
                await self._loader.ingest_events(tls_batch)
                self._tls_ingested += len(tls_batch)

            # --- DNS events ---
            dns_hits = await self._fetch_index(
                "arkime_sessions3-*",
                "malcolm.dns.last_timestamp",
                event_dataset_filter=False,
                event_type_filter="dns",
            )
            dns_batch: list[NormalizedEvent] = []
            for hit in dns_hits:
                event = self._normalize_dns(hit.get("_source", {}))
                if event is not None:
                    dns_batch.append(event)
            if dns_batch and self._loader is not None:
                await self._loader.ingest_events(dns_batch)
                self._dns_ingested += len(dns_batch)

            # --- Fileinfo events ---
            fileinfo_hits = await self._fetch_index(
                "arkime_sessions3-*",
                "malcolm.fileinfo.last_timestamp",
                event_dataset_filter=False,
                event_type_filter="fileinfo",
            )
            fileinfo_batch: list[NormalizedEvent] = []
            for hit in fileinfo_hits:
                event = self._normalize_fileinfo(hit.get("_source", {}))
                if event is not None:
                    fileinfo_batch.append(event)
            if fileinfo_batch and self._loader is not None:
                await self._loader.ingest_events(fileinfo_batch)
                self._fileinfo_ingested += len(fileinfo_batch)

            # --- Anomaly events ---
            anomaly_hits = await self._fetch_index(
                "arkime_sessions3-*",
                "malcolm.anomaly.last_timestamp",
                event_dataset_filter=False,
                event_type_filter="anomaly",
            )
            anomaly_batch: list[NormalizedEvent] = []
            for hit in anomaly_hits:
                event = self._normalize_anomaly(hit.get("_source", {}))
                if event is not None:
                    anomaly_batch.append(event)
            if anomaly_batch and self._loader is not None:
                await self._loader.ingest_events(anomaly_batch)
                self._anomaly_ingested += len(anomaly_batch)

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
            "tls_ingested": self._tls_ingested,
            "dns_ingested": self._dns_ingested,
            "fileinfo_ingested": self._fileinfo_ingested,
            "anomaly_ingested": self._anomaly_ingested,
        }
