"""Pydantic models for the AI SOC Brain API.

Phase 2 additions:
  - IngestSource enum (fixture | syslog | vector | api)
  - NormalizedEvent.source — where the event originated
  - NormalizedEvent.enrichments — analyst-readable tags added by enricher
  - NormalizedEvent.user — optional username/account field
"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class IngestSource(str, Enum):
    fixture = "fixture"
    syslog = "syslog"
    vector = "vector"
    api = "api"


class NormalizedEvent(BaseModel):
    id: str
    timestamp: str
    host: str
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    event_type: str
    query: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    severity: str = "info"
    # Phase 2 additions
    source: IngestSource = IngestSource.api
    enrichments: list[str] = Field(default_factory=list)
    user: Optional[str] = None
    raw: dict = Field(default_factory=dict)


class GraphNode(BaseModel):
    id: str
    type: str  # host | ip | alert
    label: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Alert(BaseModel):
    id: str
    timestamp: str
    rule: str
    severity: str
    event_id: str
    description: str


class HealthResponse(BaseModel):
    status: str
    ingestion_sources: list[str] = Field(default_factory=list)
