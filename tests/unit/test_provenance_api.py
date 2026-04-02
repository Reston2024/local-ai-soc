"""Tests for P21-T05: provenance API auth enforcement.

Verifies that all 4 GET provenance endpoints return HTTP 401 when called
without a valid auth token.
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
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.provenance import router as provenance_router

    app = FastAPI()
    app.include_router(provenance_router)
    # No dependency overrides — auth is NOT bypassed

    client = TestClient(app, raise_server_exceptions=False)

    endpoints = [
        "/api/provenance/ingest/test-event-id",
        "/api/provenance/detection/test-detection-id",
        "/api/provenance/llm/test-audit-id",
        "/api/provenance/playbook/test-run-id",
    ]
    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 401, (
            f"Expected 401 for unauthenticated request to {url}, "
            f"got {resp.status_code}: {resp.text}"
        )
