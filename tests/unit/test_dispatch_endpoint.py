"""
Dispatch endpoint tests for POST /api/recommendations/{id}/dispatch (Plan 27-04).

Tests activated from wave-0 stubs; uses mocked DuckDB store pattern
(same as test_recommendation_api.py) — no real DB required.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures — mirror test_recommendation_api.py pattern
# ---------------------------------------------------------------------------


def _make_db_row(
    rec_id: str,
    case_id: str,
    status: str = "draft",
    inference_confidence: str = "high",
    prompt_inspection_passed: bool = True,
) -> tuple:
    """Return a DuckDB tuple row matching the recommendations SELECT column order."""
    now = datetime.now(timezone.utc).isoformat()
    return (
        rec_id,                                           # recommendation_id
        case_id,                                          # case_id
        "1.0.0",                                          # schema_version
        "network_control_change",                         # type
        "Block outbound traffic to 10.0.0.5",             # proposed_action
        "10.0.0.5",                                       # target
        "perimeter-firewall",                             # scope
        json.dumps(["High-confidence C2 beacon detected"]),  # rationale
        json.dumps([str(uuid4())]),                       # evidence_event_ids
        json.dumps({"count": 1, "ids": [str(uuid4())]}),  # retrieval_sources
        inference_confidence,                             # inference_confidence
        "llama3:8b",                                      # model_id
        str(uuid4()),                                     # model_run_id
        json.dumps({                                      # prompt_inspection
            "method": "regex-v1",
            "passed": prompt_inspection_passed,
            "flagged_patterns": [],
            "audit_log_id": str(uuid4()),
        }),
        "2026-01-01T00:00:00+00:00",                      # generated_at
        status == "approved",                             # analyst_approved
        "analyst@example.com" if status == "approved" else "",  # approved_by
        None,                                             # override_log
        "2026-12-31T23:59:59+00:00",                      # expires_at
        status,                                           # status
        now,                                              # created_at
    )


def _make_corrupt_db_row(rec_id: str, case_id: str) -> tuple:
    """Return an approved row with a corrupt type field that fails RecommendationArtifact validation."""
    now = datetime.now(timezone.utc).isoformat()
    return (
        rec_id,                                           # recommendation_id
        case_id,                                          # case_id
        "1.0.0",                                          # schema_version
        "INVALID_TYPE_NOT_IN_SCHEMA",                     # type — will fail pydantic
        "Block outbound traffic to 10.0.0.5",             # proposed_action
        "10.0.0.5",                                       # target
        "perimeter-firewall",                             # scope
        json.dumps(["High-confidence C2 beacon detected"]),  # rationale
        json.dumps([str(uuid4())]),                       # evidence_event_ids
        json.dumps({"count": 1, "ids": [str(uuid4())]}),  # retrieval_sources
        "high",                                           # inference_confidence
        "llama3:8b",                                      # model_id
        str(uuid4()),                                     # model_run_id
        json.dumps({                                      # prompt_inspection
            "method": "regex-v1",
            "passed": True,
            "flagged_patterns": [],
            "audit_log_id": str(uuid4()),
        }),
        "2026-01-01T00:00:00+00:00",                      # generated_at
        True,                                             # analyst_approved
        "analyst@example.com",                            # approved_by
        None,                                             # override_log
        "2026-12-31T23:59:59+00:00",                      # expires_at
        "approved",                                       # status
        now,                                              # created_at
    )


@pytest.fixture()
def mock_duckdb() -> AsyncMock:
    """AsyncMock that mimics DuckDBStore interface."""
    db = AsyncMock()
    db.execute_write = AsyncMock(return_value=None)
    db.fetch_all = AsyncMock(return_value=[])
    return db


@pytest.fixture()
def app(mock_duckdb: AsyncMock) -> FastAPI:
    """Minimal FastAPI app with recommendations router and mocked stores."""
    from backend.api.recommendations import router as recommendations_router

    _app = FastAPI()
    stores = MagicMock()
    stores.duckdb = mock_duckdb
    _app.state.stores = stores
    _app.include_router(recommendations_router)
    return _app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Test: 404 for unknown recommendation ID
# ---------------------------------------------------------------------------


def test_dispatch_not_found_returns_404(client: TestClient, mock_duckdb: AsyncMock):
    """POST /api/recommendations/{id}/dispatch for unknown id returns 404."""
    mock_duckdb.fetch_all = AsyncMock(return_value=[])

    response = client.post("/api/recommendations/nonexistent-id-xyz/dispatch")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test: 409 for non-approved recommendation
# ---------------------------------------------------------------------------


def test_dispatch_non_approved_returns_409(client: TestClient, mock_duckdb: AsyncMock):
    """POST /api/recommendations/{id}/dispatch when status != 'approved' returns 409 Conflict."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    draft_row = _make_db_row(rec_id, case_id, status="draft")
    mock_duckdb.fetch_all = AsyncMock(return_value=[draft_row])

    response = client.post(f"/api/recommendations/{rec_id}/dispatch")
    assert response.status_code == 409
    body = response.json()
    assert body.get("error") == "not_approved"


# ---------------------------------------------------------------------------
# Test: 200 for approved recommendation
# ---------------------------------------------------------------------------


def test_dispatch_approved_recommendation_returns_200(client: TestClient, mock_duckdb: AsyncMock):
    """POST /api/recommendations/{id}/dispatch with an approved recommendation
    returns 200 with {"dispatched": true, "recommendation_id": id}."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    approved_row = _make_db_row(rec_id, case_id, status="approved")
    mock_duckdb.fetch_all = AsyncMock(return_value=[approved_row])

    response = client.post(f"/api/recommendations/{rec_id}/dispatch")
    assert response.status_code == 200
    body = response.json()
    assert body["dispatched"] is True
    assert body["recommendation_id"] == rec_id
    assert "artifact_type" in body


# ---------------------------------------------------------------------------
# Test: 422 for approved recommendation with corrupt artifact data
# ---------------------------------------------------------------------------


def test_dispatch_schema_validation_failure_returns_422(client: TestClient, mock_duckdb: AsyncMock):
    """POST /api/recommendations/{id}/dispatch when RecommendationArtifact
    validation fails returns 422 with {"error": "schema_validation_failed", "detail": [...]}."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    corrupt_row = _make_corrupt_db_row(rec_id, case_id)
    mock_duckdb.fetch_all = AsyncMock(return_value=[corrupt_row])

    response = client.post(f"/api/recommendations/{rec_id}/dispatch")
    assert response.status_code == 422
    body = response.json()
    assert body.get("error") == "schema_validation_failed"
    assert "detail" in body


# ---------------------------------------------------------------------------
# Test: No outbound HTTP calls during dispatch
# ---------------------------------------------------------------------------


def test_dispatch_does_not_make_http_call(client: TestClient, mock_duckdb: AsyncMock):
    """Dispatch endpoint does NOT make any outbound HTTP calls
    (future phase — no firewall integration yet)."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    # Return empty — will hit 404, but no HTTP call should be made regardless
    mock_duckdb.fetch_all = AsyncMock(return_value=[])

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("httpx.AsyncClient.get") as mock_get, \
         patch("requests.post") as mock_requests_post:

        client.post(f"/api/recommendations/{rec_id}/dispatch")

        mock_post.assert_not_called()
        mock_get.assert_not_called()
        mock_requests_post.assert_not_called()
