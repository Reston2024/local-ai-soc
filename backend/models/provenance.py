"""Pydantic response models for evidence provenance records.

Each class maps directly to its corresponding SQLite table schema defined
in Phase 21. Fields use str / Optional[str] / list[str] only — no complex
types — so serialization to/from the DB is trivial.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class IngestProvenanceRecord(BaseModel):
    """Provenance record for a single ingested event (ingest_provenance table)."""

    prov_id: str
    event_id: str
    raw_sha256: str          # 64-char hex SHA-256 of the raw event bytes
    source_file: str
    parser_name: str
    parser_version: Optional[str] = None
    operator_id: Optional[str] = None
    ingested_at: str         # ISO-8601 UTC timestamp


class DetectionProvenanceRecord(BaseModel):
    """Provenance record for a Sigma rule detection hit (detection_provenance table)."""

    prov_id: str
    detection_id: str
    rule_id: str
    rule_title: str
    rule_sha256: str         # 64-char hex SHA-256 of the .yml rule file bytes
    pysigma_version: str
    field_map_version: str
    operator_id: Optional[str] = None
    detected_at: str         # ISO-8601 UTC timestamp


class LlmProvenanceRecord(BaseModel):
    """Provenance record for a single LLM call (llm_audit_provenance table)."""

    audit_id: str
    model_id: str
    prompt_template_name: str
    prompt_template_sha256: str   # 64-char hex SHA-256 of the prompt template text
    response_sha256: str          # 64-char hex SHA-256 of the raw LLM response text
    operator_id: Optional[str] = None
    grounding_event_ids: list[str]
    created_at: str               # ISO-8601 UTC timestamp


class PlaybookProvenanceRecord(BaseModel):
    """Provenance record for a playbook run (playbook_run_provenance table)."""

    prov_id: str
    run_id: str
    playbook_id: str
    playbook_file_sha256: str     # 64-char hex SHA-256 of the playbook YAML bytes
    playbook_version: str
    trigger_event_ids: list[str]
    operator_id_who_approved: Optional[str] = None
    created_at: str               # ISO-8601 UTC timestamp
