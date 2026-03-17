"""Integration smoke tests for investigation API round-trips.

Tests run against the real FastAPI app using httpx.AsyncClient.
No external services required — SQLite uses an in-process store.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def app():
    from backend.main import create_app
    return create_app()


@pytest.mark.asyncio
async def test_create_and_list_cases(app):
    """POST /api/cases then GET /api/cases — case must appear in list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/cases",
            json={"title": "Smoke Test Case", "description": "roundtrip UAT"},
        )
        assert create_resp.status_code == 200, create_resp.text
        case_id = create_resp.json()["case_id"]
        assert case_id  # non-empty

        list_resp = await client.get("/api/cases")
        assert list_resp.status_code == 200, list_resp.text
        ids = [c["case_id"] for c in list_resp.json()["cases"]]
        assert case_id in ids, f"case_id {case_id!r} not found in {ids}"


@pytest.mark.asyncio
async def test_hunt_accepts_template_id(app):
    """POST /api/hunt with template_id field returns 200, not 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/hunt",
            json={"template_id": "suspicious_ip_comms", "params": {"target_ip": "1.2.3.4"}},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "result_count" in body
        assert "results" in body
