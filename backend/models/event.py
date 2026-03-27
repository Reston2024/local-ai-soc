"""Normalized event model for the AI-SOC-Brain ingestion pipeline.

This module was reorganized in Phase 8 — this file re-establishes
the canonical NormalizedEvent that matches the DuckDB schema.
All ingestion parsers, API endpoints, and stores import from here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Union

from pydantic import BaseModel, Field


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

    def to_duckdb_row(self) -> tuple[Any, ...]:
        """Return a tuple of values matching the _INSERT_SQL column order in loader.py.

        Column order:
            event_id, timestamp, ingested_at, source_type, source_file,
            hostname, username, process_name, process_id,
            parent_process_name, parent_process_id,
            file_path, file_hash_sha256, command_line,
            src_ip, src_port, dst_ip, dst_port, domain, url,
            event_type, severity, confidence, detection_source,
            attack_technique, attack_tactic,
            raw_event, tags, case_id
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
    "DetectionRecord",
    "EventListResponse",
    "GraphEntity",
    "GraphEdge",
    "GraphResponse",
]
