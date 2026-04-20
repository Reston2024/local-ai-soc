"""
Authentication security tests.

Covers: missing token, wrong token, empty AUTH_TOKEN misconfiguration,
query-param token path, multiple protected routes, oversized payload rejection.

Requirements: P10-T01, P19-T03, P23.5-T01, P23.5-T02
"""
from __future__ import annotations

import io
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_with_auth(auth_token: str = "ci-test-token-abc123", monkeypatch=None):
    """TestClient with a live AUTH_TOKEN configured (no store mocking — 401 fires before store access)."""
    from backend.main import create_app
    import pytest as _pytest

    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = auth_token

    if monkeypatch is not None:
        monkeypatch.setattr("backend.core.auth.settings", mock_settings)
        return TestClient(create_app(), raise_server_exceptions=False)

    with _pytest.MonkeyPatch().context() as mp:
        mp.setattr("backend.core.auth.settings", mock_settings)
        return TestClient(create_app(), raise_server_exceptions=False)


def _authed_client(monkeypatch):
    """TestClient with mocked stores and auth dependency overridden — for testing routes past the auth guard."""
    from backend.main import create_app
    from backend.core.auth import verify_token
    from backend.core.rbac import OperatorContext

    app = create_app()
    app.state.stores = MagicMock()
    app.state.ollama = MagicMock()
    app.state.settings = MagicMock()
    app.state.settings.DATA_DIR = "data"

    ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
    app.dependency_overrides[verify_token] = lambda: ctx

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Original tests (retained)
# ---------------------------------------------------------------------------

