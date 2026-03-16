"""Phase 3 smoke tests — OpenSearch activation, search endpoint, Sigma detection.

Wave 0 stubs: These tests FAIL until Phase 3 implementation plans (02 and 03) are complete.
Tests referencing sigma_loader are SKIPPED when the module is absent (pytest.importorskip
is called inside each test method so only those tests skip, not the whole file).
"""
import re
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.src.api.main import app
from backend.src.api.models import NormalizedEvent

client = TestClient(app)

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# TestOpenSearch
# Tests for unconditional opensearch_sink.try_index behavior.
# P3-T8: try_index must attempt HTTP PUT when OPENSEARCH_URL is configured.
# ---------------------------------------------------------------------------

class TestOpenSearch:
    def test_try_index_attempts_http_when_url_set(self):
        """P3-T8: try_index must attempt HTTP PUT when OPENSEARCH_URL is configured."""
        import backend.src.ingestion.opensearch_sink as sink

        # Save and restore module-level OPENSEARCH_URL (read at import time)
        original_url = sink.OPENSEARCH_URL
        sink.OPENSEARCH_URL = "http://localhost:9200"
        try:
            with patch.object(sink, "_get_client") as mock_get_client:
                mock_http = MagicMock()
                mock_http.put.return_value = MagicMock(status_code=201)
                mock_get_client.return_value = mock_http
                event = NormalizedEvent(
                    id="test-opensearch-1",
                    timestamp="2026-03-15T00:00:00Z",
                    host="testhost",
                    event_type="dns",
                )
                result = sink.try_index(event)
                assert result is True
                mock_http.put.assert_called_once()
        finally:
            sink.OPENSEARCH_URL = original_url


# ---------------------------------------------------------------------------
# TestSearchRoute
# Tests for GET /search?q= endpoint.
# P3-T1: /search?q=suspicious returns list (possibly empty — no OS running)
# P3-T2: /search with no q param returns []
# ---------------------------------------------------------------------------

