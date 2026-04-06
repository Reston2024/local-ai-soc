"""
Unit tests for POST/GET recommendation API routes (Plan 24-03).

Uses FastAPI TestClient with a mock DuckDB store — no real DB required.
Tests drive TDD RED phase; implementation is in backend/api/recommendations.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_BODY = {
    "case_id": str(uuid4()),
    "type": "network_control_change",
    "proposed_action": "Block outbound traffic to 10.0.0.5",
    "target": "10.0.0.5",
    "scope": "perimeter-firewall",
    "rationale": ["High-confidence C2 beacon detected"],
    "evidence_event_ids": [str(uuid4())],
    "retrieval_sources": {"count": 1, "ids": [str(uuid4())]},
    "inference_confidence": "high",
    "model_id": "llama3:8b",
    "model_run_id": str(uuid4()),
    "prompt_inspection": {
        "method": "regex-v1",
        "passed": True,
        "flagged_patterns": [],
        "audit_log_id": str(uuid4()),
    },
    "generated_at": "2026-01-01T00:00:00Z",
    "expires_at": "2026-12-31T23:59:59Z",
}


def _make_db_row(rec_id: str, case_id: str, status: str = "draft") -> tuple:
    """Return a DuckDB tuple row matching the recommendations SELECT column order."""
    now = datetime.now(timezone.utc).isoformat()
    return (
        rec_id,                                  # recommendation_id
        case_id,                                 # case_id
        "1.0.0",                                 # schema_version
        "network_control_change",                # type
        "Block outbound traffic to 10.0.0.5",    # proposed_action
        "10.0.0.5",                              # target
        "perimeter-firewall",                    # scope
        json.dumps(["High-confidence C2 beacon detected"]),   # rationale
        json.dumps([str(uuid4())]),              # evidence_event_ids
        json.dumps({"count": 1, "ids": [str(uuid4())]}),  # retrieval_sources
        "high",                                  # inference_confidence
        "llama3:8b",                             # model_id
        str(uuid4()),                            # model_run_id
        json.dumps({"method": "regex-v1", "passed": True, "flagged_patterns": [], "audit_log_id": str(uuid4())}),  # prompt_inspection
        "2026-01-01T00:00:00+00:00",             # generated_at
        False,                                   # analyst_approved
        "",                                      # approved_by
        None,                                    # override_log
        "2026-12-31T23:59:59+00:00",             # expires_at
        status,                                  # status
        now,                                     # created_at
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
# POST /api/recommendations
# ---------------------------------------------------------------------------


def test_post_recommendation_creates_draft(client: TestClient, mock_duckdb: AsyncMock):
    """POST /api/recommendations returns 201 with recommendation_id; status=draft."""
    resp = client.post("/api/recommendations", json=_VALID_BODY)
    assert resp.status_code == 201
    data = resp.json()
    assert "recommendation_id" in data
    # UUID v4 — just check it's a non-empty string
    assert isinstance(data["recommendation_id"], str)
    assert len(data["recommendation_id"]) == 36

    # execute_write called once with INSERT
    mock_duckdb.execute_write.assert_awaited_once()
    call_args = mock_duckdb.execute_write.call_args
    sql = call_args[0][0]
    assert "INSERT INTO recommendations" in sql
    params = call_args[0][1]
    # status is the 20th param (index 19)
    assert params[19] == "draft"
    # analyst_approved is index 15
    assert params[15] is False


def test_post_recommendation_invalid_body_returns_422(client: TestClient):
    """POST with missing required fields returns 422."""
    resp = client.post("/api/recommendations", json={"case_id": "x"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/recommendations/{id}
# ---------------------------------------------------------------------------


def test_get_recommendation_by_id(client: TestClient, mock_duckdb: AsyncMock, app: FastAPI):
    """GET /api/recommendations/{id} returns full artifact dict."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    mock_duckdb.fetch_all = AsyncMock(return_value=[_make_db_row(rec_id, case_id)])

    resp = client.get(f"/api/recommendations/{rec_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["recommendation_id"] == rec_id
    assert data["case_id"] == case_id
    assert data["status"] == "draft"
    assert data["analyst_approved"] is False
    # JSON columns must be deserialized
    assert isinstance(data["rationale"], list)
    assert isinstance(data["retrieval_sources"], dict)
    assert isinstance(data["prompt_inspection"], dict)


def test_get_recommendation_not_found(client: TestClient, mock_duckdb: AsyncMock):
    """GET /api/recommendations/{id} returns 404 for unknown id."""
    mock_duckdb.fetch_all = AsyncMock(return_value=[])
    resp = client.get(f"/api/recommendations/{uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/recommendations (list)
# ---------------------------------------------------------------------------


def test_list_recommendations_no_filters(client: TestClient, mock_duckdb: AsyncMock):
    """GET /api/recommendations returns {"items": [...], "total": N}."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    row = _make_db_row(rec_id, case_id)
    # first call = COUNT(*), second call = SELECT *
    mock_duckdb.fetch_all = AsyncMock(side_effect=[([(1,)]), ([row])])

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["recommendation_id"] == rec_id


def test_list_recommendations_filter_by_status(client: TestClient, mock_duckdb: AsyncMock):
    """GET /api/recommendations?status=draft filters by status column."""
    mock_duckdb.fetch_all = AsyncMock(side_effect=[([(0,)]), ([])])

    resp = client.get("/api/recommendations?status=draft")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []

    # Both COUNT and SELECT calls should have used "status = ?" filter
    calls = mock_duckdb.fetch_all.call_args_list
    count_sql = calls[0][0][0]
    assert "WHERE" in count_sql
    assert "status = ?" in count_sql


def test_list_recommendations_filter_by_case_id(client: TestClient, mock_duckdb: AsyncMock):
    """GET /api/recommendations?case_id=UUID filters by case_id column."""
    mock_duckdb.fetch_all = AsyncMock(side_effect=[([(0,)]), ([])])
    resp = client.get(f"/api/recommendations?case_id={uuid4()}")
    assert resp.status_code == 200
    calls = mock_duckdb.fetch_all.call_args_list
    count_sql = calls[0][0][0]
    assert "case_id = ?" in count_sql


# ---------------------------------------------------------------------------
# _run_approval_gate unit tests (Plan 24-04, ADR-030 §2 + §4)
# ---------------------------------------------------------------------------


def _make_rec(
    confidence: str = "high",
    passed: bool = True,
    expires_at: str = "2099-12-31T23:59:59+00:00",
    analyst_approved: bool = False,
) -> dict:
    """Return a minimal rec dict for gate testing."""
    return {
        "recommendation_id": str(uuid4()),
        "analyst_approved": analyst_approved,
        "inference_confidence": confidence,
        "prompt_inspection": {"method": "regex-v1", "passed": passed, "flagged_patterns": [], "audit_log_id": str(uuid4())},
        "expires_at": expires_at,
        "status": "draft",
    }


def _make_approve_body(approved_by: str = "analyst@soc", override_log=None):
    from backend.models.recommendation import ApproveRequest
    return ApproveRequest(approved_by=approved_by, override_log=override_log)


def test_gate_returns_empty_for_valid_input():
    """_run_approval_gate returns [] when all conditions pass."""
    from backend.api.recommendations import _run_approval_gate

    rec = _make_rec(confidence="high", passed=True, expires_at="2099-12-31T23:59:59+00:00")
    body = _make_approve_body(approved_by="analyst@soc")
    errors = _run_approval_gate(rec, body)
    assert errors == []


def test_gate_returns_error_when_approved_by_empty():
    """_run_approval_gate returns error when approved_by is empty string."""
    from backend.api.recommendations import _run_approval_gate

    rec = _make_rec()
    body = _make_approve_body(approved_by="")
    errors = _run_approval_gate(rec, body)
    assert any("approved_by" in e for e in errors)


def test_gate_returns_error_when_approved_by_whitespace_only():
    """_run_approval_gate returns error when approved_by is whitespace."""
    from backend.api.recommendations import _run_approval_gate

    rec = _make_rec()
    body = _make_approve_body(approved_by="   ")
    errors = _run_approval_gate(rec, body)
    assert any("approved_by" in e for e in errors)


def test_gate_returns_error_when_expires_at_in_past():
    """_run_approval_gate returns error when expires_at is yesterday."""
    from backend.api.recommendations import _run_approval_gate

    rec = _make_rec(expires_at="2000-01-01T00:00:00+00:00")
    body = _make_approve_body()
    errors = _run_approval_gate(rec, body)
    assert any("past" in e for e in errors)


def test_gate_returns_error_when_low_confidence_no_override():
    """_run_approval_gate returns error when confidence=low and override_log=None."""
    from backend.api.recommendations import _run_approval_gate

    rec = _make_rec(confidence="low")
    body = _make_approve_body(override_log=None)
    errors = _run_approval_gate(rec, body)
    assert any("override_log" in e for e in errors)


def test_gate_returns_error_when_none_confidence_no_override():
    """_run_approval_gate returns error when confidence=none and override_log=None."""
    from backend.api.recommendations import _run_approval_gate

    rec = _make_rec(confidence="none")
    body = _make_approve_body(override_log=None)
    errors = _run_approval_gate(rec, body)
    assert any("override_log" in e for e in errors)


def test_gate_returns_error_when_inspection_failed_no_override():
    """_run_approval_gate returns error when prompt_inspection.passed=False and no override."""
    from backend.api.recommendations import _run_approval_gate

    rec = _make_rec(confidence="high", passed=False)
    body = _make_approve_body(override_log=None)
    errors = _run_approval_gate(rec, body)
    assert any("override_log" in e for e in errors)


def test_gate_passes_when_low_confidence_with_override():
    """_run_approval_gate returns [] when confidence=low but override_log provided."""
    from backend.api.recommendations import _run_approval_gate
    from backend.models.recommendation import OverrideLog

    rec = _make_rec(confidence="low")
    override = OverrideLog(
        approved_at="2026-04-06T00:00:00Z",
        approval_basis="Manual review completed",
        modified_fields=[],
        operator_note="Low confidence threshold accepted",
    )
    body = _make_approve_body(override_log=override)
    errors = _run_approval_gate(rec, body)
    assert errors == []


# ---------------------------------------------------------------------------
# PATCH /api/recommendations/{id}/approve route tests (Plan 24-04)
# ---------------------------------------------------------------------------


def _make_approve_row(
    rec_id: str,
    case_id: str,
    analyst_approved: bool = False,
    confidence: str = "high",
    passed: bool = True,
    expires_at: str = "2099-12-31T23:59:59+00:00",
    status: str = "draft",
) -> tuple:
    """Return a DuckDB tuple row suitable for approve endpoint testing."""
    now = datetime.now(timezone.utc).isoformat()
    return (
        rec_id,
        case_id,
        "1.0.0",
        "network_control_change",
        "Block outbound traffic to 10.0.0.5",
        "10.0.0.5",
        "perimeter-firewall",
        json.dumps(["High-confidence C2 beacon detected"]),
        json.dumps([str(uuid4())]),
        json.dumps({"count": 1, "ids": [str(uuid4())]}),
        confidence,
        "llama3:8b",
        str(uuid4()),
        json.dumps({"method": "regex-v1", "passed": passed, "flagged_patterns": [], "audit_log_id": str(uuid4())}),
        "2026-01-01T00:00:00+00:00",
        analyst_approved,
        "",
        None,
        expires_at,
        status,
        now,
    )


def test_approve_recommendation_valid(client: TestClient, mock_duckdb: AsyncMock):
    """PATCH /approve with valid body sets analyst_approved=True; returns 200."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    mock_duckdb.fetch_all = AsyncMock(return_value=[
        _make_approve_row(rec_id, case_id, analyst_approved=False)
    ])

    resp = client.patch(
        f"/api/recommendations/{rec_id}/approve",
        json={"approved_by": "analyst@soc"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["recommendation_id"] == rec_id

    # execute_write called once with UPDATE
    mock_duckdb.execute_write.assert_awaited_once()
    call_args = mock_duckdb.execute_write.call_args[0]
    assert "UPDATE recommendations" in call_args[0]
    assert "analyst_approved = TRUE" in call_args[0]


def test_approve_recommendation_empty_approved_by_returns_422(
    client: TestClient, mock_duckdb: AsyncMock
):
    """PATCH /approve with empty approved_by returns 422 with gate_errors."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    mock_duckdb.fetch_all = AsyncMock(return_value=[
        _make_approve_row(rec_id, case_id, analyst_approved=False)
    ])

    resp = client.patch(
        f"/api/recommendations/{rec_id}/approve",
        json={"approved_by": ""},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "gate_errors" in detail
    assert len(detail["gate_errors"]) > 0


def test_approve_recommendation_low_confidence_no_override_returns_422(
    client: TestClient, mock_duckdb: AsyncMock
):
    """PATCH /approve with confidence=low and no override_log returns 422."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    mock_duckdb.fetch_all = AsyncMock(return_value=[
        _make_approve_row(rec_id, case_id, confidence="low")
    ])

    resp = client.patch(
        f"/api/recommendations/{rec_id}/approve",
        json={"approved_by": "analyst@soc"},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "gate_errors" in detail


def test_approve_recommendation_double_approval_returns_409(
    client: TestClient, mock_duckdb: AsyncMock
):
    """PATCH /approve on already-approved artifact returns 409 Conflict."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    mock_duckdb.fetch_all = AsyncMock(return_value=[
        _make_approve_row(rec_id, case_id, analyst_approved=True, status="approved")
    ])

    resp = client.patch(
        f"/api/recommendations/{rec_id}/approve",
        json={"approved_by": "analyst@soc"},
    )
    assert resp.status_code == 409


def test_approve_recommendation_expired_artifact_returns_422(
    client: TestClient, mock_duckdb: AsyncMock
):
    """PATCH /approve with expires_at in past returns 422 gate error."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    mock_duckdb.fetch_all = AsyncMock(return_value=[
        _make_approve_row(rec_id, case_id, expires_at="2000-01-01T00:00:00+00:00")
    ])

    resp = client.patch(
        f"/api/recommendations/{rec_id}/approve",
        json={"approved_by": "analyst@soc"},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "gate_errors" in detail
    assert any("past" in e for e in detail["gate_errors"])


def test_approve_recommendation_not_found_returns_404(
    client: TestClient, mock_duckdb: AsyncMock
):
    """PATCH /approve on unknown ID returns 404."""
    mock_duckdb.fetch_all = AsyncMock(return_value=[])

    resp = client.patch(
        f"/api/recommendations/{uuid4()}/approve",
        json={"approved_by": "analyst@soc"},
    )
    assert resp.status_code == 404


def test_approve_sets_analyst_approved_true_in_db(
    client: TestClient, mock_duckdb: AsyncMock
):
    """After successful PATCH /approve, execute_write is called with analyst_approved=TRUE."""
    rec_id = str(uuid4())
    case_id = str(uuid4())
    mock_duckdb.fetch_all = AsyncMock(return_value=[
        _make_approve_row(rec_id, case_id, analyst_approved=False)
    ])

    client.patch(
        f"/api/recommendations/{rec_id}/approve",
        json={"approved_by": "analyst@soc"},
    )
    call_args = mock_duckdb.execute_write.call_args[0]
    params = call_args[1]
    # params: [approved_by, override_json, recommendation_id]
    assert params[0] == "analyst@soc"
    assert params[2] == rec_id
