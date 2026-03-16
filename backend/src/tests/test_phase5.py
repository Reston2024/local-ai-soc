"""Phase 5 smoke tests — Suricata EVE parser, threat scoring, ATT&CK tagging, route wiring.

Wave 0 stubs: All tests are marked xfail until Phase 5 implementation plans
(01, 02, 03) are complete. Module-level imports are minimal to ensure this
file imports cleanly before implementation stubs are replaced.
"""
import pytest
from fastapi.testclient import TestClient
from backend.src.api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# TestSuricataParser
# Tests for parse_eve_line: EVE JSON -> normalized dict.
# P5: Plan 01 will implement parse_eve_line in suricata_parser.py.
# ---------------------------------------------------------------------------

class TestSuricataParser:
    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 01 not yet implemented")
    def test_parse_alert_event(self):
        """parse_eve_line must parse an alert EVE JSON into a normalized dict with severity=critical."""
        from backend.src.parsers.suricata_parser import parse_eve_line
        import json
        line = json.dumps({
            "timestamp": "2026-01-15T10:23:45.123456+0000",
            "flow_id": 1234567890,
            "event_type": "alert",
            "src_ip": "192.168.1.50",
            "src_port": 54321,
            "dest_ip": "203.0.113.100",
            "dest_port": 443,
            "proto": "TCP",
            "alert": {
                "action": "allowed",
                "gid": 1,
                "signature_id": 2016766,
                "rev": 5,
                "signature": "ET MALWARE CobaltStrike Beacon",
                "category": "Malware Command and Control Activity Detected",
                "severity": 1,
            },
            "host": "suricata-sensor",
        })
        result = parse_eve_line(line)
        assert "ET MALWARE CobaltStrike Beacon" in result.get("event_type", "") or \
               "ET MALWARE CobaltStrike Beacon" in result.get("description", ""), \
            "Result must reference the signature text"
        assert result["severity"] == "critical", \
            f"EVE severity=1 must map to 'critical', got {result.get('severity')}"
        assert result.get("dst_ip") is not None, \
            "dest_ip must be mapped to dst_ip"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 01 not yet implemented")
    def test_parse_dns_event(self):
        """parse_eve_line must map dest_ip->dst_ip and dns.rrname->query for dns events."""
        from backend.src.parsers.suricata_parser import parse_eve_line
        import json
        line = json.dumps({
            "timestamp": "2026-01-15T10:23:46.234567+0000",
            "flow_id": 1234567891,
            "event_type": "dns",
            "src_ip": "192.168.1.50",
            "src_port": 51234,
            "dest_ip": "8.8.8.8",
            "dest_port": 53,
            "proto": "UDP",
            "dns": {
                "type": "query",
                "id": 12345,
                "rrname": "suspicious-domain.test",
                "rrtype": "A",
                "tx_id": 0,
            },
            "host": "suricata-sensor",
        })
        result = parse_eve_line(line)
        assert result.get("event_type") == "dns_query", \
            f"dns EVE must normalize to event_type='dns_query', got {result.get('event_type')}"
        assert result.get("query") == "suspicious-domain.test", \
            f"dns.rrname must map to query field, got {result.get('query')}"
        assert result.get("dst_ip") is not None, \
            "dest_ip must be mapped to dst_ip"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 01 not yet implemented")
    def test_parse_flow_event(self):
        """parse_eve_line must normalize a flow EVE JSON to event_type=connection."""
        from backend.src.parsers.suricata_parser import parse_eve_line
        import json
        line = json.dumps({
            "timestamp": "2026-01-15T10:23:47.345678+0000",
            "flow_id": 1234567892,
            "event_type": "flow",
            "src_ip": "192.168.1.50",
            "src_port": 55123,
            "dest_ip": "198.51.100.1",
            "dest_port": 4444,
            "proto": "TCP",
            "flow": {
                "pkts_toserver": 10,
                "pkts_toclient": 8,
                "bytes_toserver": 1024,
                "bytes_toclient": 2048,
                "start": "2026-01-15T10:23:40.000000+0000",
                "end": "2026-01-15T10:23:47.000000+0000",
                "age": 7,
                "state": "closed",
                "reason": "timeout",
                "alerted": False,
            },
            "host": "suricata-sensor",
        })
        result = parse_eve_line(line)
        assert result.get("event_type") == "connection", \
            f"flow EVE must normalize to event_type='connection', got {result.get('event_type')}"
        assert result.get("dst_ip") is not None, \
            "dest_ip must be mapped to dst_ip"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 01 not yet implemented")
    def test_parse_http_event(self):
        """parse_eve_line must normalize an http EVE JSON to event_type=http_request."""
        from backend.src.parsers.suricata_parser import parse_eve_line
        import json
        line = json.dumps({
            "timestamp": "2026-01-15T10:23:48.456789+0000",
            "flow_id": 1234567893,
            "event_type": "http",
            "src_ip": "192.168.1.50",
            "src_port": 53456,
            "dest_ip": "203.0.113.200",
            "dest_port": 80,
            "proto": "TCP",
            "http": {
                "hostname": "malware.example",
                "url": "/stage2/payload.exe",
                "http_user_agent": "Mozilla/5.0",
                "http_method": "GET",
                "protocol": "HTTP/1.1",
                "status": 200,
                "length": 45678,
            },
            "host": "suricata-sensor",
        })
        result = parse_eve_line(line)
        assert result.get("event_type") == "http_request", \
            f"http EVE must normalize to event_type='http_request', got {result.get('event_type')}"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 01 not yet implemented")
    def test_parse_tls_event(self):
        """parse_eve_line must normalize a tls EVE JSON; tls.sni maps to query field."""
        from backend.src.parsers.suricata_parser import parse_eve_line
        import json
        line = json.dumps({
            "timestamp": "2026-01-15T10:23:49.567890+0000",
            "flow_id": 1234567894,
            "event_type": "tls",
            "src_ip": "192.168.1.50",
            "src_port": 52345,
            "dest_ip": "203.0.113.100",
            "dest_port": 443,
            "proto": "TCP",
            "tls": {
                "subject": "CN=c2.evil.test",
                "issuerdn": "CN=Fake CA",
                "serial": "01:23:45",
                "fingerprint": "aa:bb:cc:dd:ee",
                "sni": "c2.evil.test",
                "version": "TLS 1.3",
                "notbefore": "2026-01-01T00:00:00",
                "notafter": "2027-01-01T00:00:00",
            },
            "host": "suricata-sensor",
        })
        result = parse_eve_line(line)
        assert result.get("event_type") == "tls_session", \
            f"tls EVE must normalize to event_type='tls_session', got {result.get('event_type')}"
        assert result.get("query") == "c2.evil.test", \
            f"tls.sni must map to query field, got {result.get('query')}"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 01 not yet implemented")
    def test_parse_unknown_event_no_crash(self):
        """parse_eve_line must not raise for unknown event types; prefixes with 'suricata_'."""
        from backend.src.parsers.suricata_parser import parse_eve_line
        line = '{"timestamp":"2026-01-01T00:00:00Z","event_type":"fileinfo","host":"sensor"}'
        result = parse_eve_line(line)
        assert result.get("event_type", "").startswith("suricata_"), \
            f"Unknown event type must be prefixed with 'suricata_', got {result.get('event_type')}"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 01 not yet implemented")
    def test_severity_mapping(self):
        """EVE alert severity=1 must map to 'critical'; severity=4 must map to 'low'."""
        from backend.src.parsers.suricata_parser import parse_eve_line
        import json
        critical_line = json.dumps({
            "timestamp": "2026-01-15T10:00:00Z",
            "event_type": "alert",
            "src_ip": "10.0.0.1",
            "dest_ip": "10.0.0.2",
            "dest_port": 80,
            "proto": "TCP",
            "alert": {"severity": 1, "signature": "Test Critical", "signature_id": 1},
            "host": "sensor",
        })
        low_line = json.dumps({
            "timestamp": "2026-01-15T10:00:01Z",
            "event_type": "alert",
            "src_ip": "10.0.0.1",
            "dest_ip": "10.0.0.2",
            "dest_port": 80,
            "proto": "TCP",
            "alert": {"severity": 4, "signature": "Test Low", "signature_id": 2},
            "host": "sensor",
        })
        r_critical = parse_eve_line(critical_line)
        assert r_critical["severity"] == "critical", \
            f"EVE severity=1 must map to 'critical', got {r_critical.get('severity')}"
        r_low = parse_eve_line(low_line)
        assert r_low["severity"] == "low", \
            f"EVE severity=4 must map to 'low', got {r_low.get('severity')}"


