"""
Pydantic models for the recommendation artifact lifecycle (Phase 24).

Governed by ADR-030. Canonical schema: contracts/recommendation.schema.json v1.0.0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

import jsonschema
from pydantic import BaseModel, ConfigDict, Field, model_validator

# Load and pin the JSON Schema at import time — fail fast if file missing.
_SCHEMA_PATH = (
    Path(__file__).parent.parent.parent / "contracts" / "recommendation.schema.json"
)
_SCHEMA: dict = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Nested sub-models
# ---------------------------------------------------------------------------


class PromptInspection(BaseModel):
    """Structured prompt injection inspection record (ADR-030 §3)."""

    model_config = ConfigDict(from_attributes=True)

    method: str = Field(min_length=1)
    passed: bool
    flagged_patterns: list[str] = Field(default_factory=list)
    audit_log_id: str  # UUID v4 as string


class RetrievalSources(BaseModel):
    """RAG retrieval audit record."""

    model_config = ConfigDict(from_attributes=True)

    count: int = Field(ge=0)
    ids: list[str] = Field(default_factory=list)


class OverrideLog(BaseModel):
    """Required when inference_confidence is low/none or prompt_inspection.passed is false (ADR-030 §4)."""

    model_config = ConfigDict(from_attributes=True)

    approved_at: str  # ISO-8601 date-time
    approval_basis: str = Field(min_length=1)
    modified_fields: list[str] = Field(default_factory=list)
    operator_note: str = ""


# ---------------------------------------------------------------------------
# Primary artifact model
# ---------------------------------------------------------------------------


class RecommendationArtifact(BaseModel):
    """
    Versioned, immutable recommendation artifact.

    Enforces the full JSON Schema (contracts/recommendation.schema.json v1.0.0)
    including allOf cross-field constraints via model_validator.
    """

    model_config = ConfigDict(from_attributes=True)

    schema_version: Literal["1.0.0"] = "1.0.0"
    recommendation_id: str           # UUID v4
    case_id: str                     # UUID v4
    type: Literal[
        "network_control_change",
        "alert_suppression",
        "asset_isolation",
        "no_action",
    ]
    proposed_action: str = Field(min_length=1)
    target: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    rationale: list[str] = Field(min_length=1)
    evidence_event_ids: list[str] = Field(min_length=1)
    retrieval_sources: RetrievalSources
    inference_confidence: Literal["high", "medium", "low", "none"]
    model_id: str = Field(min_length=1)
    model_run_id: str
    prompt_inspection: PromptInspection
    generated_at: str                # ISO-8601 date-time
    analyst_approved: bool = False
    approved_by: str = ""
    override_log: Optional[OverrideLog] = None
    expires_at: str                  # ISO-8601 date-time

    @model_validator(mode="after")
    def validate_against_json_schema(self) -> "RecommendationArtifact":
        """
        Full JSON Schema Draft 2020-12 validation against contracts/recommendation.schema.json.

        Uses exclude_none=True to omit optional None fields — prevents false positives
        from jsonschema additionalProperties=false seeing null keys (Research pitfall 3).
        """
        data = self.model_dump(mode="json", exclude_none=True)
        try:
            jsonschema.validate(instance=data, schema=_SCHEMA)
        except jsonschema.ValidationError as exc:
            raise ValueError(f"JSON Schema validation failed: {exc.message}") from exc
        return self


# ---------------------------------------------------------------------------
# Request / response helpers (used by API routes)
# ---------------------------------------------------------------------------


class RecommendationCreate(BaseModel):
    """Request body for POST /api/recommendations. Creates a draft artifact."""

    model_config = ConfigDict(from_attributes=True)

    case_id: str
    type: Literal[
        "network_control_change",
        "alert_suppression",
        "asset_isolation",
        "no_action",
    ]
    proposed_action: str = Field(min_length=1)
    target: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    rationale: list[str] = Field(min_length=1)
    evidence_event_ids: list[str] = Field(min_length=1)
    retrieval_sources: RetrievalSources
    inference_confidence: Literal["high", "medium", "low", "none"]
    model_id: str = Field(min_length=1)
    model_run_id: str
    prompt_inspection: PromptInspection
    generated_at: str
    expires_at: str


class ApproveRequest(BaseModel):
    """Request body for PATCH /api/recommendations/{id}/approve."""

    model_config = ConfigDict(from_attributes=True)

    approved_by: str
    override_log: Optional[OverrideLog] = None
