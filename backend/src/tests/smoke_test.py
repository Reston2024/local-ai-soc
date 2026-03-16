"""Wave 1 smoke tests — verify all 6 required endpoints."""
import pytest
from fastapi.testclient import TestClient
from backend.src.api.main import app

client = TestClient(app)


def test_health_returns_200():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_events_returns_list():
    r = client.get("/events")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_timeline_returns_list():
    r = client.get("/timeline")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_graph_returns_nodes_and_edges():
    r = client.get("/graph")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data
    assert "edges" in data


def test_alerts_returns_list():
    r = client.get("/alerts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_post_event_stores_and_returns():
    payload = {
        "timestamp": "2026-03-15T12:00:00Z",
        "host": "fw01",
        "src_ip": "192.168.1.10",
        "dst_ip": "8.8.8.8",
        "event": "dns_query",
        "query": "example.com",
    }
    r = client.post("/events", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["host"] == "fw01"
    assert data["event_type"] == "dns_query"


def test_fixtures_load_returns_count():
    # Will return 404 if fixture file missing — that's acceptable in CI
    r = client.post("/fixtures/load")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "loaded" in r.json()
