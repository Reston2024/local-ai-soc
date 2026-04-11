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
        ubuntu_normalizer_url: str = "",   # Phase 31: empty = disabled
    ) -> None:
        self._loader = loader
        self._sqlite = sqlite_store
        self._interval = interval_sec
        self._interval_sec = interval_sec  # alias for tests
        self._url = opensearch_url.rstrip("/")
        self._auth = (opensearch_user, opensearch_pass)
        self._verify_ssl = verify_ssl
        self._ubuntu_normalizer_url = ubuntu_normalizer_url.rstrip("/")
        self._ubuntu_ingested: int = 0
        self._consecutive_failures: int = 0
        self._running: bool = False
        self._alerts_ingested: int = 0
        self._syslog_ingested: int = 0
        self._tls_ingested: int = 0
        self._dns_ingested: int = 0
        self._fileinfo_ingested: int = 0
        self._anomaly_ingested: int = 0
        self._conn_ingested: int = 0
        self._weird_ingested: int = 0
        # Phase 36-02: new Zeek log type counters
        self._http_ingested: int = 0
        self._ssl_ingested: int = 0
        self._x509_ingested: int = 0
        self._files_ingested: int = 0
        self._notice_ingested: int = 0
        self._kerberos_ingested: int = 0
        self._ntlm_ingested: int = 0
        self._ssh_ingested: int = 0
        self._smb_mapping_ingested: int = 0
        self._smb_files_ingested: int = 0
        self._rdp_ingested: int = 0
        self._dce_rpc_ingested: int = 0
        self._dhcp_ingested: int = 0
        self._dns_zeek_ingested: int = 0
        self._software_ingested: int = 0
        self._known_host_ingested: int = 0
        self._known_service_ingested: int = 0
        self._sip_ingested: int = 0
        self._ftp_ingested: int = 0
        self._smtp_ingested: int = 0
        self._socks_ingested: int = 0
        self._tunnel_ingested: int = 0
        self._pe_ingested: int = 0

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

    def _normalize_conn(self, doc: dict) -> NormalizedEvent | None:
        """Normalize a Zeek conn log document to NormalizedEvent.

        Returns None if src_ip cannot be extracted.
        Uses triple-fallback field access: nested -> dotted flat -> Arkime flat.
        """
        src_ip = (
            (doc.get("source") or {}).get("ip")
            or doc.get("src_ip")
            or doc.get("srcip")
        )
        if not src_ip:
            return None

        network_obj = doc.get("network") or {}
        zeek_conn = (doc.get("zeek") or {}).get("conn") or {}

        conn_state = (
            zeek_conn.get("state")
            or doc.get("zeek.conn.state")
            or network_obj.get("state")
        )
        duration_raw = (
            network_obj.get("duration")
            or (doc.get("event") or {}).get("duration")
        )
        orig_bytes = (
            (doc.get("source") or {}).get("bytes")
            or network_obj.get("bytes")
        )
        resp_bytes = (doc.get("destination") or {}).get("bytes")

        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)

        return NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=ts,
            ingested_at=datetime.now(timezone.utc),
            source_type="zeek",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            event_type="conn",
            severity="info",
            detection_source="zeek_conn",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or doc.get("dst_ip") or "") or None,
            src_port=int(p) if (p := (doc.get("source") or {}).get("port")) else None,
            dst_port=int(p) if (p := (doc.get("destination") or {}).get("port")) else None,
            network_protocol=str(network_obj.get("transport") or "").lower() or None,
            conn_state=str(conn_state) if conn_state else None,
            conn_duration=float(duration_raw) if duration_raw is not None else None,
            conn_orig_bytes=int(orig_bytes) if orig_bytes is not None else None,
            conn_resp_bytes=int(resp_bytes) if resp_bytes is not None else None,
        )

    def _normalize_weird(self, doc: dict) -> NormalizedEvent | None:
        """Normalize a Zeek weird log document to NormalizedEvent.

        Returns None if src_ip cannot be extracted.
        Always severity='high' -- weird events indicate unexpected protocol behavior.
        """
        src_ip = (
            (doc.get("source") or {}).get("ip")
            or doc.get("src_ip")
            or doc.get("srcip")
        )
        if not src_ip:
            return None

        zeek_weird = (doc.get("zeek") or {}).get("weird") or {}
        weird_name = (
            zeek_weird.get("name")
            or doc.get("zeek.weird.name")
            or doc.get("weird_name")
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
            source_type="zeek",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            event_type="weird",
            severity="high",
            detection_source="zeek_weird",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            src_port=int(p) if (p := (doc.get("source") or {}).get("port")) else None,
            dst_port=int(p) if (p := (doc.get("destination") or {}).get("port")) else None,
            zeek_weird_name=str(weird_name) if weird_name else None,
        )

    # ------------------------------------------------------------------
    # Phase 36-02: Zeek normalizers — HTTP/SSL/x509/files/notice
    # ------------------------------------------------------------------

    def _normalize_http(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        http_obj = (doc.get("http") or {})
        req_obj = http_obj.get("request") or {}
        resp_obj = http_obj.get("response") or {}
        url_obj = doc.get("url") or {}
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="http", severity="info",
            detection_source="zeek_http",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            src_port=int(p) if (p := (doc.get("source") or {}).get("port")) else None,
            dst_port=int(p) if (p := (doc.get("destination") or {}).get("port")) else None,
            http_method=req_obj.get("method") or doc.get("zeek.http.method"),
            http_uri=url_obj.get("original") or doc.get("url.original"),
            http_status_code=int(c) if (c := resp_obj.get("status_code") or doc.get("zeek.http.status_code")) else None,
            http_user_agent=(doc.get("user_agent") or {}).get("original") or doc.get("user_agent.original"),
            domain=(doc.get("destination") or {}).get("domain") or (url_obj.get("domain")),
        )

    def _normalize_ssl(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        tls_obj = doc.get("tls") or {}
        zeek_ssl = (doc.get("zeek") or {}).get("ssl") or {}
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="ssl", severity="info",
            detection_source="zeek_ssl",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            src_port=int(p) if (p := (doc.get("source") or {}).get("port")) else None,
            dst_port=int(p) if (p := (doc.get("destination") or {}).get("port")) else None,
            tls_version=tls_obj.get("version") or zeek_ssl.get("version"),
            tls_ja3=(tls_obj.get("client") or {}).get("ja3") or doc.get("tls.client.ja3"),
            tls_sni=zeek_ssl.get("server_name") or doc.get("zeek.ssl.server_name") or (tls_obj.get("client") or {}).get("server_name"),
            tls_cert_subject=(tls_obj.get("server") or {}).get("subject") or zeek_ssl.get("subject"),
        )

    def _normalize_x509(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_x509 = (doc.get("zeek") or {}).get("x509") or {}
        cert_obj = (doc.get("tls") or {}).get("server") or {}
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="x509", severity="info",
            detection_source="zeek_x509",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            tls_cert_subject=zeek_x509.get("subject") or cert_obj.get("subject") or doc.get("zeek.x509.subject"),
        )

    def _normalize_files(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        file_obj = doc.get("file") or {}
        zeek_files = (doc.get("zeek") or {}).get("files") or {}
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="files", severity="info",
            detection_source="zeek_files",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            file_md5=(file_obj.get("hash") or {}).get("md5") or zeek_files.get("md5"),
            file_sha256_eve=(file_obj.get("hash") or {}).get("sha256"),
            file_mime_type=file_obj.get("mime_type") or zeek_files.get("mime_type"),
            file_size_bytes=int(s) if (s := file_obj.get("size") or zeek_files.get("total_bytes")) else None,
            file_path=file_obj.get("name") or zeek_files.get("filename"),
        )

    def _normalize_notice(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_notice = (doc.get("zeek") or {}).get("notice") or {}
        note = zeek_notice.get("note") or doc.get("zeek.notice.note")
        msg = zeek_notice.get("msg") or doc.get("zeek.notice.msg")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="notice", severity="high",
            detection_source="zeek_notice",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            zeek_notice_note=str(note) if note else None,
            zeek_notice_msg=str(msg) if msg else None,
        )

    # ------------------------------------------------------------------
    # Phase 36-02: Zeek normalizers — kerberos/ntlm/ssh
    # ------------------------------------------------------------------

    def _normalize_kerberos(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_krb = (doc.get("zeek") or {}).get("kerberos") or {}
        krb_client = zeek_krb.get("client") or doc.get("zeek.kerberos.client")
        krb_service = zeek_krb.get("service") or doc.get("zeek.kerberos.service")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="kerberos_tgs_request", severity="info",
            detection_source="zeek_kerberos",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            src_port=int(p) if (p := (doc.get("source") or {}).get("port")) else None,
            dst_port=int(p) if (p := (doc.get("destination") or {}).get("port")) else None,
            username=str(krb_client).split("@")[0] if krb_client else None,
            kerberos_client=str(krb_client) if krb_client else None,
            kerberos_service=str(krb_service) if krb_service else None,
        )

    def _normalize_ntlm(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_ntlm = (doc.get("zeek") or {}).get("ntlm") or {}
        ntlm_user = zeek_ntlm.get("username") or doc.get("zeek.ntlm.username")
        ntlm_dom = zeek_ntlm.get("domain") or doc.get("zeek.ntlm.domain")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="ntlm_auth", severity="info",
            detection_source="zeek_ntlm",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            username=str(ntlm_user) if ntlm_user else None,
            ntlm_username=str(ntlm_user) if ntlm_user else None,
            ntlm_domain=str(ntlm_dom) if ntlm_dom else None,
        )

    def _normalize_ssh(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_ssh = (doc.get("zeek") or {}).get("ssh") or {}
        auth_success = zeek_ssh.get("auth_success")
        if auth_success is None:
            auth_success = doc.get("zeek.ssh.auth_success")
        ssh_ver = zeek_ssh.get("version") or doc.get("zeek.ssh.version")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="ssh", severity="info",
            detection_source="zeek_ssh",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            src_port=int(p) if (p := (doc.get("source") or {}).get("port")) else None,
            dst_port=int(p) if (p := (doc.get("destination") or {}).get("port")) else None,
            ssh_auth_success=bool(auth_success) if auth_success is not None else None,
            ssh_version=int(ssh_ver) if ssh_ver is not None else None,
        )

    # ------------------------------------------------------------------
    # Phase 36-02: Zeek normalizers — lateral movement (smb/rdp/dce_rpc)
    # ------------------------------------------------------------------

    def _normalize_smb_mapping(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_smb = (doc.get("zeek") or {}).get("smb_mapping") or {}
        smb_path_val = zeek_smb.get("path") or doc.get("zeek.smb_mapping.path")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="smb_mapping", severity="info",
            detection_source="zeek_smb_mapping",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            smb_path=str(smb_path_val) if smb_path_val else None,
        )

    def _normalize_smb_files(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_smb = (doc.get("zeek") or {}).get("smb_files") or {}
        action = zeek_smb.get("action") or doc.get("zeek.smb_files.action")
        fname = zeek_smb.get("name") or doc.get("zeek.smb_files.name")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="smb_files", severity="info",
            detection_source="zeek_smb_files",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            smb_action=str(action) if action else None,
            smb_path=str(fname) if fname else None,
        )

    def _normalize_rdp(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_rdp = (doc.get("zeek") or {}).get("rdp") or {}
        cookie = zeek_rdp.get("cookie") or doc.get("zeek.rdp.cookie")
        sec_proto = zeek_rdp.get("security_protocol") or doc.get("zeek.rdp.security_protocol")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="rdp", severity="info",
            detection_source="zeek_rdp",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            src_port=int(p) if (p := (doc.get("source") or {}).get("port")) else None,
            dst_port=int(p) if (p := (doc.get("destination") or {}).get("port")) else None,
            rdp_cookie=str(cookie) if cookie else None,
            rdp_security_protocol=str(sec_proto) if sec_proto else None,
        )

    def _normalize_dce_rpc(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_rpc = (doc.get("zeek") or {}).get("dce_rpc") or {}
        endpoint = zeek_rpc.get("endpoint") or doc.get("zeek.dce_rpc.endpoint")
        operation = zeek_rpc.get("operation") or doc.get("zeek.dce_rpc.operation")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="dce_rpc", severity="info",
            detection_source="zeek_dce_rpc",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            file_path=f"{endpoint}/{operation}" if endpoint and operation else (endpoint or operation),
        )

    # ------------------------------------------------------------------
    # Phase 36-02: Zeek normalizers — infrastructure (dhcp/dns/software/known)
    # ------------------------------------------------------------------

    def _normalize_dhcp(self, doc: dict) -> NormalizedEvent | None:
        # DHCP may have src_ip 0.0.0.0 (broadcast) — use assigned_ip or client_addr as fallback
        src_ip = (
            (doc.get("source") or {}).get("ip")
            or (doc.get("zeek") or {}).get("dhcp", {}).get("client_addr")
            or doc.get("zeek.dhcp.client_addr")
            or "0.0.0.0"
        )
        zeek_dhcp = (doc.get("zeek") or {}).get("dhcp") or {}
        assigned = zeek_dhcp.get("assigned_ip") or doc.get("zeek.dhcp.assigned_ip")
        dhcp_host = zeek_dhcp.get("hostname") or doc.get("zeek.dhcp.hostname")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="dhcp", severity="info",
            detection_source="zeek_dhcp",
            hostname=str(dhcp_host) if dhcp_host else ((doc.get("observer") or {}).get("hostname") or "malcolm"),
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str(assigned) if assigned else None,
        )

    def _normalize_dns_zeek(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        dns_obj = doc.get("dns") or {}
        zeek_dns = (doc.get("zeek") or {}).get("dns") or {}
        query = (dns_obj.get("question") or {}).get("name") or zeek_dns.get("query") or doc.get("zeek.dns.query")
        qtype = (dns_obj.get("question") or {}).get("type") or zeek_dns.get("qtype_name")
        rcode = dns_obj.get("response_code") or zeek_dns.get("rcode_name")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="dns_query", severity="info",
            detection_source="zeek_dns",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            src_port=int(p) if (p := (doc.get("source") or {}).get("port")) else None,
            dst_port=int(p) if (p := (doc.get("destination") or {}).get("port")) else None,
            dns_query=str(query) if query else None,
            dns_query_type=str(qtype) if qtype else None,
            dns_rcode=str(rcode) if rcode else None,
            domain=str(query) if query else None,
        )

    def _normalize_software(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_sw = (doc.get("zeek") or {}).get("software") or {}
        sw_name = zeek_sw.get("name") or doc.get("zeek.software.name")
        sw_ver = zeek_sw.get("version") or doc.get("zeek.software.version")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="software", severity="info",
            detection_source="zeek_software",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            process_name=f"{sw_name}/{sw_ver}" if sw_name and sw_ver else sw_name,
        )

    def _normalize_known_host(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (
            (doc.get("source") or {}).get("ip")
            or doc.get("src_ip")
            or doc.get("zeek.known_hosts.host")
            or (doc.get("zeek") or {}).get("known_hosts", {}).get("host")
        )
        if not src_ip:
            return None
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="known_host", severity="info",
            detection_source="zeek_known_hosts",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
        )

    def _normalize_known_service(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (
            (doc.get("source") or {}).get("ip")
            or doc.get("src_ip")
            or (doc.get("zeek") or {}).get("known_services", {}).get("host")
        )
        if not src_ip:
            return None
        zeek_ks = (doc.get("zeek") or {}).get("known_services") or {}
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="known_service", severity="info",
            detection_source="zeek_known_services",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_port=int(p) if (p := zeek_ks.get("port_num") or doc.get("zeek.known_services.port_num")) else None,
            network_protocol=str(zeek_ks.get("port_proto") or "").lower() or None,
        )

    # ------------------------------------------------------------------
    # Phase 36-02: Zeek normalizers — application layer (sip/ftp/smtp/socks/tunnel/pe)
    # ------------------------------------------------------------------

    def _normalize_sip(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_sip = (doc.get("zeek") or {}).get("sip") or {}
        method = zeek_sip.get("method") or doc.get("zeek.sip.method")
        uri = zeek_sip.get("uri") or doc.get("zeek.sip.uri")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="sip", severity="info",
            detection_source="zeek_sip",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            http_method=str(method) if method else None,
            url=str(uri) if uri else None,
        )

    def _normalize_ftp(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_ftp = (doc.get("zeek") or {}).get("ftp") or {}
        cmd = zeek_ftp.get("command") or doc.get("zeek.ftp.command")
        reply = zeek_ftp.get("reply_code") or doc.get("zeek.ftp.reply_code")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="ftp", severity="info",
            detection_source="zeek_ftp",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            command_line=f"{cmd} ({reply})" if cmd else None,
            http_status_code=int(reply) if reply else None,
        )

    def _normalize_smtp(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_smtp = (doc.get("zeek") or {}).get("smtp") or {}
        smtp_from = zeek_smtp.get("from") or doc.get("zeek.smtp.from")
        smtp_subject = zeek_smtp.get("subject") or doc.get("zeek.smtp.subject")
        smtp_to_raw = zeek_smtp.get("to") or doc.get("zeek.smtp.to")
        smtp_to = json.dumps(smtp_to_raw) if isinstance(smtp_to_raw, list) else str(smtp_to_raw) if smtp_to_raw else None
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="smtp", severity="info",
            detection_source="zeek_smtp",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            username=str(smtp_from) if smtp_from else None,
            tags=smtp_to,
            file_path=str(smtp_subject) if smtp_subject else None,
        )

    def _normalize_socks(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="socks", severity="info",
            detection_source="zeek_socks",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
        )

    def _normalize_tunnel(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_tunnel = (doc.get("zeek") or {}).get("tunnel") or {}
        tunnel_type = zeek_tunnel.get("type") or doc.get("zeek.tunnel.type")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="tunnel", severity="info",
            detection_source="zeek_tunnel",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            dst_ip=str((doc.get("destination") or {}).get("ip") or "") or None,
            network_protocol=str(tunnel_type) if tunnel_type else None,
        )

    def _normalize_pe(self, doc: dict) -> NormalizedEvent | None:
        src_ip = (doc.get("source") or {}).get("ip") or doc.get("src_ip")
        if not src_ip:
            return None
        zeek_pe = (doc.get("zeek") or {}).get("pe") or {}
        is_packed = zeek_pe.get("is_packed") or doc.get("zeek.pe.is_packed")
        compile_ts = zeek_pe.get("compile_ts") or doc.get("zeek.pe.compile_ts")
        raw_ts = doc.get("@timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        sev = "high" if is_packed else "info"
        return NormalizedEvent(
            event_id=str(uuid4()), timestamp=ts, ingested_at=datetime.now(timezone.utc),
            source_type="zeek", event_type="pe", severity=sev,
            detection_source="zeek_pe",
            hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
            raw_event=json.dumps(doc)[:8192],
            src_ip=str(src_ip),
            tags=f"compile_ts:{compile_ts}" if compile_ts else None,
        )

    async def _poll_ubuntu_normalizer(self) -> list[NormalizedEvent]:
        """
        Poll Ubuntu normalization server for new NDJSON events.

        Returns [] immediately if UBUNTU_NORMALIZER_URL is empty (disabled).
        Tracks ingested line count via SQLite key "malcolm.ubuntu_normalized.last_line_count".
        Skips already-seen lines (file is append-only).
        """
        if not self._ubuntu_normalizer_url:
            return []  # Disabled — no Ubuntu box configured

        url = f"{self._ubuntu_normalizer_url}/normalized/latest"
        try:
            response = await asyncio.to_thread(
                lambda: httpx.get(url, timeout=10.0)
            )
            response.raise_for_status()
        except Exception as exc:
            log.warning("UbuntuNormalizer poll failed", url=url, error=str(exc))
            return []

        # Track line offset to avoid re-ingesting old lines
        last_count_str = await asyncio.to_thread(
            self._sqlite.get_kv, "malcolm.ubuntu_normalized.last_line_count"
        )
        last_count = int(last_count_str) if last_count_str else 0

        lines = response.text.splitlines()
        new_lines = lines[last_count:]
        if not new_lines:
            return []

        events: list[NormalizedEvent] = []
        for line in new_lines:
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                log.warning("UbuntuNormalizer: invalid NDJSON line", line=line[:100])
                continue
            # Map to NormalizedEvent — use _normalize_syslog for syslog, else build from doc
            source_type = doc.get("source_type", "ubuntu_normalized")
            if source_type == "ipfire_syslog":
                event = self._normalize_syslog(doc)
            else:
                # Generic EVE event — build NormalizedEvent directly from mapped fields
                raw_ts = doc.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = datetime.now(timezone.utc)
                event = NormalizedEvent(
                    event_id=str(uuid4()),
                    timestamp=ts,
                    ingested_at=datetime.now(timezone.utc),
                    source_type="ubuntu_normalized",
                    hostname=doc.get("hostname"),
                    event_type=doc.get("event_type"),
                    severity=doc.get("severity", "info"),
                    detection_source="ubuntu_normalizer",
                    raw_event=doc.get("raw_event", line[:8192]),
                    src_ip=doc.get("src_ip"),
                    dst_ip=doc.get("dst_ip"),
                    src_port=int(doc["src_port"]) if doc.get("src_port") else None,
                    dst_port=int(doc["dst_port"]) if doc.get("dst_port") else None,
                )
            if event is not None:
                events.append(event)

        # Advance cursor
        new_total = last_count + len(new_lines)
        await asyncio.to_thread(
            self._sqlite.set_kv, "malcolm.ubuntu_normalized.last_line_count", str(new_total)
        )
        return events

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

            # --- Zeek conn logs ---
            conn_hits = await self._fetch_index(
                "arkime_sessions3-*",
                "malcolm.zeek_conn.last_timestamp",
                event_type_filter="conn",
            )
            conn_batch = [e for h in conn_hits if (e := self._normalize_conn(h.get("_source", {})))]
            if conn_batch and self._loader:
                await self._loader.ingest_events(conn_batch)
                self._conn_ingested += len(conn_batch)

            # --- Zeek weird logs (always high severity) ---
            weird_hits = await self._fetch_index(
                "arkime_sessions3-*",
                "malcolm.zeek_weird.last_timestamp",
                event_type_filter="weird",
            )
            weird_batch = [e for h in weird_hits if (e := self._normalize_weird(h.get("_source", {})))]
            if weird_batch and self._loader:
                await self._loader.ingest_events(weird_batch)
                self._weird_ingested += len(weird_batch)

            # --- Phase 36-02: remaining 21 Zeek log types ---
            for log_type, cursor_suffix, normalizer_fn, counter_attr in [
                ("http",          "http",          self._normalize_http,          "_http_ingested"),
                ("ssl",           "ssl",           self._normalize_ssl,           "_ssl_ingested"),
                ("x509",          "x509",          self._normalize_x509,          "_x509_ingested"),
                ("files",         "files",         self._normalize_files,         "_files_ingested"),
                ("notice",        "notice",        self._normalize_notice,        "_notice_ingested"),
                ("kerberos",      "kerberos",      self._normalize_kerberos,      "_kerberos_ingested"),
                ("ntlm",          "ntlm",          self._normalize_ntlm,          "_ntlm_ingested"),
                ("ssh",           "ssh",           self._normalize_ssh,           "_ssh_ingested"),
                ("smb_mapping",   "smb_mapping",   self._normalize_smb_mapping,   "_smb_mapping_ingested"),
                ("smb_files",     "smb_files",     self._normalize_smb_files,     "_smb_files_ingested"),
                ("rdp",           "rdp",           self._normalize_rdp,           "_rdp_ingested"),
                ("dce_rpc",       "dce_rpc",       self._normalize_dce_rpc,       "_dce_rpc_ingested"),
                ("dhcp",          "dhcp",          self._normalize_dhcp,          "_dhcp_ingested"),
                ("dns",           "dns_zeek",      self._normalize_dns_zeek,      "_dns_zeek_ingested"),
                ("software",      "software",      self._normalize_software,      "_software_ingested"),
                ("known_host",    "known_hosts",   self._normalize_known_host,    "_known_host_ingested"),
                ("known_service", "known_services", self._normalize_known_service, "_known_service_ingested"),
                ("sip",           "sip",           self._normalize_sip,           "_sip_ingested"),
                ("ftp",           "ftp",           self._normalize_ftp,           "_ftp_ingested"),
                ("smtp",          "smtp",          self._normalize_smtp,          "_smtp_ingested"),
                ("socks",         "socks",         self._normalize_socks,         "_socks_ingested"),
                ("tunnel",        "tunnel",        self._normalize_tunnel,        "_tunnel_ingested"),
                ("pe",            "pe",            self._normalize_pe,            "_pe_ingested"),
            ]:
                hits = await self._fetch_index(
                    "arkime_sessions3-*",
                    f"malcolm.zeek_{cursor_suffix}.last_timestamp",
                    event_type_filter=log_type,
                )
                batch = [e for h in hits if (e := normalizer_fn(h.get("_source", {})))]
                if batch and self._loader:
                    await self._loader.ingest_events(batch)
                    setattr(self, counter_attr, getattr(self, counter_attr) + len(batch))

            # --- Ubuntu normalization pipeline ---
            ubuntu_events = await self._poll_ubuntu_normalizer()
            if ubuntu_events and self._loader is not None:
                await self._loader.ingest_events(ubuntu_events)
                self._ubuntu_ingested += len(ubuntu_events)

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
            "ubuntu_ingested": self._ubuntu_ingested,
            "conn_ingested": self._conn_ingested,
            "weird_ingested": self._weird_ingested,
            "http_ingested": self._http_ingested,
            "ssl_ingested": self._ssl_ingested,
            "x509_ingested": self._x509_ingested,
            "files_ingested": self._files_ingested,
            "notice_ingested": self._notice_ingested,
            "kerberos_ingested": self._kerberos_ingested,
            "ntlm_ingested": self._ntlm_ingested,
            "ssh_ingested": self._ssh_ingested,
            "smb_mapping_ingested": self._smb_mapping_ingested,
            "smb_files_ingested": self._smb_files_ingested,
            "rdp_ingested": self._rdp_ingested,
            "dce_rpc_ingested": self._dce_rpc_ingested,
            "dhcp_ingested": self._dhcp_ingested,
            "dns_zeek_ingested": self._dns_zeek_ingested,
            "software_ingested": self._software_ingested,
            "known_host_ingested": self._known_host_ingested,
            "known_service_ingested": self._known_service_ingested,
            "sip_ingested": self._sip_ingested,
            "ftp_ingested": self._ftp_ingested,
            "smtp_ingested": self._smtp_ingested,
            "socks_ingested": self._socks_ingested,
            "tunnel_ingested": self._tunnel_ingested,
            "pe_ingested": self._pe_ingested,
        }
