"""
Phase 53 Plan 03: Privacy REST API tests.
Tests for PRIV-09 and PRIV-10 (hits and feeds endpoints).

Uses FastAPI TestClient with the privacy router mounted on a minimal app.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

pytestmark = pytest.mark.unit

# Skip the entire file if the implementation module does not yet exist.
privacy_api = pytest.importorskip(
    "backend.api.privacy",
    reason="Wave 0 — implement in Plan 53-03",
)


# ---------------------------------------------------------------------------
# PRIV-09: Hits endpoint
# ---------------------------------------------------------------------------

def test_hits_endpoint_returns_list():
    """GET /api/privacy/hits returns 200 with JSON body containing a 'hits' list.

    PRIV-09: TestClient(app) with a minimal FastAPI app that includes the privacy
    router returns 200 and a response body with a top-level 'hits' key whose
    value is a list.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.privacy import router as privacy_router

    app = FastAPI()
    app.include_router(privacy_router)
    client = TestClient(app)
    response = client.get("/api/privacy/hits")
    assert response.status_code == 200
    data = response.json()
    assert "hits" in data
    assert isinstance(data["hits"], list)


# ---------------------------------------------------------------------------
# PRIV-10: Feeds endpoint
# ---------------------------------------------------------------------------

def test_feeds_endpoint_returns_status():
    """GET /api/privacy/feeds returns 200 with JSON body containing a 'feeds' list.

    PRIV-10: Each entry in the 'feeds' list must have 'feed', 'last_sync',
    and 'domain_count' keys — matching the PrivacyBlocklistStore.get_feed_status()
    contract defined in PRIV-04b.

    Note: bare FastAPI app without privacy_store on app.state triggers the
    graceful-degradation path which returns {"feeds": []}.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.privacy import router as privacy_router

    app = FastAPI()
    app.include_router(privacy_router)
    client = TestClient(app)
    response = client.get("/api/privacy/feeds")
    assert response.status_code == 200
    data = response.json()
    assert "feeds" in data
    assert isinstance(data["feeds"], list)
    # If feeds list is non-empty, verify structure
    for entry in data["feeds"]:
        assert "feed" in entry
        assert "last_sync" in entry
        assert "domain_count" in entry
