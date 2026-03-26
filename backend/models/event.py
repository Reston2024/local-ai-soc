"""Normalized event model for the AI-SOC-Brain ingestion pipeline.

This module was reorganized in Phase 8 — this file re-establishes
the canonical NormalizedEvent that matches the DuckDB schema.
All ingestion parsers, API endpoints, and stores import from here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

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


class EventListResponse(BaseModel):
    """Paginated event list response for GET /api/events."""

    events: list[NormalizedEvent]
    total: int
    page: int
    page_size: int
    has_next: bool


__all__ = ["NormalizedEvent", "EventListResponse"]