class TestSearchRoute:
    def test_search_with_query_returns_list(self):
        """P3-T1: GET /search?q=suspicious must return 200 with a list payload."""
        r = client.get("/search", params={"q": "suspicious"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_search_with_empty_query_returns_empty_list(self):
        """P3-T2: GET /search with empty q must return []."""
        r = client.get("/search", params={"q": ""})
        assert r.status_code == 200
        assert r.json() == []

    def test_search_without_q_param_returns_empty_list(self):
        """P3-T2 variant: GET /search with no q param at all must return []."""
        r = client.get("/search")
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# TestSigmaLoader
# Tests for sigma_loader.load_sigma_rules().
# P3-T3: load_sigma_rules() returns list with >= 1 callable
# P3-T4: sigma dns callable fires an Alert for event with query="suspicious-domain.test"
# P3-T5: alert.rule == UUID from suspicious_dns.yml id field
# ---------------------------------------------------------------------------

class TestSigmaLoader:
    def test_load_sigma_rules_returns_nonempty_list(self):
        """P3-T3: load_sigma_rules() must return a list with at least 1 callable."""
        sigma_loader = pytest.importorskip(
            "backend.src.detection.sigma_loader",
            reason="sigma_loader not yet implemented — Wave 1 Plan 03",
        )
        rules = sigma_loader.load_sigma_rules()
        assert isinstance(rules, list)
        assert len(rules) >= 1

    def test_sigma_dns_rule_fires_on_suspicious_query(self):
        """P3-T4: The sigma dns callable fires an Alert for suspicious query."""
        sigma_loader = pytest.importorskip(
            "backend.src.detection.sigma_loader",
            reason="sigma_loader not yet implemented — Wave 1 Plan 03",
        )
        rules = sigma_loader.load_sigma_rules()
        event = NormalizedEvent(
            id="test-sigma-1",
            timestamp="2026-03-15T12:00:00Z",
            host="testhost",
            event_type="dns",
            query="suspicious-domain.test",
        )
        fired_alerts = []
        for rule_fn in rules:
            result = rule_fn(event)
            if result:
                if isinstance(result, list):
                    fired_alerts.extend(result)
                else:
                    fired_alerts.append(result)
        assert len(fired_alerts) >= 1, (
            "Expected at least one Alert from the suspicious_dns sigma rule"
        )

    def test_sigma_alert_rule_field_is_uuid(self):
        """P3-T5: The alert from P3-T4 has rule field matching the UUID from suspicious_dns.yml."""
        sigma_loader = pytest.importorskip(
            "backend.src.detection.sigma_loader",
            reason="sigma_loader not yet implemented — Wave 1 Plan 03",
        )
        rules = sigma_loader.load_sigma_rules()
        event = NormalizedEvent(
            id="test-sigma-2",
            timestamp="2026-03-15T12:00:00Z",
            host="testhost",
            event_type="dns",
            query="suspicious-domain.test",
        )
        fired_alerts = []
        for rule_fn in rules:
            result = rule_fn(event)
            if result:
                if isinstance(result, list):
                    fired_alerts.extend(result)
                else:
                    fired_alerts.append(result)
        assert len(fired_alerts) >= 1, "No alerts fired — cannot verify rule UUID field"
        alert = fired_alerts[0]
        assert hasattr(alert, "rule"), "Alert must have a 'rule' field"
        assert _UUID_PATTERN.match(alert.rule), (
            f"alert.rule must be a UUID string, got: {alert.rule!r}"
        )


# ---------------------------------------------------------------------------
# TestSigmaDetection
# Tests for Sigma-produced alerts visible via GET /alerts.
# P3-T6: POST event with suspicious query → GET /alerts contains sigma-sourced alert
# ---------------------------------------------------------------------------

class TestSigmaDetection:
    def test_post_suspicious_event_produces_sigma_alert(self):
        """P3-T6: POST event with suspicious DNS query → GET /alerts has UUID-rule alert."""
        pytest.importorskip(
            "backend.src.detection.sigma_loader",
            reason="sigma_loader not yet implemented — Wave 1 Plan 03",
        )
        payload = {
            "timestamp": "2026-03-15T12:00:00Z",
            "host": "sigma-test-host",
            "event": "dns",
            "query": "suspicious-domain.test",
        }
        client.post("/events", json=payload)
        r = client.get("/alerts")
        assert r.status_code == 200
        alerts = r.json()
        uuid_alerts = [
            a for a in alerts
            if _UUID_PATTERN.match(a.get("rule", ""))
        ]
        assert len(uuid_alerts) >= 1, (
            "Expected at least one alert with a UUID rule field from Sigma detection"
        )


# ---------------------------------------------------------------------------
# TestSigmaAlerts
# Integration alias: verifies /alerts contains sigma-sourced alert after ingest.
# P3-T6 duplicate hook for completeness.
# ---------------------------------------------------------------------------

class TestSigmaAlerts:
    def test_ingest_then_alerts_contains_sigma_rule(self):
        """P3-T6 alias: ingest suspicious event via /ingest → sigma alert in /alerts."""
        pytest.importorskip(
            "backend.src.detection.sigma_loader",
            reason="sigma_loader not yet implemented — Wave 1 Plan 03",
        )
        payload = {
            "source": "api",
            "events": [
                {
                    "timestamp": "2026-03-15T12:30:00Z",
                    "host": "sigma-ingest-host",
                    "event": "dns",
                    "query": "suspicious-domain.test",
                }
            ],
        }
        client.post("/ingest", json=payload)
        r = client.get("/alerts")
        assert r.status_code == 200
        alerts = r.json()
        uuid_alerts = [
            a for a in alerts
            if _UUID_PATTERN.match(a.get("rule", ""))
        ]
        assert len(uuid_alerts) >= 1, (
            "Expected at least one sigma-sourced alert (UUID rule) after ingest"
        )
