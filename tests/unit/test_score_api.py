"""Unit test stubs for Phase 9 POST /api/score endpoint.

Tests P9-T04 (score endpoint returns 200, structured JSON).
Wave 0: all stubs are xfail.
Plan 03 will implement backend/api/score.py and wire into main.py.
"""
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


class TestScoreEndpoint:
    @pytest.mark.xfail(reason="P9-T04: POST /api/score endpoint not yet implemented")
    def test_post_score_returns_200(self):
        from fastapi.testclient import TestClient

        from backend.main import create_app
        app = create_app()
        client = TestClient(app)
        with patch("backend.api.score.score_entity", return_value=75):
            resp = client.post("/api/score", json={"detection_id": "det-001"})
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="P9-T04: POST /api/score returns structured JSON with scored_entities")
    def test_post_score_returns_scored_entities(self):
        from fastapi.testclient import TestClient

        from backend.main import create_app
        app = create_app()
        client = TestClient(app)
        resp = client.post("/api/score", json={"event_ids": []})
        assert resp.status_code == 200
        body = resp.json()
        assert "scored_entities" in body

    @pytest.mark.xfail(reason="P9-T04: POST /api/score returns 200 not 404/500 on missing data")
    def test_post_score_graceful_empty(self):
        from fastapi.testclient import TestClient

        from backend.main import create_app
        app = create_app()
        client = TestClient(app)
        resp = client.post("/api/score", json={})
        assert resp.status_code == 200
