"""
Pydantic models for events, detections, and graph entities.

NormalizedEvent mirrors the normalized_events DuckDB table exactly.
All Optional fields map to nullable columns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Core event model
# ---------------------------------------------------------------------------


class NormalizedEvent(BaseModel):
    """
    A single normalized security event.

    Fields match the normalized_events DuckDB table column-for-column.
    Timestamps are stored as Python datetime objects; Pydantic coerces
    ISO-8601 strings automatically.
    """

    event_id: str = Field(description="Unique event identifier (UUID or source-derived)")
    timestamp: datetime = Field(description="Event timestamp (UTC preferred)")
    ingested_at: datetime = Field(description="Time this event was stored in DuckDB")
    source_type: Optional[str] = Field(None, description="evtx | json | csv | osquery | …")
    source_file: Optional[str] = Field(None, description="Original file path / name")

    # Host context
    hostname: Optional[str] = None
    username: Optional[str] = None

    # Process context
    process_name: Optional[str] = None
    process_id: Optional[int] = None
    parent_process_name: Optional[str] = None
    parent_process_id: Optional[int] = None

    # File context
    file_path: Optional[str] = None
    file_hash_sha256: Optional[str] = None
    command_line: Optional[str] = None

    # Network context
    src_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_ip: Optional[str] = None
    dst_port: Optional[int] = None
    domain: Optional[str] = None
    url: Optional[str] = None

    # Classification
    event_type: Optional[str] = Field(None, description="process_create | network_connect | …")
    severity: Optional[str] = Field(None, description="critical | high | medium | low | info")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    detection_source: Optional[str] = None
    attack_technique: Optional[str] = Field(None, description="MITRE ATT&CK technique ID")
    attack_tactic: Optional[str] = Field(None, description="MITRE ATT&CK tactic name")

    # Raw / metadata
    raw_event: Optional[str] = Field(None, description="Original JSON/XML as string")
    tags: Optional[str] = Field(None, description="Comma-separated tag list")
    case_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Embedding text generation
    # ------------------------------------------------------------------

    def to_embedding_text(self) -> str:
        """
        Produce a compact text representation suitable for vector embedding.

        The output is designed to capture the security-relevant signal in a
        form that the mxbai-embed-large model can encode into a meaningful
        retrieval vector.
        """
        parts: list[str] = []
        if self.event_type:
            parts.append(f"[{self.event_type}]")
        if self.hostname:
            parts.append(f"host:{self.hostname}")
        if self.username:
            parts.append(f"user:{self.username}")
        if self.process_name:
            parts.append(f"process:{self.process_name}")
        if self.command_line:
            parts.append(f"cmd:{self.command_line}")
        if self.file_path:
            parts.append(f"file:{self.file_path}")
        if self.dst_ip:
            parts.append(f"dst:{self.dst_ip}:{self.dst_port}")
        if self.domain:
            parts.append(f"domain:{self.domain}")
        if self.attack_technique:
            parts.append(f"technique:{self.attack_technique}")
        return " | ".join(parts)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_duckdb_row(self) -> tuple:
        """
        Return a tuple matching the column order of normalized_events.

        Used in parameterised INSERT statements.
        """
        return (
            self.event_id,
            self.timestamp,
            self.ingested_at,
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

    @classmethod
    def from_duckdb_row(cls, row: tuple, columns: list[str]) -> "NormalizedEvent":
        """Construct a NormalizedEvent from a DuckDB row + column list."""
        return cls(**dict(zip(columns, row)))


# ---------------------------------------------------------------------------
# Detection model
# ---------------------------------------------------------------------------


class DetectionRecord(BaseModel):
    """A correlated detection / alert produced by the detection engine."""

    id: str = Field(description="Unique detection ID")
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    severity: str = Field(description="critical | high | medium | low | informational")
    matched_event_ids: list[str] = Field(
        default_factory=list,
        description="event_id values from normalized_events that triggered this detection",
    )
    attack_technique: Optional[str] = None
    attack_tactic: Optional[str] = None
    explanation: Optional[str] = None
    case_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("severity")
    @classmethod
    def severity_must_be_valid(cls, v: str) -> str:
        valid = {"critical", "high", "medium", "low", "informational", "info"}
        if v.lower() not in valid:
            raise ValueError(f"severity must be one of {sorted(valid)}, got {v!r}")
        return v.lower()


# ---------------------------------------------------------------------------
# Graph models
# ---------------------------------------------------------------------------


class GraphEntity(BaseModel):
    """A node in the investigation graph."""

    id: str
    type: str = Field(
        description=(
            "host | user | process | file | network | domain | ip | "
            "detection | evidence | case | technique"
        )
    )
    name: str
    attributes: Optional[dict[str, Any]] = None
    case_id: Optional[str] = None
    created_at: Optional[datetime] = None


class GraphEdge(BaseModel):
    """A directed relationship between two graph entities."""

    id: Optional[int] = None
    source_type: str
    source_id: str
    edge_type: str = Field(
        description=(
            "spawned | wrote | read | connected_to | resolved | "
            "triggered | belongs_to | related_to"
        )
    )
    target_type: str
    target_id: str
    properties: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None


class GraphResponse(BaseModel):
    """Response payload for graph API endpoints."""

    entities: list[GraphEntity] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    root_entity_id: Optional[str] = None
    depth: Optional[int] = None
    total_entities: int = 0
    total_edges: int = 0

    @classmethod
    def from_stores(
        cls,
        entities: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        root_entity_id: Optional[str] = None,
        depth: Optional[int] = None,
    ) -> "GraphResponse":
        """Build a GraphResponse from raw store dictionaries."""
        entity_models = [GraphEntity(**e) for e in entities]
        edge_models = [GraphEdge(**e) for e in edges]
        return cls(
            entities=entity_models,
            edges=edge_models,
            root_entity_id=root_entity_id,
            depth=depth,
            total_entities=len(entity_models),
            total_edges=len(edge_models),
        )


# ---------------------------------------------------------------------------
# API request / response helpers
# ---------------------------------------------------------------------------


class EventListResponse(BaseModel):
    """Paginated list of events."""

    events: list[NormalizedEvent]
    total: int
    page: int
    page_size: int
    has_next: bool


class EventSearchRequest(BaseModel):
    """Full-text search request body."""

    query: str = Field(min_length=1, max_length=1000)
    case_id: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
