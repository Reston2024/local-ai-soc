"""
Wave 0 test stubs for Phase 33 Intel API endpoints.
P33-T09 (ioc-hits endpoint), P33-T16 (feeds endpoint).

Uses FastAPI TestClient with mocked stores — no real disk I/O.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing the intel router — skip if not yet implemented
# ---------------------------------------------------------------------------
try:
    from backend.api import intel as intel_api
    _INTEL_API_AVAILABLE = True
except ImportError:
    _INTEL_API_AVAILABLE = False


def _build_intel_app(ioc_store_mock=None, authed: bool = True):
    """Build a minimal FastAPI app with the intel router mounted."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.core.auth import verify_token
    from backend.core.rbac import OperatorContext
    from backend.main import create_app

    app = create_app()

    # Inject app.state.ioc_store
    if ioc_store_mock is not None:
        app.state.ioc_store = ioc_store_mock
    else:
        app.state.ioc_store = MagicMock()
        app.state.ioc_store.list_hits = MagicMock(return_value=[])
        app.state.ioc_store.get_feed_status = MagicMock(return_value=[])

    # Inject other required state
    app.state.stores = MagicMock()
    app.state.ollama = MagicMock()
    app.state.settings = MagicMock()

    if authed:
        _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
        app.dependency_overrides[verify_token] = lambda: _ctx

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# test_ioc_hits_endpoint
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _INTEL_API_AVAILABLE, reason="Wave 0 stub — implementation in Plan 03")
def test_ioc_hits_endpoint():
    """GET /api/intel/ioc-hits returns 200 with list of hits."""
    mock_ioc_store = MagicMock()
    mock_ioc_store.list_hits = MagicMock(return_value=[
        {"id": 1, "ioc_value": "1.2.3.4", "risk_score": 80},
        {"id": 2, "ioc_value": "5.6.7.8", "risk_score": 60},
    ])
    mock_ioc_store.get_feed_status = MagicMock(return_value=[])

    client = _build_intel_app(ioc_store_mock=mock_ioc_store, authed=True)
    resp = client.get("/api/intel/ioc-hits")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2


# ---------------------------------------------------------------------------
# test_feeds_endpoint
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _INTEL_API_AVAILABLE, reason="Wave 0 stub — implementation in Plan 03")
def test_feeds_endpoint():
    """GET /api/intel/feeds returns 200 with list of 3 feed statuses."""
    mock_ioc_store = MagicMock()
    mock_ioc_store.list_hits = MagicMock(return_value=[])
    mock_ioc_store.get_feed_status = MagicMock(return_value=[
        {"feed": "feodo", "last_sync": "2024-01-01T00:00:00Z", "ioc_count": 100, "status": "ok"},
        {"feed": "cisa_kev", "last_sync": "2024-01-01T00:00:00Z", "ioc_count": 50, "status": "ok"},
        {"feed": "threatfox", "last_sync": None, "ioc_count": 0, "status": "never"},
    ])

    client = _build_intel_app(ioc_store_mock=mock_ioc_store, authed=True)
    resp = client.get("/api/intel/feeds")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 3


# ---------------------------------------------------------------------------
# test_intel_requires_auth
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _INTEL_API_AVAILABLE, reason="Wave 0 stub — implementation in Plan 03")
def test_intel_requires_auth():
    """GET /api/intel/ioc-hits without token returns 401 or 403."""
    client = _build_intel_app(authed=False)
    resp = client.get("/api/intel/ioc-hits")

    assert resp.status_code in (401, 403)
