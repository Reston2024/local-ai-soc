"""Unit test stubs for Phase 9 POST /api/explain endpoint.

Tests P9-T05 (explain endpoint returns 200, structured sections, graceful Ollama error).
Wave 0: all stubs are xfail.
Plan 05 will implement backend/api/explain.py and wire into main.py.
"""
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


class TestExplainEndpoint:
    @pytest.mark.xfail(reason="P9-T05: POST /api/explain endpoint not yet implemented")
    def test_post_explain_returns_200(self):
        from fastapi.testclient import TestClient

        from backend.main import create_app
        app = create_app()
        client = TestClient(app)
        resp = client.post("/api/explain", json={"detection_id": "det-001"})
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="P9-T05: POST /api/explain returns three structured sections")
    def test_post_explain_returns_sections(self):
        from fastapi.testclient import TestClient

        from backend.main import create_app
        app = create_app()
        client = TestClient(app)
        resp = client.post("/api/explain", json={"detection_id": "det-001"})
        assert resp.status_code == 200
        body = resp.json()
        assert "what_happened" in body or "explanation" in body

    @pytest.mark.xfail(reason="P9-T05: POST /api/explain returns 200 not 500 when Ollama unavailable")
    def test_post_explain_graceful_ollama_error(self):
        from fastapi.testclient import TestClient

        from backend.main import create_app
        app = create_app()
        client = TestClient(app)
        with patch("backend.intelligence.explain_engine.generate_explanation",
                   side_effect=Exception("Ollama offline")):
            resp = client.post("/api/explain", json={"detection_id": "det-001"})
        assert resp.status_code == 200
