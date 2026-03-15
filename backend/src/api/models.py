from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

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
