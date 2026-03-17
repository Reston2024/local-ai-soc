"""Integration tests for backend health and basic API functionality.

These tests require the backend to be running at http://localhost:8000.
Skip automatically if backend is not reachable.
"""
import pytest
import httpx


BASE_URL = "http://localhost:8000"


def backend_available() -> bool:
    """Check if backend is running."""
    try:
        httpx.get(f"{BASE_URL}/health", timeout=3.0)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not backend_available(),
    reason="Backend not running at localhost:8000"
)


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE_URL, timeout=10.0)


class TestHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_status_field(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded", "unhealthy")

    def test_health_has_components(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "components" in data
        assert isinstance(data["components"], dict)


class TestEventsAPI:
    def test_events_list_returns_200(self, client):
        resp = client.get("/api/events")
        assert resp.status_code == 200

    def test_events_list_has_pagination_fields(self, client):
        resp = client.get("/api/events")
        data = resp.json()
        assert "events" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "has_next" in data

    def test_events_list_limit_param(self, client):
        resp = client.get("/api/events?page_size=5")
        data = resp.json()
        assert len(data["events"]) <= 5


class TestDetectionsAPI:
    def test_detections_list_returns_200(self, client):
        resp = client.get("/api/detect")
        assert resp.status_code == 200

    def test_detections_has_detections_field(self, client):
        resp = client.get("/api/detect")
        data = resp.json()
        assert "detections" in data


class TestGraphAPI:
    def test_entities_returns_200(self, client):
        resp = client.get("/api/graph/entities")
        assert resp.status_code == 200

    def test_entities_has_entities_field(self, client):
        resp = client.get("/api/graph/entities")
        data = resp.json()
        assert "entities" in data


class TestOpenAPI:
    def test_openapi_json_available(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200

    def test_openapi_has_paths(self, client):
        resp = client.get("/openapi.json")
        data = resp.json()
        assert "paths" in data
        assert len(data["paths"]) >= 5


class TestTelemetryAPI:
    @pytest.mark.xfail(strict=False, reason="Telemetry endpoint added in Wave 2 (P8-T09)")
    def test_telemetry_osquery_status_returns_200(self, client):
        resp = client.get("/api/telemetry/osquery/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
