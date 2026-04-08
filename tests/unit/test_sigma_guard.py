"""
Unit tests for the 0-rule guard in POST /api/detect/run.

TDD RED phase: these tests are written BEFORE the guard is added to detect.py.
- test_run_detection_no_rules_raises_422: expects HTTP 422 when 0 rules are loaded
- test_run_detection_with_rules_proceeds: expects HTTP 200 when rules are present

After adding the guard (Task 2), both tests must pass (GREEN).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_client() -> TestClient:
    """Build a TestClient with mocked stores and auth bypassed."""
    from backend.core.auth import verify_token
    from backend.core.deps import Stores
    from backend.core.rbac import OperatorContext
    from backend.main import create_app

    app = create_app()

    # Minimal mock stores
    duckdb = MagicMock()
    duckdb.fetch_all = AsyncMock(return_value=[])
    duckdb.execute_write = AsyncMock(return_value=None)

    chroma = MagicMock()
    chroma.query_async = AsyncMock(return_value=[])

    sqlite = MagicMock()
    sqlite._conn = MagicMock()
    sqlite._conn.execute = MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))

    stores = Stores(duckdb=duckdb, chroma=chroma, sqlite=sqlite)
    app.state.stores = stores
    app.state.ollama = MagicMock()
    app.state.settings = MagicMock()

    # Bypass JWT/TOTP auth
    _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
    app.dependency_overrides[verify_token] = lambda: _ctx

    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSigmaRunGuard:
    """Guard: POST /api/detect/run must return 422 when 0 rules are loaded."""

    def test_run_detection_no_rules_raises_422(self):
        """When load_rules_dir returns 0 for every dir, endpoint must return 422."""
        with patch("backend.api.detect.SigmaMatcher") as MockMatcher:
            instance = MagicMock()
            # load_rules_dir returns 0 — simulates no rules present
            instance.load_rules_dir.return_value = 0
            MockMatcher.return_value = instance

            client = _build_client()
            response = client.post("/api/detect/run")

        assert response.status_code == 422, (
            f"Expected 422 when 0 rules loaded, got {response.status_code}: {response.text}"
        )
        detail = response.json().get("detail", "")
        assert "No Sigma rules loaded" in detail, (
            f"Expected 'No Sigma rules loaded' in detail, got: {detail!r}"
        )

    def test_run_detection_with_rules_proceeds(self):
        """When load_rules_dir returns > 0, endpoint must return 200 with count."""
        with patch("backend.api.detect.SigmaMatcher") as MockMatcher:
            instance = MagicMock()
            # load_rules_dir returns 3 — simulates rules present
            instance.load_rules_dir.return_value = 3
            # run_all returns empty list (clean result, not an error)
            instance.run_all = AsyncMock(return_value=[])
            instance.save_detections = AsyncMock(return_value=None)
            MockMatcher.return_value = instance

            client = _build_client()
            response = client.post("/api/detect/run")

        assert response.status_code == 200, (
            f"Expected 200 when rules are loaded, got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert "count" in body, f"Response missing 'count' key: {body}"
        assert body["count"] == 0, f"Expected count=0 for clean run, got: {body['count']}"
