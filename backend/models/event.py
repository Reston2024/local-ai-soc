"""Normalized event model for the AI-SOC-Brain ingestion pipeline.

This module was reorganized in Phase 8 — this file re-establishes
the canonical NormalizedEvent that matches the DuckDB schema.
All ingestion parsers, API endpoints, and stores import from here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Union

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# OCSF class_uid lookup — maps event_type strings to OCSF integer class UIDs.
# Reference: Open Cybersecurity Schema Framework v1.1
# ---------------------------------------------------------------------------
OCSF_CLASS_UID_MAP: dict[str, int] = {
    # Process Activity (1007)
    "process_create": 1007,
    "process_terminate": 1007,
    "process_access": 1007,
    # File System Activity (1001)
    "file_create": 1001,
    "file_delete": 1001,
    "file_create_stream_hash": 1001,
    "file_creation_time_changed": 1001,
    "file_delete_detected": 1001,
    # Registry Activity (1001 — mapped to File System Activity per OCSF v1)
    "registry_event": 1001,
    "registry_value_set": 1001,
    # Network Activity (4001)
    "network_connect": 4001,
    # DNS Activity (4003)
    "dns_query": 4003,
    # Authentication (3002)
    "logon_success": 3002,
    "logon_failure": 3002,
    "logoff": 3002,
    "logon_event": 3002,
    "explicit_credential_logon": 3002,
    "kerberos_tgs_request": 3002,
    "kerberos_service_ticket": 3002,
    "ntlm_auth": 3002,
    # Module Activity (1005)
    "driver_load": 1005,
    "image_load": 1005,
    # Scheduled Job Activity (1006)
    "scheduled_task_created": 1006,
    # Account Change (3001)
    "user_account_created": 3001,
    "user_account_deleted": 3001,
    # WMI Activity (1009)
    "wmi_event": 1009,
    "wmi_consumer": 1009,
    "wmi_subscription": 1009,
    # Network Activity (4001) — EVE telemetry types added Phase 31
    "tls": 4001,
    "anomaly": 4001,
    # File System Activity (1001) — EVE fileinfo
    "file_transfer": 1001,
    # dns_query: 4003 already present above
    # Zeek telemetry types added Phase 36
    "conn":              4001,
    "http":              4002,
    "ssl":               4001,
    "x509":              4001,
    "files":             1001,
    "notice":            2001,
    "weird":             2001,
    "ssh":               3002,
    "smb_mapping":       4001,
    "smb_files":         1001,
    "rdp":               3002,
    "dce_rpc":           4001,
    "dhcp":              4001,
    "software":          5001,
    "known_host":        5001,
    "known_service":     5001,
    "intel":             2001,
    "sip":               4001,
    "ftp":               4001,
    "smtp":              4002,
    "socks":             4001,
    "tunnel":            4001,
    "pe":                1001,
}


class NormalizedEvent(BaseModel):
    """A normalized security event matching the DuckDB normalized_events schema."""

    event_id: str
    timestamp: Union[datetime, str]
    ingested_at: Union[datetime, str]
    source_type: Optional[str] = None
    source_file: Optional[str] = None
    hostname: Optional[str] = None
    username: Optional[str] = None
    process_name: Optional[str] = None
    process_id: Optional[int] = None
    parent_process_name: Optional[str] = None
    parent_process_id: Optional[int] = None
    file_path: Optional[str] = None
    file_hash_sha256: Optional[str] = None
    command_line: Optional[str] = None
    src_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_ip: Optional[str] = None
    dst_port: Optional[int] = None
    domain: Optional[str] = None
    url: Optional[str] = None
    event_type: Optional[str] = None
    severity: Optional[str] = "info"
    confidence: Optional[float] = None
    detection_source: Optional[str] = None
    attack_technique: Optional[str] = None
    attack_tactic: Optional[str] = None
    raw_event: Optional[str] = None
    tags: Optional[str] = None
    case_id: Optional[str] = None
    # ECS-aligned fields added in Phase 20 (plan 20-01).
    # These are appended at the END of to_duckdb_row() (positions 29-34)
    # so that the existing 29-column INSERT in loader.py is unaffected
    # until plan 20-02 migrates the DuckDB schema.
    ocsf_class_uid: Optional[int] = None
    event_outcome: Optional[str] = None
    user_domain: Optional[str] = None
    process_executable: Optional[str] = None
    network_protocol: Optional[str] = None
    network_direction: Optional[str] = None
    # Phase 31: EVE protocol telemetry fields (positions 35-54 in to_duckdb_row)
    # DNS fields
    dns_query: Optional[str] = None
    dns_query_type: Optional[str] = None
    dns_rcode: Optional[str] = None
    dns_answers: Optional[str] = None      # JSON-encoded list of answer IPs
    dns_ttl: Optional[int] = None
    # TLS fields
    tls_version: Optional[str] = None
    tls_ja3: Optional[str] = None
    tls_ja3s: Optional[str] = None
    tls_sni: Optional[str] = None
    tls_cipher: Optional[str] = None
    tls_cert_subject: Optional[str] = None
    tls_validation_status: Optional[str] = None
    # File fields
    file_md5: Optional[str] = None
    file_sha256_eve: Optional[str] = None
    file_mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    # HTTP fields
    http_method: Optional[str] = None
    http_uri: Optional[str] = None
    http_status_code: Optional[int] = None
    http_user_agent: Optional[str] = None
    # Phase 33: IOC matching fields
    ioc_matched: Optional[bool] = False
    ioc_confidence: Optional[int] = None
    ioc_actor_tag: Optional[str] = None
    # Phase 36: Zeek full telemetry fields (positions 58-74 in to_duckdb_row)
    conn_state: Optional[str] = None            # [58] zeek.conn.state
    conn_duration: Optional[float] = None       # [59] event.duration / network.duration
    conn_orig_bytes: Optional[int] = None       # [60] source.bytes (originator)
    conn_resp_bytes: Optional[int] = None       # [61] destination.bytes (responder)
    zeek_notice_note: Optional[str] = None      # [62] zeek.notice.note
    zeek_notice_msg: Optional[str] = None       # [63] zeek.notice.msg
    zeek_weird_name: Optional[str] = None       # [64] zeek.weird.name
    ssh_auth_success: Optional[bool] = None     # [65] zeek.ssh.auth_success
    ssh_version: Optional[int] = None           # [66] zeek.ssh.version
    kerberos_client: Optional[str] = None       # [67] zeek.kerberos.client
    kerberos_service: Optional[str] = None      # [68] zeek.kerberos.service
    ntlm_domain: Optional[str] = None           # [69] zeek.ntlm.domain
    ntlm_username: Optional[str] = None         # [70] zeek.ntlm.username
    smb_path: Optional[str] = None              # [71] zeek.smb_mapping.path
    smb_action: Optional[str] = None            # [72] zeek.smb_files.action
    rdp_cookie: Optional[str] = None            # [73] zeek.rdp.cookie
    rdp_security_protocol: Optional[str] = None # [74] zeek.rdp.security_protocol
    # Phase 42: Online anomaly scoring (River HalfSpaceTrees)
    anomaly_score: Optional[float] = None       # [75] float in [0.0, 1.0] or None
    # Phase 53: Privacy monitoring — extended HTTP fields
    http_referrer: Optional[str] = None          # [76] Referer header value
    http_request_body_len: Optional[int] = None  # [77] zeek.http.request_body_len
    http_response_body_len: Optional[int] = None # [78] zeek.http.response_body_len
    http_resp_mime_type: Optional[str] = None    # [79] zeek.http.resp_mime_types[0]

    def to_duckdb_row(self) -> tuple[Any, ...]:
        """Return a tuple of values matching the _INSERT_SQL column order in loader.py.

        Column order (79 elements total):
            [0]  event_id
            [1]  timestamp
            [2]  ingested_at
            [3]  source_type
            [4]  source_file
            [5]  hostname
            [6]  username
            [7]  process_name
            [8]  process_id
            [9]  parent_process_name
            [10] parent_process_id
            [11] file_path
            [12] file_hash_sha256
            [13] command_line
            [14] src_ip
            [15] src_port
            [16] dst_ip
            [17] dst_port
            [18] domain
            [19] url
            [20] event_type
            [21] severity
            [22] confidence
            [23] detection_source
            [24] attack_technique
            [25] attack_tactic
            [26] raw_event
            [27] tags
            [28] case_id
            --- ECS / OCSF fields added in plan 20-01 ---
            [29] ocsf_class_uid
            [30] event_outcome
            [31] user_domain
            [32] process_executable
            [33] network_protocol
            [34] network_direction
            --- Phase 31: EVE protocol fields ---
            [35] dns_query
            [36] dns_query_type
            [37] dns_rcode
            [38] dns_answers
            [39] dns_ttl
            [40] tls_version
            [41] tls_ja3
            [42] tls_ja3s
            [43] tls_sni
            [44] tls_cipher
            [45] tls_cert_subject
            [46] tls_validation_status
            [47] file_md5
            [48] file_sha256_eve
            [49] file_mime_type
            [50] file_size_bytes
            [51] http_method
            [52] http_uri
            [53] http_status_code
            [54] http_user_agent
            --- Phase 33: IOC matching fields ---
            [55] ioc_matched
            [56] ioc_confidence
            [57] ioc_actor_tag
            --- Phase 36: Zeek full telemetry fields ---
            [58] conn_state
            [59] conn_duration
            [60] conn_orig_bytes
            [61] conn_resp_bytes
            [62] zeek_notice_note
            [63] zeek_notice_msg
            [64] zeek_weird_name
            [65] ssh_auth_success
            [66] ssh_version
            [67] kerberos_client
            [68] kerberos_service
            [69] ntlm_domain
            [70] ntlm_username
            [71] smb_path
            [72] smb_action
            [73] rdp_cookie
            [74] rdp_security_protocol
            --- Phase 42: anomaly scoring ---
            [75] anomaly_score
            --- Phase 53: extended HTTP fields ---
            [76] http_referrer
            [77] http_request_body_len
            [78] http_response_body_len
            [79] http_resp_mime_type
        """
        def _ts(v: Union[datetime, str, None]) -> Optional[str]:
            if v is None:
                return None
            if hasattr(v, "isoformat"):
                return v.isoformat()
            return str(v)

        return (
            self.event_id,
            _ts(self.timestamp),
            _ts(self.ingested_at),
            self.source_type,
            self.source_file,
            self.hostname,
            self.username,
            self.process_name,
            self.process_id,
            self.parent_process_name,
            self.parent_process_id,
            self.file_path,
            self.file_hash_sha256,
            self.command_line,
            self.src_ip,
            self.src_port,
            self.dst_ip,
            self.dst_port,
            self.domain,
            self.url,
            self.event_type,
            self.severity,
            self.confidence,
            self.detection_source,
            self.attack_technique,
            self.attack_tactic,
            self.raw_event,
            self.tags,
            self.case_id,
            self.ocsf_class_uid,
            self.event_outcome,
            self.user_domain,
            self.process_executable,
            self.network_protocol,
            self.network_direction,
            # Phase 31: EVE protocol fields (positions 35-54)
            self.dns_query,
            self.dns_query_type,
            self.dns_rcode,
            self.dns_answers,
            self.dns_ttl,
            self.tls_version,
            self.tls_ja3,
            self.tls_ja3s,
            self.tls_sni,
            self.tls_cipher,
            self.tls_cert_subject,
            self.tls_validation_status,
            self.file_md5,
            self.file_sha256_eve,
            self.file_mime_type,
            self.file_size_bytes,
            self.http_method,
            self.http_uri,
            self.http_status_code,
            self.http_user_agent,
            # Phase 33: IOC matching fields (positions 55-57)
            self.ioc_matched if self.ioc_matched is not None else False,
            self.ioc_confidence,
            self.ioc_actor_tag,
            # Phase 36: Zeek full telemetry fields (positions 58-74)
            self.conn_state,
            self.conn_duration,
            self.conn_orig_bytes,
            self.conn_resp_bytes,
            self.zeek_notice_note,
            self.zeek_notice_msg,
            self.zeek_weird_name,
            self.ssh_auth_success,
            self.ssh_version,
            self.kerberos_client,
            self.kerberos_service,
            self.ntlm_domain,
            self.ntlm_username,
            self.smb_path,
            self.smb_action,
            self.rdp_cookie,
            self.rdp_security_protocol,
            # Phase 42: anomaly scoring (position 75)
            self.anomaly_score,
            # Phase 53: extended HTTP fields (positions 76-79)
            self.http_referrer,
            self.http_request_body_len,
            self.http_response_body_len,
            self.http_resp_mime_type,
        )

    def to_embedding_text(self) -> str:
        """Build a plain-text representation suitable for vector embedding."""
        parts: list[str] = []
        if self.hostname:
            parts.append(f"host:{self.hostname}")
        if self.username:
            parts.append(f"user:{self.username}")
        if self.process_name:
            parts.append(f"process:{self.process_name}")
        if self.command_line:
            parts.append(f"cmd:{self.command_line[:256]}")
        if self.event_type:
            parts.append(f"type:{self.event_type}")
        if self.severity:
            parts.append(f"severity:{self.severity}")
        if self.dst_ip:
            parts.append(f"dst:{self.dst_ip}")
        if self.attack_technique:
            parts.append(f"technique:{self.attack_technique}")
        return " ".join(parts)


class DetectionRecord(BaseModel):
    """A detection produced by the Sigma rule matcher."""

    id: str
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    severity: str = "medium"
    matched_event_ids: list[str] = Field(default_factory=list)
    attack_technique: Optional[str] = None
    attack_tactic: Optional[str] = None
    explanation: Optional[str] = None
    case_id: Optional[str] = None
    created_at: Optional[datetime] = None
    entity_key: Optional[str] = None  # Phase 43: correlation engine dedup key (e.g. src_ip)


class EventListResponse(BaseModel):
    """Paginated event list response for GET /api/events."""

    events: list[NormalizedEvent]
    total: int
    page: int
    page_size: int
    has_next: bool


class GraphEntity(BaseModel):
    """An entity node in the investigation graph (host, user, process, etc.)."""

    id: str
    type: str
    label: str = ""
    attributes: dict = Field(default_factory=dict)
    first_seen: str = ""
    last_seen: str = ""
    evidence: list[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    """A directed relationship edge between two graph entities."""

    id: str
    type: str
    src: str
    dst: str
    timestamp: str = ""
    evidence_event_ids: list[str] = Field(default_factory=list)


class GraphResponse(BaseModel):
    """Response model for graph traversal and case-graph endpoints."""

    entities: list[GraphEntity] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    total_entities: int = 0
    total_edges: int = 0

    @classmethod
    def from_stores(
        cls,
        entities: list[dict],
        edges: list[dict],
        root_entity_id: Optional[str] = None,
        depth: Optional[int] = None,
    ) -> "GraphResponse":
        """Build a GraphResponse from raw dicts returned by the SQLite store."""
        entity_objs = [
            GraphEntity(
                id=e.get("id", ""),
                type=e.get("entity_type", e.get("type", "")),
                label=e.get("entity_name", e.get("label", e.get("id", ""))),
                attributes=e.get("attributes", {}),
                first_seen=str(e.get("first_seen", "")),
                last_seen=str(e.get("last_seen", "")),
                evidence=e.get("evidence", []),
            )
            for e in entities
        ]
        edge_objs = [
            GraphEdge(
                id=ed.get("id", ""),
                type=ed.get("edge_type", ed.get("type", "")),
                src=ed.get("source_id", ed.get("src", "")),
                dst=ed.get("target_id", ed.get("dst", "")),
                timestamp=str(ed.get("timestamp", "")),
                evidence_event_ids=ed.get("evidence_event_ids", []),
            )
            for ed in edges
        ]
        return cls(
            entities=entity_objs,
            edges=edge_objs,
            total_entities=len(entity_objs),
            total_edges=len(edge_objs),
        )


__all__ = [
    "NormalizedEvent",
    "OCSF_CLASS_UID_MAP",
    "DetectionRecord",
    "EventListResponse",
    "GraphEntity",
    "GraphEdge",
    "GraphResponse",
]
