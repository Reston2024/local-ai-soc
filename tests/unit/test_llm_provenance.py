"""Failing test stubs for P21-T03: LLM audit provenance (RED state).

All tests intentionally call pytest.fail() — they will be made GREEN
in the Wave 1 executor plans that implement the actual functionality.
"""
import pytest

from backend.models.provenance import LlmProvenanceRecord


def test_llm_provenance_table_exists():
    """SQLiteStore creates llm_audit_provenance table on init."""
    pytest.fail("NOT IMPLEMENTED")


def test_llm_provenance_written():
    """generate() writes a row with audit_id, prompt_template_sha256, and grounding_event_ids."""
    pytest.fail("NOT IMPLEMENTED")


def test_llm_provenance_no_duplicate_rows():
    """Only one provenance row is written per logical LLM call, not per streaming chunk."""
    pytest.fail("NOT IMPLEMENTED")


def test_llm_provenance_api():
    """GET /api/provenance/llm/{audit_id} returns 200 with model_id and response_sha256."""
    pytest.fail("NOT IMPLEMENTED")
