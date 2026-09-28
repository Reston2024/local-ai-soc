"""/api/feedback must enforce verify_token (was mounted without auth)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

TOKEN = "ci-test-token-abc123"
BODY = {"detection_id": "det-1", "verdict": "TP"}


@pytest.fixture
def client(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = TOKEN
    monkeypatch.setattr("backend.core.auth.settings", mock_settings)
    from backend.main import create_app
    app = create_app()
    app.state.stores = MagicMock()
    app.state.ollama = MagicMock()
    return TestClient(app, raise_server_exceptions=False)


def test_feedback_post_requires_auth(client):
    assert client.post("/api/feedback", json=BODY).status_code == 401


def test_feedback_similar_requires_auth(client):
    assert client.get("/api/feedback/similar?detection_id=det-1").status_code == 401


def test_feedback_post_with_token_passes_auth(client):
    resp = client.post("/api/feedback", json=BODY, headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code != 401


def test_feedback_similar_with_token_passes_auth(client):
    resp = client.get(
        "/api/feedback/similar?detection_id=det-1",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code != 401
