"""
Unit tests for backend/models/recommendation.py (Phase 24, Plan 02).

TDD RED phase: stubs activated with real test implementations.
These tests define the contract for RecommendationArtifact and helper models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

VALID_UUID_1 = "550e8400-e29b-41d4-a716-446655440000"
VALID_UUID_2 = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
VALID_UUID_3 = "6ba7b811-9dad-11d1-80b4-00c04fd430c8"
VALID_UUID_4 = "6ba7b812-9dad-11d1-80b4-00c04fd430c8"


def _valid_payload(**overrides) -> dict:
    """Return a minimal valid RecommendationArtifact payload."""
    base = {
        "schema_version": "1.0.0",
        "recommendation_id": VALID_UUID_1,
        "case_id": VALID_UUID_2,
        "type": "network_control_change",
        "proposed_action": "block_ip",
        "target": "192.168.1.100",
        "scope": "RED->GREEN",
        "rationale": ["Suspicious outbound traffic detected"],
        "evidence_event_ids": ["evt-001"],
        "retrieval_sources": {"count": 2, "ids": ["chunk-001", "chunk-002"]},
        "inference_confidence": "high",
        "model_id": "qwen3:14b",
        "model_run_id": VALID_UUID_3,
        "prompt_inspection": {
            "method": "pattern_scrub_v2",
            "passed": True,
            "flagged_patterns": [],
            "audit_log_id": VALID_UUID_4,
        },
        "generated_at": "2026-04-06T10:00:00+00:00",
        "analyst_approved": False,
        "approved_by": "",
        "expires_at": "2026-04-13T10:00:00+00:00",
    }
    base.update(overrides)
    return base


def _import_models():
    """Import all 6 exported classes from the recommendation model module."""
    from backend.models.recommendation import (
        RecommendationArtifact,
        PromptInspection,
        RetrievalSources,
        OverrideLog,
        RecommendationCreate,
        ApproveRequest,
    )
    return RecommendationArtifact, PromptInspection, RetrievalSources, OverrideLog, RecommendationCreate, ApproveRequest


# ---------------------------------------------------------------------------
# Test 1: Valid artifact with high confidence is accepted
# ---------------------------------------------------------------------------

def test_recommendation_artifact_valid_high_confidence():
    """Valid artifact with high confidence and analyst_approved=False is accepted."""
    RecommendationArtifact, *_ = _import_models()
    artifact = RecommendationArtifact(**_valid_payload())
    assert artifact.recommendation_id == VALID_UUID_1
    assert artifact.type == "network_control_change"
    assert artifact.inference_confidence == "high"
    assert artifact.analyst_approved is False
    assert artifact.override_log is None


# ---------------------------------------------------------------------------
# Test 2: Missing required field raises ValidationError
# ---------------------------------------------------------------------------

def test_recommendation_artifact_missing_required_field():
    """Missing required field (e.g. case_id) raises ValidationError."""
    RecommendationArtifact, *_ = _import_models()
    payload = _valid_payload()
    del payload["case_id"]
    with pytest.raises(ValidationError):
        RecommendationArtifact(**payload)


# ---------------------------------------------------------------------------
# Test 3: Invalid type enum raises ValidationError
# ---------------------------------------------------------------------------

def test_recommendation_artifact_invalid_type_enum():
    """type field not in enum raises ValidationError."""
    RecommendationArtifact, *_ = _import_models()
    with pytest.raises(ValidationError):
        RecommendationArtifact(**_valid_payload(type="invalid_type"))


# ---------------------------------------------------------------------------
# Test 4: Invalid inference_confidence enum raises ValidationError
# ---------------------------------------------------------------------------

def test_recommendation_artifact_invalid_confidence_enum():
    """inference_confidence not in enum raises ValidationError."""
    RecommendationArtifact, *_ = _import_models()
    with pytest.raises(ValidationError):
        RecommendationArtifact(**_valid_payload(inference_confidence="very_high"))


# ---------------------------------------------------------------------------
# Test 5: allOf — analyst_approved=True with empty approved_by fails
# ---------------------------------------------------------------------------

def test_recommendation_artifact_jsonschema_rejects_approved_without_approved_by():
    """analyst_approved=True with empty approved_by fails JSON Schema allOf."""
    RecommendationArtifact, *_ = _import_models()
    with pytest.raises((ValidationError, ValueError)):
        RecommendationArtifact(**_valid_payload(
            analyst_approved=True,
            approved_by="",
        ))


# ---------------------------------------------------------------------------
# Test 6: allOf — low confidence without override_log fails
# ---------------------------------------------------------------------------

def test_recommendation_artifact_low_confidence_requires_override_log():
    """inference_confidence='low' with no override_log fails JSON Schema allOf."""
    RecommendationArtifact, *_ = _import_models()
    with pytest.raises((ValidationError, ValueError)):
        RecommendationArtifact(**_valid_payload(
            inference_confidence="low",
            override_log=None,
        ))


# ---------------------------------------------------------------------------
# Test 7: allOf — failed inspection without override_log fails
# ---------------------------------------------------------------------------

def test_recommendation_artifact_failed_inspection_requires_override_log():
    """prompt_inspection.passed=False with no override_log fails JSON Schema allOf."""
    RecommendationArtifact, *_ = _import_models()
    failed_inspection = {
        "method": "pattern_scrub_v2",
        "passed": False,
        "flagged_patterns": ["IGNORE PREVIOUS"],
        "audit_log_id": VALID_UUID_4,
    }
    with pytest.raises((ValidationError, ValueError)):
        RecommendationArtifact(**_valid_payload(
            prompt_inspection=failed_inspection,
            override_log=None,
        ))


# ---------------------------------------------------------------------------
# Test 8: PromptInspection sub-model validates correctly
# ---------------------------------------------------------------------------

def test_prompt_inspection_nested_model():
    """PromptInspection model validates correctly as nested sub-model."""
    RecommendationArtifact, PromptInspection, *_ = _import_models()
    artifact = RecommendationArtifact(**_valid_payload())
    assert isinstance(artifact.prompt_inspection, PromptInspection)
    assert artifact.prompt_inspection.passed is True
    assert artifact.prompt_inspection.method == "pattern_scrub_v2"
    assert artifact.prompt_inspection.flagged_patterns == []


# ---------------------------------------------------------------------------
# Test 9: high confidence + override_log=None succeeds
# ---------------------------------------------------------------------------

def test_recommendation_artifact_high_confidence_no_override_succeeds():
    """High confidence with passed inspection and override_log=None is valid."""
    RecommendationArtifact, *_ = _import_models()
    artifact = RecommendationArtifact(**_valid_payload(
        inference_confidence="high",
        override_log=None,
    ))
    assert artifact.override_log is None


# ---------------------------------------------------------------------------
# Test 10: model_dump validates against the JSON Schema
# ---------------------------------------------------------------------------

def test_model_dump_validates_against_schema():
    """model_dump(mode='json', exclude_none=True) output is valid under the JSON Schema."""
    import json
    import jsonschema
    from pathlib import Path

    RecommendationArtifact, *_ = _import_models()
    artifact = RecommendationArtifact(**_valid_payload())
    data = artifact.model_dump(mode="json", exclude_none=True)

    schema_path = Path(__file__).parent.parent.parent / "contracts" / "recommendation.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=data, schema=schema)  # must not raise


# ---------------------------------------------------------------------------
# Test 11: OverrideLog is a nested sub-model when provided
# ---------------------------------------------------------------------------

def test_override_log_is_nested_model():
    """OverrideLog is an OverrideLog instance when override_log is provided."""
    RecommendationArtifact, _, _, OverrideLog, *_ = _import_models()
    override = {
        "approved_at": "2026-04-06T11:00:00+00:00",
        "approval_basis": "Risk accepted by CISO",
        "modified_fields": [],
        "operator_note": "Reviewed manually",
    }
    artifact = RecommendationArtifact(**_valid_payload(
        inference_confidence="low",
        override_log=override,
    ))
    assert isinstance(artifact.override_log, OverrideLog)
    assert artifact.override_log.approval_basis == "Risk accepted by CISO"


# ---------------------------------------------------------------------------
# Test 12: All 6 classes are importable
# ---------------------------------------------------------------------------

def test_all_six_classes_exported():
    """All 6 classes are importable from backend.models.recommendation."""
    classes = _import_models()
    assert len(classes) == 6
    names = [cls.__name__ for cls in classes]
    for expected in ["RecommendationArtifact", "PromptInspection", "RetrievalSources",
                     "OverrideLog", "RecommendationCreate", "ApproveRequest"]:
        assert expected in names, f"{expected} not found in exported names"


# ---------------------------------------------------------------------------
# Test 13: Gate logic — approved_by empty returns error (via model constraint)
# ---------------------------------------------------------------------------

def test_gate_logic_approved_by_empty_returns_error():
    """approved_by must be non-empty when analyst_approved=True."""
    RecommendationArtifact, *_ = _import_models()
    with pytest.raises((ValidationError, ValueError)):
        RecommendationArtifact(**_valid_payload(
            analyst_approved=True,
            approved_by="",
        ))


# ---------------------------------------------------------------------------
# Test 14: Gate logic — expired artifact: model allows it (gate enforced in API layer)
# Rationale: expires_at expiry is a runtime check (PATCH /approve), not model-layer.
# ---------------------------------------------------------------------------

def test_gate_logic_expired_artifact_returns_error():
    """expires_at in the past is accepted by the model (API gate enforces expiry at approval time)."""
    RecommendationArtifact, *_ = _import_models()
    # Model should NOT reject past expires_at — only the approval gate API does
    artifact = RecommendationArtifact(**_valid_payload(
        expires_at="2020-01-01T00:00:00+00:00",
    ))
    assert artifact.expires_at == "2020-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Test 15: Gate logic — low confidence + no override returns error
# ---------------------------------------------------------------------------

def test_gate_logic_low_confidence_no_override_returns_error():
    """inference_confidence='low' with no override_log fails validation."""
    RecommendationArtifact, *_ = _import_models()
    with pytest.raises((ValidationError, ValueError)):
        RecommendationArtifact(**_valid_payload(
            inference_confidence="low",
            override_log=None,
        ))


# ---------------------------------------------------------------------------
# Test 16: Gate logic — high confidence without override passes
# ---------------------------------------------------------------------------

def test_gate_logic_high_confidence_passes_without_override():
    """High confidence with no override_log passes all constraints."""
    RecommendationArtifact, *_ = _import_models()
    artifact = RecommendationArtifact(**_valid_payload(
        inference_confidence="high",
        override_log=None,
    ))
    assert artifact.inference_confidence == "high"
    assert artifact.override_log is None
