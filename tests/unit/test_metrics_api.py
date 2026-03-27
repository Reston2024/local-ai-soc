"""
Unit tests for GET /api/metrics/kpis endpoint.

Tests P13-T04 / P13-T05 behaviors:
- 200 response with all 9 KPI fields
- computed_at is a valid ISO datetime
- Caching: second call does not trigger additional MetricsService.compute_all_kpis() invocations
- Endpoint accessible at /api/metrics/kpis
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_snapshot():
    """Build a minimal KpiSnapshot-like object / dict for mocking."""
    from backend.services.metrics_service import KpiSnapshot, KpiValue

    return KpiSnapshot(
        computed_at=datetime(2026, 3, 27, 12, 0, 0, tzinfo=timezone.utc),
        mttd=KpiValue(label="MTTD", value=5.0, unit="min"),
        mttr=KpiValue(label="MTTR", value=10.0, unit="min"),
        mttc=KpiValue(label="MTTC", value=15.0, unit="min"),
        false_positive_rate=KpiValue(label="False Positive Rate", value=0.12, unit="%"),
        alert_volume_24h=KpiValue(label="Alert Volume 24h", value=42.0, unit="count"),
        active_rules=KpiValue(label="Active Rules", value=7.0, unit="count"),
        open_cases=KpiValue(label="Open Cases", value=3.0, unit="count"),
        assets_monitored=KpiValue(label="Assets Monitored", value=20.0, unit="count"),
        log_sources=KpiValue(label="Log Sources", value=5.0, unit="count"),
    )


def _build_client():
    """Create a TestClient with a mock stores dependency injected."""
    from fastapi.testclient import TestClient

    from backend.main import create_app

    # We need stores on app.state for the dependency to resolve
    app = create_app()

    # Patch app.state.stores with a MagicMock after creation
    mock_stores = MagicMock()
    app.state.stores = mock_stores
    # Also patch settings (needed by verify_token)
    from backend.core.config import Settings
    app.state.settings = Settings()

    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetKpisEndpoint:
    def test_get_kpis_returns_200(self):
        """GET /api/metrics/kpis must return HTTP 200."""
        from fastapi.testclient import TestClient

        from backend.main import create_app

        app = create_app()
        app.state.stores = MagicMock()
        app.state.settings = __import__("backend.core.config", fromlist=["Settings"]).Settings()

        snapshot = _make_fake_snapshot()

        with patch(
            "backend.api.metrics.MetricsService",
        ) as MockSvc, patch(
            "backend.api.metrics._kpi_cache",
            new=None,
        ), patch(
            "backend.api.metrics._scheduler",
            new=None,
        ):
            mock_instance = AsyncMock()
            mock_instance.compute_all_kpis = AsyncMock(return_value=snapshot)
            MockSvc.return_value = mock_instance

            client = TestClient(app)
            resp = client.get(
                "/api/metrics/kpis",
                headers={"Authorization": "Bearer test"},
            )

        assert resp.status_code == 200

    def test_response_contains_all_kpi_fields(self):
        """Response body must contain all 9 KPI keys + computed_at."""
        from fastapi.testclient import TestClient

        from backend.main import create_app

        app = create_app()
        app.state.stores = MagicMock()
        app.state.settings = __import__("backend.core.config", fromlist=["Settings"]).Settings()

        snapshot = _make_fake_snapshot()

        with patch("backend.api.metrics.MetricsService") as MockSvc, patch(
            "backend.api.metrics._kpi_cache", new=None
        ), patch("backend.api.metrics._scheduler", new=None):
            mock_instance = AsyncMock()
            mock_instance.compute_all_kpis = AsyncMock(return_value=snapshot)
            MockSvc.return_value = mock_instance

            client = TestClient(app)
            resp = client.get(
                "/api/metrics/kpis",
                headers={"Authorization": "Bearer test"},
            )

        assert resp.status_code == 200
        body = resp.json()
        required_keys = {
            "mttd", "mttr", "mttc", "false_positive_rate",
            "alert_volume_24h", "active_rules", "open_cases",
            "assets_monitored", "log_sources", "computed_at",
        }
        for key in required_keys:
            assert key in body, f"Missing key: {key}"

    def test_computed_at_is_valid_iso_datetime(self):
        """computed_at in the response must be a parseable ISO datetime string."""
        from fastapi.testclient import TestClient

        from backend.main import create_app

        app = create_app()
        app.state.stores = MagicMock()
        app.state.settings = __import__("backend.core.config", fromlist=["Settings"]).Settings()

        snapshot = _make_fake_snapshot()

        with patch("backend.api.metrics.MetricsService") as MockSvc, patch(
            "backend.api.metrics._kpi_cache", new=None
        ), patch("backend.api.metrics._scheduler", new=None):
            mock_instance = AsyncMock()
            mock_instance.compute_all_kpis = AsyncMock(return_value=snapshot)
            MockSvc.return_value = mock_instance

            client = TestClient(app)
            resp = client.get(
                "/api/metrics/kpis",
                headers={"Authorization": "Bearer test"},
            )

        body = resp.json()
        # Should not raise
        parsed = datetime.fromisoformat(body["computed_at"].replace("Z", "+00:00"))
        assert isinstance(parsed, datetime)

    def test_endpoint_accessible_at_api_metrics_kpis(self):
        """The route must be registered at /api/metrics/kpis (not /metrics/kpis)."""
        from fastapi.testclient import TestClient

        from backend.main import create_app

        app = create_app()
        app.state.stores = MagicMock()
        app.state.settings = __import__("backend.core.config", fromlist=["Settings"]).Settings()

        snapshot = _make_fake_snapshot()

        with patch("backend.api.metrics.MetricsService") as MockSvc, patch(
            "backend.api.metrics._kpi_cache", new=None
        ), patch("backend.api.metrics._scheduler", new=None):
            mock_instance = AsyncMock()
            mock_instance.compute_all_kpis = AsyncMock(return_value=snapshot)
            MockSvc.return_value = mock_instance

            client = TestClient(app)
            # The /api prefix is added by main.py's router mount
            resp_correct = client.get(
                "/api/metrics/kpis",
                headers={"Authorization": "Bearer test"},
            )
            resp_wrong = client.get(
                "/metrics/kpis",
                headers={"Authorization": "Bearer test"},
            )

        assert resp_correct.status_code == 200
        assert resp_wrong.status_code == 404

    def test_cached_value_returned_on_second_call(self):
        """
        When cache is pre-populated, GET /api/metrics/kpis must return the
        cached value without invoking MetricsService.compute_all_kpis() again.
        """
        from fastapi.testclient import TestClient

        from backend.main import create_app

        app = create_app()
        app.state.stores = MagicMock()
        app.state.settings = __import__("backend.core.config", fromlist=["Settings"]).Settings()

        snapshot = _make_fake_snapshot()

        with patch("backend.api.metrics.MetricsService") as MockSvc, patch(
            "backend.api.metrics._kpi_cache", new=snapshot
        ), patch("backend.api.metrics._scheduler") as mock_sched:
            # _scheduler already set — won't be re-created
            mock_sched.__bool__ = lambda s: True

            mock_instance = AsyncMock()
            mock_instance.compute_all_kpis = AsyncMock(return_value=snapshot)
            MockSvc.return_value = mock_instance

            client = TestClient(app)
            resp = client.get(
                "/api/metrics/kpis",
                headers={"Authorization": "Bearer test"},
            )

        assert resp.status_code == 200
        # compute_all_kpis should NOT have been called because cache was warm
        mock_instance.compute_all_kpis.assert_not_called()
