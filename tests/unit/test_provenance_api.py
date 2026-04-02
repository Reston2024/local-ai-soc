"""Failing test stubs for P21-T05: provenance API auth enforcement (RED state).

All tests intentionally call pytest.fail() — they will be made GREEN
in the Wave 2 executor plans that implement the actual functionality.
"""
import pytest

from backend.models.provenance import (
    IngestProvenanceRecord,
    DetectionProvenanceRecord,
    LlmProvenanceRecord,
    PlaybookProvenanceRecord,
)


def test_provenance_endpoints_require_auth():
    """All 4 GET provenance endpoints return HTTP 401 when called without an auth token."""
    pytest.fail("NOT IMPLEMENTED")