# ---------------------------------------------------------------------------
# TestModels
# Tests for extended IngestSource and Alert models.
# P5: Plan 03 adds IngestSource.suricata; Plan 02 adds threat_score/attack_tags to Alert.
# ---------------------------------------------------------------------------

class TestModels:
    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 03 not yet implemented")
    def test_ingest_source_suricata(self):
        """IngestSource enum must have a 'suricata' member with value 'suricata' after Plan 03."""
        from backend.src.api.models import IngestSource
        assert IngestSource.suricata.value == "suricata", \
            "IngestSource.suricata must exist with value 'suricata'"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 02 not yet implemented")
    def test_alert_new_fields_defaults(self):
        """Alert model must have threat_score=0 and attack_tags=[] as defaults after Plan 02."""
        from backend.src.api.models import Alert
        alert = Alert(
            id="x",
            timestamp="t",
            rule="r",
            severity="info",
            event_id="e",
            description="d",
        )
        assert alert.threat_score == 0, \
            f"Alert.threat_score must default to 0, got {getattr(alert, 'threat_score', 'MISSING')}"
        assert alert.attack_tags == [], \
            f"Alert.attack_tags must default to [], got {getattr(alert, 'attack_tags', 'MISSING')}"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 03 not yet implemented")
    def test_normalized_event_accepts_suricata_source(self):
        """NormalizedEvent must accept source='suricata' once IngestSource.suricata is added."""
        from backend.src.api.models import NormalizedEvent, IngestSource
        event = NormalizedEvent(
            id="e-suricata",
            timestamp="2026-01-15T10:00:00Z",
            host="suricata-sensor",
            event_type="alert",
            severity="critical",
            source=IngestSource.suricata,
        )
        assert event.source == IngestSource.suricata, \
            f"NormalizedEvent.source must accept IngestSource.suricata, got {event.source}"


