def test_health_endpoint_no_auth_required():
    """GET /health must not return 401 — it is unauthenticated even when AUTH_TOKEN is set."""
    from unittest.mock import MagicMock

    from fastapi.testclient import TestClient

    from backend.main import create_app

    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = "ci-test-token-abc123"
    # Patch verify_token settings so auth is active
    import pytest

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("backend.core.auth.settings", mock_settings)
        client = TestClient(create_app(), raise_server_exceptions=False)
        resp = client.get("/health")
        # Health endpoint must NOT be blocked by auth (not 401/403)
        assert resp.status_code != 401
        assert resp.status_code != 403


def test_events_endpoint_requires_auth_when_token_set(monkeypatch):
    """GET /api/events must return 401 when AUTH_TOKEN is configured and token is missing."""
    from unittest.mock import MagicMock

    from fastapi.testclient import TestClient

    from backend.main import create_app

    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = "ci-test-token-abc123"
    # Patch the settings instance that verify_token reads directly — avoids unreliable
    # importlib.reload() with pydantic-settings singleton. (per monkeypatch.setattr pattern)
    monkeypatch.setattr("backend.core.auth.settings", mock_settings)
    client = TestClient(create_app())
    resp = client.get("/api/events")
    assert resp.status_code == 401