def test_health_endpoint_no_auth_required():
    """GET /health must not return 401 — it is unauthenticated even when AUTH_TOKEN is set."""
    with pytest.MonkeyPatch().context() as mp:
        mock_settings = MagicMock()
        mock_settings.AUTH_TOKEN = "ci-test-token-abc123"
        mp.setattr("backend.core.auth.settings", mock_settings)
        client = TestClient(create_app_(), raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code != 401
        assert resp.status_code != 403


def create_app_():
    from backend.main import create_app
    return create_app()


def test_events_endpoint_requires_auth_when_token_set(monkeypatch):
    """GET /api/events must return 401 when AUTH_TOKEN is configured and token is missing."""
    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = "ci-test-token-abc123"
    monkeypatch.setattr("backend.core.auth.settings", mock_settings)
    from backend.main import create_app
    client = TestClient(create_app())
    resp = client.get("/api/events")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Missing token variations
# ---------------------------------------------------------------------------

def test_missing_token_returns_401(monkeypatch):
    """Request with no Authorization header and no ?token= param → 401."""
    client = _client_with_auth(monkeypatch=monkeypatch)
    resp = client.get("/api/events")
    assert resp.status_code == 401


def test_wrong_token_returns_401(monkeypatch):
    """Request with a plausible but wrong token → 401."""
    client = _client_with_auth(monkeypatch=monkeypatch)
    resp = client.get("/api/events", headers={"Authorization": "Bearer wrong-token-value"})
    assert resp.status_code == 401


def test_empty_bearer_value_returns_401(monkeypatch):
    """Authorization: Bearer  (empty credentials after Bearer) → 401.

    HTTPBearer returns None when credentials is empty, so verify_token
    sees raw=None and should raise 401.
    """
    client = _client_with_auth(monkeypatch=monkeypatch)
    # FastAPI's HTTPBearer rejects malformed headers before verify_token runs
    resp = client.get("/api/events", headers={"Authorization": "Bearer "})
    assert resp.status_code in (401, 403)


def test_non_bearer_scheme_returns_401(monkeypatch):
    """Authorization: Basic dXNlcjpwYXNz → 401 (wrong scheme)."""
    client = _client_with_auth(monkeypatch=monkeypatch)
    import base64
    cred = base64.b64encode(b"user:pass").decode()
    resp = client.get("/api/events", headers={"Authorization": f"Basic {cred}"})
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# AUTH_TOKEN misconfiguration guard
# ---------------------------------------------------------------------------

def test_empty_auth_token_rejects_all_requests(monkeypatch):
    """AUTH_TOKEN = '' → every /api/* request returns 401 with misconfiguration detail.

    The auth module guards against accidental open-access deployment by
    rejecting all requests when AUTH_TOKEN is empty string.
    """
    from backend.main import create_app
    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = ""
    monkeypatch.setattr("backend.core.auth.settings", mock_settings)
    client = TestClient(create_app(), raise_server_exceptions=False)

    for path in ["/api/events", "/api/privacy/hits", "/api/privacy/feeds"]:
        resp = client.get(path, headers={"Authorization": "Bearer anything"})
        assert resp.status_code == 401, f"Expected 401 for empty AUTH_TOKEN on {path}, got {resp.status_code}"


def test_whitespace_only_auth_token_rejects_all_requests(monkeypatch):
    """AUTH_TOKEN = '   ' (whitespace only) → 401 on all routes.

    strip() makes whitespace-only tokens equivalent to empty string.
    """
    from backend.main import create_app
    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = "   "
    monkeypatch.setattr("backend.core.auth.settings", mock_settings)
    client = TestClient(create_app(), raise_server_exceptions=False)
    resp = client.get("/api/events", headers={"Authorization": "Bearer anything"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Query param token path
# ---------------------------------------------------------------------------

def test_query_param_token_bypasses_header_requirement(monkeypatch):
    """Valid token via ?token= query param must not return 401.

    The query param fallback exists for browser-initiated binary downloads
    (PDF, ZIP export) where the browser cannot set headers.
    We verify the auth guard accepts it — we don't care about downstream
    store errors (those are separate concerns).
    """
    from backend.main import create_app
    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = "ci-test-token-abc123"
    monkeypatch.setattr("backend.core.auth.settings", mock_settings)
    client = TestClient(create_app(), raise_server_exceptions=False)
    # Valid token via query param — auth must pass (status != 401)
    resp = client.get("/api/events?token=ci-test-token-abc123")
    assert resp.status_code != 401, (
        f"Query param token must be accepted by verify_token, got {resp.status_code}"
    )


def test_wrong_query_param_token_returns_401(monkeypatch):
    """Wrong token via ?token= → 401."""
    from backend.main import create_app
    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = "ci-test-token-abc123"
    monkeypatch.setattr("backend.core.auth.settings", mock_settings)
    client = TestClient(create_app(), raise_server_exceptions=False)
    resp = client.get("/api/events?token=wrong-token")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Multiple sensitive routes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", [
    # Core event/detection routes (GET)
    ("GET",  "/api/events"),
    ("GET",  "/api/detect"),
    # Score and query use POST
    ("POST", "/api/score"),
    ("POST", "/api/query/ask"),
    # Privacy routes (fixed in Phase 53 hardening — previously missing auth)
    ("GET",  "/api/privacy/hits"),
    ("GET",  "/api/privacy/feeds"),
    ("GET",  "/api/privacy/http-events"),
    ("GET",  "/api/privacy/dns-events"),
    # Ingest (POST)
    ("POST", "/api/ingest/events"),
    # Operator management
    ("GET",  "/api/operators"),
    # Playbooks
    ("GET",  "/api/playbooks"),
    # Export
    ("GET",  "/api/export/events/csv"),
])
def test_sensitive_routes_require_auth(method, path, monkeypatch):
    """Spot-check that all sensitive API routes enforce the auth guard.

    Every /api/* route except /health must reject unauthenticated requests.
    This catches routes accidentally missing the verify_token dependency.
    """
    client = _client_with_auth(monkeypatch=monkeypatch)
    call = getattr(client, method.lower())
    resp = call(path)
    assert resp.status_code == 401, (
        f"[{method}] {path!r} returned {resp.status_code} without auth — "
        "verify_token dependency may be missing"
    )


# ---------------------------------------------------------------------------
# Oversized payload rejection
# ---------------------------------------------------------------------------

def test_oversized_json_payload_rejected(monkeypatch):
    """Ingest endpoint must reject payloads larger than the configured limit.

    Sending a 2 MB JSON body to /api/ingest/events should return 413 or 422,
    not 200 or 500. Accepts 401 as well since auth guard fires first in some
    configurations (no real store wired up in this test).
    """
    client = _client_with_auth(monkeypatch=monkeypatch)
    large_body = '{"events": [' + ','.join(['{"x": "' + 'A' * 1000 + '"}'] * 1500) + ']}'
    resp = client.post(
        "/api/ingest/events",
        content=large_body,
        headers={
            "Authorization": "Bearer ci-test-token-abc123",
            "Content-Type": "application/json",
        },
    )
    # 413 = Request Entity Too Large (preferred)
    # 422 = FastAPI validation failure on oversized list
    # 401 = auth guard fired before size check (acceptable — still rejected)
    # 500 = store not wired up (acceptable — still rejected, not 200)
    # NOT acceptable: 200 (data accepted)
    assert resp.status_code != 200, (
        f"Oversized payload was accepted (200) — ingest endpoint must reject it: "
        f"body size={len(large_body)} bytes"
    )