# ---------------------------------------------------------------------------
# TestThreatScorer
# Tests for score_alert: additive 0-100 threat scoring model.
# P5: Plan 02 will implement score_alert in detection/threat_scorer.py.
# ---------------------------------------------------------------------------

class TestThreatScorer:
    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 02 not yet implemented")
    def test_score_critical_suricata(self):
        """score_alert must return 40 for a critical-severity alert with no other signals."""
        from backend.src.detection.threat_scorer import score_alert
        from backend.src.api.models import Alert
        alert = Alert(
            id="test-1",
            timestamp="2026-01-15T10:00:00Z",
            rule="some-rule",
            severity="critical",
            event_id="e1",
            description="CobaltStrike Beacon",
        )
        result = score_alert(alert, [], None)
        assert result == 40, \
            f"Critical alert with no other signals must score 40, got {result}"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 02 not yet implemented")
    def test_score_sigma_hit(self):
        """score_alert must return 20 for an info-severity alert with a UUID rule (sigma hit)."""
        from backend.src.detection.threat_scorer import score_alert
        from backend.src.api.models import Alert
        alert = Alert(
            id="test-2",
            timestamp="2026-01-15T10:00:00Z",
            rule="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            severity="info",
            event_id="e2",
            description="Sigma rule fired",
        )
        result = score_alert(alert, [], None)
        assert result == 20, \
            f"Info alert with UUID rule must score 20 (sigma hit), got {result}"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 02 not yet implemented")
    def test_score_capped_at_100(self):
        """score_alert must never exceed 100 regardless of stacked signals."""
        from backend.src.detection.threat_scorer import score_alert
        from backend.src.api.models import Alert
        alert = Alert(
            id="test-3",
            timestamp="2026-01-15T10:00:00Z",
            rule="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            severity="critical",
            event_id="e3",
            description="CobaltStrike + Sigma",
        )
        # 5 events from the same host to trigger recurrence bonus (+10)
        events = [
            {"host": "victim-host", "src_ip": "192.168.1.50", "event_type": "connection"}
            for _ in range(5)
        ]
        result = score_alert(alert, events, None)
        assert result <= 100, f"Threat score must be capped at 100, got {result}"


# ---------------------------------------------------------------------------
# TestAttackMapper
# Tests for map_attack_tags: static ATT&CK tactic/technique mapping.
# P5: Plan 02 will implement map_attack_tags in detection/attack_mapper.py.
# ---------------------------------------------------------------------------

