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

    def to_duckdb_row(self) -> tuple[Any, ...]:
        """Return a tuple of values matching the _INSERT_SQL column order in loader.py.

        Column order (35 elements total):
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

        NOTE: loader.py _INSERT_SQL uses positions 0-28 only until plan 20-02
        migrates the DuckDB schema to include the six new columns.
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
