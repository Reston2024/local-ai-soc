"""Pydantic models for the AI SOC Brain API.

Phase 2 additions:
  - IngestSource enum (fixture | syslog | vector | api)
  - NormalizedEvent.source — where the event originated
  - NormalizedEvent.enrichments — analyst-readable tags added by enricher
  - NormalizedEvent.user — optional username/account field

Phase 4 additions:
  - GraphNode extended with attributes, first_seen, last_seen, evidence fields
  - GraphEdge renamed source/target -> src/dst; added timestamp, evidence_event_ids
  - AttackPath — connected-component path with severity, temporal bounds
  - GraphResponse extended with attack_paths and stats fields

Phase 5 additions:
  - IngestSource.suricata — Suricata EVE JSON ingestion source
  - Alert.threat_score — additive 0-100 threat score (default 0)
  - Alert.attack_tags — list of MITRE ATT&CK tactic/technique dicts (default [])
"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class IngestSource(str, Enum):
    fixture = "fixture"
    syslog = "syslog"
    vector = "vector"
    api = "api"
    suricata = "suricata"


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
    type: str  # host|ip|domain|alert|process|user
    label: str
    attributes: dict = Field(default_factory=dict)
    first_seen: str = ""
    last_seen: str = ""
    evidence: list[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    id: str
    type: str  # dns_query|connection|alert_trigger|related_event|observed_on
    src: str
    dst: str
    timestamp: str = ""
    evidence_event_ids: list[str] = Field(default_factory=list)


class AttackPath(BaseModel):
    id: str
    node_ids: list[str]
    edge_ids: list[str]
    severity: str  # max alert severity; "info" if no alerts
    first_event: str
    last_event: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    attack_paths: list[AttackPath] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)


class Alert(BaseModel):
    id: str
    timestamp: str
    rule: str
    severity: str
    event_id: str
    description: str
    threat_score: int = 0
    attack_tags: list[dict] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    ingestion_sources: list[str] = Field(default_factory=list)
