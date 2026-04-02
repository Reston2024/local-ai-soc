"""Failing test stubs for P21-T02: detection provenance (RED state).

All tests intentionally call pytest.fail() — they will be made GREEN
in the Wave 1 executor plans that implement the actual functionality.
"""
import pytest

from backend.models.provenance import DetectionProvenanceRecord


def test_detection_provenance_table_exists():
    """SQLiteStore creates detection_provenance table on init."""
    pytest.fail("NOT IMPLEMENTED")


def test_detection_provenance_fields():
    """Detection provenance row contains pySigma version, rule_sha256, and field_map_version."""
    pytest.fail("NOT IMPLEMENTED")


def test_detection_provenance_api():
    """GET /api/provenance/detection/{id} returns 200 with rule_sha256 and pysigma_version."""
    pytest.fail("NOT IMPLEMENTED")
