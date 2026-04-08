"""Stub tests for Phase 27 recommendation dispatch endpoint (P27-T04). Activated in plan 27-04."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="wave-0 stub — activate in plan 27-04")


def test_dispatch_approved_recommendation_returns_200():
    """POST /api/recommendations/{id}/dispatch with an approved recommendation
    returns 200 with {"dispatched": true, "recommendation_id": id}."""
    from fastapi.testclient import TestClient
    from backend.main import create_app

    client = TestClient(create_app())
    recommendation_id = "test-rec-001"

    response = client.post(f"/api/recommendations/{recommendation_id}/dispatch")
    assert response.status_code == 200
    body = response.json()
    assert body["dispatched"] is True
    assert body["recommendation_id"] == recommendation_id


def test_dispatch_non_approved_returns_409():
    """POST /api/recommendations/{id}/dispatch when status != 'approved' returns 409 Conflict."""
    from fastapi.testclient import TestClient
    from backend.main import create_app

    client = TestClient(create_app())
    recommendation_id = "pending-rec-002"

    response = client.post(f"/api/recommendations/{recommendation_id}/dispatch")
    assert response.status_code == 409


def test_dispatch_not_found_returns_404():
    """POST /api/recommendations/{id}/dispatch for unknown id returns 404."""
    from fastapi.testclient import TestClient
    from backend.main import create_app

    client = TestClient(create_app())

    response = client.post("/api/recommendations/nonexistent-id-xyz/dispatch")
    assert response.status_code == 404


def test_dispatch_schema_validation_failure_returns_422():
    """POST /api/recommendations/{id}/dispatch when RecommendationArtifact
    validation fails returns 422 with {"error": "schema_validation_failed", "detail": [...]}."""
    from fastapi.testclient import TestClient
    from backend.main import create_app

    client = TestClient(create_app())

    # Send malformed body that fails RecommendationArtifact schema
    response = client.post(
        "/api/recommendations/test-rec-003/dispatch",
        json={"invalid_field": "bad_value"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body.get("error") == "schema_validation_failed"
    assert "detail" in body


def test_dispatch_does_not_make_http_call():
    """Dispatch endpoint does NOT make any outbound HTTP calls
    (future phase — no firewall integration yet)."""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from backend.main import create_app

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("httpx.AsyncClient.get") as mock_get, \
         patch("requests.post") as mock_requests_post:

        client = TestClient(create_app())
        client.post("/api/recommendations/test-rec-004/dispatch")

        # No outbound HTTP calls should be made
        mock_post.assert_not_called()
        mock_get.assert_not_called()
        mock_requests_post.assert_not_called()
