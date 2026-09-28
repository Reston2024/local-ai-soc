"""Health endpoint auth model: /health/ping open, /health/network auth, /health minimal when anonymous."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

TOKEN = "ci-test-token-abc123"


@pytest.fixture
def client(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = TOKEN
    monkeypatch.setattr("backend.core.auth.settings", mock_settings)
    from backend.main import create_app
    app = create_app()
    stores = MagicMock()
    stores.duckdb.fetch_all = AsyncMock(return_value=[(1,)])
    stores.chroma.list_collections_async = AsyncMock(return_value=[])
    stores.chroma.mode = "local_fallback"
    stores.sqlite._conn.execute.return_value.fetchone.return_value = (0,)
    stores.sqlite.health_check = MagicMock(return_value={})
    app.state.stores = stores
    app.state.ollama = MagicMock()
    app.state.ollama.health_check = AsyncMock(return_value=False)
    return TestClient(app, raise_server_exceptions=False)


def test_health_ping_is_open(client):
    resp = client.get("/health/ping")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_network_requires_auth(client):
    assert client.get("/health/network").status_code == 401


def test_health_network_with_token(client):
    resp = client.get("/health/network", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200
    assert "devices" in resp.json()


def test_health_anonymous_is_minimal(client):
    resp = client.get("/health")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert set(body) == {"status", "timestamp"}


def test_health_authenticated_has_components(client):
    resp = client.get("/health", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code in (200, 503)
    assert "components" in resp.json()


def test_health_wrong_token_is_minimal(client):
    resp = client.get("/health", headers={"Authorization": "Bearer nope"})
    assert "components" not in resp.json()
