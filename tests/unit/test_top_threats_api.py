"""Unit test stubs for Phase 9 GET /api/top-threats endpoint.

Tests P9-T06 (top-threats returns 200, list, respects limit param).
Wave 0: all stubs are xfail.
Plan 04 will implement backend/api/top_threats.py and wire into main.py.
"""
import pytest

pytestmark = pytest.mark.unit


class TestTopThreatsEndpoint:
    @pytest.mark.xfail(reason="P9-T06: GET /api/top-threats endpoint not yet implemented")
    def test_get_top_threats_returns_200(self):
        from fastapi.testclient import TestClient

        from backend.main import create_app
        app = create_app()
        client = TestClient(app)
        resp = client.get("/api/top-threats")
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="P9-T06: GET /api/top-threats returns list")
    def test_get_top_threats_returns_list(self):
        from fastapi.testclient import TestClient

        from backend.main import create_app
        app = create_app()
        client = TestClient(app)
        resp = client.get("/api/top-threats")
        body = resp.json()
        assert "threats" in body
        assert isinstance(body["threats"], list)

    @pytest.mark.xfail(reason="P9-T06: GET /api/top-threats respects ?limit= query param")
    def test_get_top_threats_limit_param(self):
        from fastapi.testclient import TestClient

        from backend.main import create_app
        app = create_app()
        client = TestClient(app)
        resp = client.get("/api/top-threats?limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body.get("threats", [])) <= 5