class TestAttackMapper:
    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 02 not yet implemented")
    def test_dns_query_maps_to_c2(self):
        """map_attack_tags must return C2 tactic tag for a dns_query event."""
        from backend.src.detection.attack_mapper import map_attack_tags
        from backend.src.api.models import Alert, NormalizedEvent
        event = NormalizedEvent(
            id="e10",
            timestamp="2026-01-15T10:00:00Z",
            host="victim-host",
            event_type="dns_query",
            query="suspicious-domain.test",
            dst_ip="8.8.8.8",
        )
        alert = Alert(
            id="a10",
            timestamp="2026-01-15T10:00:00Z",
            rule="some-rule",
            severity="high",
            event_id="e10",
            description="Suspicious DNS",
        )
        result = map_attack_tags(alert, event)
        assert {"tactic": "Command and Control", "technique": "T1071.004"} in result, \
            f"dns_query event must map to C2/T1071.004, got {result}"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 02 not yet implemented")
    def test_unmapped_returns_empty_list(self):
        """map_attack_tags must return [] for event types with no static mapping."""
        from backend.src.detection.attack_mapper import map_attack_tags
        from backend.src.api.models import Alert, NormalizedEvent
        event = NormalizedEvent(
            id="e11",
            timestamp="2026-01-15T10:00:00Z",
            host="victim-host",
            event_type="http_request",
            dst_ip="203.0.113.200",
        )
        alert = Alert(
            id="a11",
            timestamp="2026-01-15T10:00:00Z",
            rule="some-rule",
            severity="low",
            event_id="e11",
            description="Generic HTTP",
        )
        result = map_attack_tags(alert, event)
        assert result == [], \
            f"Unmapped event type must return empty list, got {result}"


# ---------------------------------------------------------------------------
# TestSuricataRoute
# Tests for /events and /alerts endpoints with suricata-sourced data.
# P5: Plan 03 will wire suricata source into POST /events and enrich /alerts
# with threat_score and attack_tags fields.
# ---------------------------------------------------------------------------

class TestSuricataRoute:
    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 03 not yet implemented")
    def test_ingest_suricata_source(self):
        """POST /events with source='suricata' must return 200 and be retrievable via GET /alerts."""
        payload = {
            "timestamp": "2026-01-15T10:23:45Z",
            "host": "suricata-sensor",
            "event_type": "ET MALWARE CobaltStrike Beacon",
            "severity": "critical",
            "src_ip": "192.168.1.50",
            "dst_ip": "203.0.113.100",
            "source": "suricata",
        }
        r = client.post("/events", json=payload)
        assert r.status_code == 200, \
            f"POST /events with suricata source must return 200, got {r.status_code}"
        alerts_r = client.get("/alerts")
        assert alerts_r.status_code == 200, \
            f"GET /alerts must return 200, got {alerts_r.status_code}"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 03 not yet implemented")
    def test_alerts_have_new_fields(self):
        """GET /alerts must return alerts with 'threat_score' and 'attack_tags' fields."""
        r = client.get("/alerts")
        assert r.status_code == 200, f"GET /alerts must return 200, got {r.status_code}"
        alerts = r.json()
        assert isinstance(alerts, list), "GET /alerts must return a list"
        for alert in alerts:
            assert "threat_score" in alert, \
                f"Every alert must have 'threat_score' field, missing in: {alert}"
            assert "attack_tags" in alert, \
                f"Every alert must have 'attack_tags' field, missing in: {alert}"

    @pytest.mark.xfail(strict=False, reason="Phase 5 Plan 03 not yet implemented")
    def test_high_score_for_critical_alert(self):
        """A critical-severity suricata alert must appear in /alerts with threat_score >= 40."""
        payload = {
            "timestamp": "2026-01-15T10:23:50Z",
            "host": "suricata-sensor",
            "event_type": "ET MALWARE CobaltStrike Beacon",
            "severity": "critical",
            "src_ip": "192.168.1.50",
            "dst_ip": "203.0.113.100",
            "source": "suricata",
        }
        client.post("/events", json=payload)
        r = client.get("/alerts")
        assert r.status_code == 200, f"GET /alerts must return 200, got {r.status_code}"
        alerts = r.json()
        high_score_alerts = [
            a for a in alerts
            if isinstance(a.get("threat_score"), (int, float)) and a["threat_score"] >= 40
        ]
        assert len(high_score_alerts) >= 1, \
            f"Expected at least one alert with threat_score >= 40, got scores: {[a.get('threat_score') for a in alerts]}"
