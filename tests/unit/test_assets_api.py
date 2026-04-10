"""
Wave 0 test stubs for Phase 34 Assets API endpoints.
P34-T08 — GET /api/assets, GET /api/assets/{ip}, POST /api/assets/{ip}/tag.

Uses FastAPI TestClient with mocked stores — no real disk I/O.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing the assets router — skip if not yet implemented
# ---------------------------------------------------------------------------
try:
    from backend.api import assets as assets_api  # noqa: F401
    _ASSETS_API_AVAILABLE = True
except ImportError:
    _ASSETS_API_AVAILABLE = False


def _build_assets_app(asset_store_mock=None, authed: bool = True):
    """Build a minimal FastAPI app with assets router for testing."""
    from fastapi.testclient import TestClient

    from backend.core.auth import verify_token
    from backend.core.rbac import OperatorContext
    from backend.main import create_app

    app = create_app()

    # Inject app.state.asset_store
    if asset_store_mock is not None:
        app.state.asset_store = asset_store_mock
    else:
        mock = MagicMock()
        mock.list_assets = MagicMock(return_value=[])
        mock.get_asset = MagicMock(return_value=None)
        mock.set_tag = MagicMock(return_value=None)
        app.state.asset_store = mock

    # Inject other required state
    app.state.stores = MagicMock()
    app.state.ollama = MagicMock()
    app.state.settings = MagicMock()

    if authed:
        _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
        app.dependency_overrides[verify_token] = lambda: _ctx

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# test_list_assets
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _ASSETS_API_AVAILABLE, reason="Wave 0 stub — implementation in Plan 03")
def test_list_assets():
    """GET /api/assets returns 200 and body is a list."""
    mock_store = MagicMock()
    mock_store.list_assets = MagicMock(return_value=[])
    mock_store.get_asset = MagicMock(return_value=None)
    mock_store.set_tag = MagicMock(return_value=None)

    client = _build_assets_app(asset_store_mock=mock_store, authed=True)
    resp = client.get("/api/assets")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# test_get_asset
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _ASSETS_API_AVAILABLE, reason="Wave 0 stub — implementation in Plan 03")
def test_get_asset():
    """GET /api/assets/{ip} returns 200 with asset dict when asset exists."""
    mock_store = MagicMock()
    mock_store.list_assets = MagicMock(return_value=[])
    mock_store.get_asset = MagicMock(return_value={
        "ip": "192.168.1.10",
        "hostname": "ws01",
        "tag": "internal",
        "last_seen": "2024-01-01T00:00:00Z",
        "first_seen": "2024-01-01T00:00:00Z",
        "alert_count": 0,
        "risk_score": 0,
    })
    mock_store.set_tag = MagicMock(return_value=None)

    client = _build_assets_app(asset_store_mock=mock_store, authed=True)
    resp = client.get("/api/assets/192.168.1.10")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ip"] == "192.168.1.10"


# ---------------------------------------------------------------------------
# test_tag_asset
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _ASSETS_API_AVAILABLE, reason="Wave 0 stub — implementation in Plan 03")
def test_tag_asset():
    """POST /api/assets/{ip}/tag with body {"tag": "internal"} returns 200."""
    mock_store = MagicMock()
    mock_store.list_assets = MagicMock(return_value=[])
    mock_store.get_asset = MagicMock(return_value={"ip": "192.168.1.10"})
    mock_store.set_tag = MagicMock(return_value=None)

    client = _build_assets_app(asset_store_mock=mock_store, authed=True)
    resp = client.post(
        "/api/assets/192.168.1.10/tag",
        json={"tag": "internal"},
    )

    assert resp.status_code == 200
