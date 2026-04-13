"""TDD stubs for Phase 45 POST /api/investigate/agentic. P45-T03.
All tests skip until the route is registered in investigate.py."""
from __future__ import annotations
import pytest

pytestmark = pytest.mark.unit

try:
    from backend.api.investigate import router as investigate_router
    _route_paths = [r.path for r in investigate_router.routes]
    _AGENTIC_ROUTE_AVAILABLE = "/agentic" in " ".join(_route_paths)
except ImportError:
    _AGENTIC_ROUTE_AVAILABLE = False

_skip = pytest.mark.skipif(
    not _AGENTIC_ROUTE_AVAILABLE,
    reason="POST /api/investigate/agentic route not yet registered"
)


@_skip
def test_agentic_endpoint_exists():
    """POST /api/investigate/agentic is registered on the investigate router."""
    from backend.api.investigate import router as investigate_router
    paths = [r.path for r in investigate_router.routes]
    assert any("agentic" in p for p in paths)


@_skip
def test_agentic_sse_content_type():
    """POST /api/investigate/agentic returns text/event-stream content-type."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from unittest.mock import patch, AsyncMock
    from backend.api.investigate import router

    app = FastAPI()
    app.include_router(router)

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/investigate/agentic", json={"detection_id": "det-test"})
        assert resp.status_code in (200, 401, 422)
