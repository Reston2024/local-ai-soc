"""Phase 2 smoke tests — ingestion pipeline, enrichment, detection, SSE."""
import pytest
from fastapi.testclient import TestClient
from backend.src.api.main import app

client = TestClient(app)


# ── Syslog parser ───────────────────────────────────────────────────────────

class TestSyslogParser:
    def test_parse_rfc3164(self):
        from backend.src.ingestion.syslog_parser import parse_rfc3164
        line = "<34>Mar 15 12:00:00 fw01 connection established from 192.168.1.10"
        result = parse_rfc3164(line)
        assert result is not None
        assert result["host"] == "fw01"
        assert result["event"] == "connection"
        assert result["raw_format"] == "rfc3164"

    def test_parse_rfc5424(self):
        from backend.src.ingestion.syslog_parser import parse_rfc5424
        line = "<165>1 2026-03-15T12:00:00Z fw01 sshd 1234 - - Failed password for root"
        result = parse_rfc5424(line)
        assert result is not None
        assert result["host"] == "fw01"
        assert result["event"] == "auth"
        assert result["raw_format"] == "rfc5424"

    def test_parse_cef(self):
        from backend.src.ingestion.syslog_parser import parse_cef
        line = "CEF:0|PAN|PAN-OS|10.1|threat|Suspicious DNS|7|src=192.168.1.10 dst=9.9.9.9 dpt=53"
        result = parse_cef(line)
        assert result is not None
        assert result["src"] == "192.168.1.10"
        assert result["dst"] == "9.9.9.9"
        assert result["severity"] == "high"
        assert result["raw_format"] == "cef"

    def test_parse_syslog_line_router_picks_rfc5424(self):
        from backend.src.ingestion.syslog_parser import parse_syslog_line
        line = "<165>1 2026-03-15T12:00:00Z host01 app 42 - - some message"
        result = parse_syslog_line(line)
        assert result["raw_format"] == "rfc5424"

    def test_parse_syslog_line_fallback(self):
        from backend.src.ingestion.syslog_parser import parse_syslog_line
        result = parse_syslog_line("just a plain log message with no priority")
        assert result["event"] == "unknown"
        assert result["raw_format"] == "unknown"


# ── Enricher ────────────────────────────────────────────────────────────────

class TestEnricher:
    def _make_event(self, **kwargs):
        from backend.src.api.models import NormalizedEvent
        defaults = dict(id="test", timestamp="2026-03-15T12:00:00Z",
                        host="fw01", event_type="dns_query")
        defaults.update(kwargs)
        return NormalizedEvent(**defaults)

    def test_suspicious_dns_enrichment(self):
        from backend.src.ingestion.enricher import enrich
        ev = self._make_event(query="suspicious-domain.test")
        enrich(ev)
        assert "suspicious_dns" in ev.enrichments

    def test_suspicious_ip_enrichment(self):
        from backend.src.ingestion.enricher import enrich
        ev = self._make_event(event_type="connection", dst_ip="9.9.9.9")
        enrich(ev)
        assert "suspicious_dst_ip" in ev.enrichments

    def test_suspicious_port_enrichment(self):
        from backend.src.ingestion.enricher import enrich
        ev = self._make_event(event_type="connection", port=4444)
        enrich(ev)
        assert "suspicious_port:4444" in ev.enrichments

    def test_private_src_tag(self):
        from backend.src.ingestion.enricher import enrich
        ev = self._make_event(src_ip="192.168.1.10")
        enrich(ev)
        assert "src_private" in ev.enrichments

    def test_external_dst_tag(self):
        from backend.src.ingestion.enricher import enrich
        ev = self._make_event(dst_ip="8.8.8.8")
        enrich(ev)
        assert "dst_external" in ev.enrichments

    def test_no_false_positives_on_benign_event(self):
        from backend.src.ingestion.enricher import enrich
        ev = self._make_event(event_type="connection",
                              src_ip="192.168.1.10", dst_ip="192.168.1.1", port=443)
        enrich(ev)
        assert "suspicious_dns" not in ev.enrichments
        assert "suspicious_dst_ip" not in ev.enrichments
        assert "suspicious_port:443" not in ev.enrichments


# ── Detection rules ─────────────────────────────────────────────────────────

class TestDetectionRules:
    def _event_with_enrichments(self, enrichments: list[str], **kwargs):
        from backend.src.api.models import NormalizedEvent
        defaults = dict(id="test", timestamp="2026-03-15T12:00:00Z",
                        host="fw01", event_type="connection",
                        enrichments=enrichments)
        defaults.update(kwargs)
        return NormalizedEvent(**defaults)

    def test_suspicious_dns_fires_alert(self):
        from backend.src.detection.rules import evaluate
        ev = self._event_with_enrichments(["suspicious_dns"], query="suspicious-domain.test")
        alerts = evaluate(ev)
        rules = [a.rule for a in alerts]
        assert "suspicious_dns_query" in rules

    def test_suspicious_outbound_fires_alert(self):
        from backend.src.detection.rules import evaluate
        ev = self._event_with_enrichments(["suspicious_dst_ip"], dst_ip="9.9.9.9")
        alerts = evaluate(ev)
        assert any(a.rule == "suspicious_outbound_connection" for a in alerts)

    def test_suspicious_port_fires_alert(self):
        from backend.src.detection.rules import evaluate
        ev = self._event_with_enrichments(["suspicious_port:4444"])
        alerts = evaluate(ev)
        assert any(a.rule == "suspicious_port" for a in alerts)

    def test_benign_event_no_alerts(self):
        from backend.src.detection.rules import evaluate
        ev = self._event_with_enrichments(["src_private", "dst_external"])
        alerts = evaluate(ev)
        # dst_external + src_private alone should not fire
        assert len(alerts) == 0


# ── API endpoints ───────────────────────────────────────────────────────────

class TestPhase2Routes:
    def test_health_returns_ingestion_sources(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "ingestion_sources" in data
        assert isinstance(data["ingestion_sources"], list)

    def test_post_ingest_batch(self):
        payload = {
            "source": "api",
            "events": [
                {"timestamp": "2026-03-15T13:00:00Z", "host": "ingest-test",
                 "src_ip": "10.0.0.1", "dst_ip": "8.8.8.8",
                 "event": "connection", "port": 443},
                {"timestamp": "2026-03-15T13:00:01Z", "host": "ingest-test",
                 "src_ip": "10.0.0.1", "dst_ip": "9.9.9.9",
                 "event": "connection", "port": 4444},
            ]
        }
        r = client.post("/ingest", json=payload)
        assert r.status_code == 202
        data = r.json()
        assert data["accepted"] == 2
        assert data["source"] == "api"
        # 9.9.9.9 + port 4444 should both fire
        assert data["alerts"] >= 1

    def test_post_ingest_syslog_rfc3164(self):
        line = "<34>Mar 15 12:00:00 fw01 connection established from 192.168.1.10"
        r = client.post("/ingest/syslog",
                        content=line.encode(),
                        headers={"Content-Type": "text/plain"})
        assert r.status_code == 202
        data = r.json()
        assert data["accepted"] == 1
        assert "event_id" in data

    def test_post_ingest_syslog_cef(self):
        line = "CEF:0|PAN|PAN-OS|10|threat|SuspiciousDNS|8|src=10.0.0.5 dst=9.9.9.9 dpt=53"
        r = client.post("/ingest/syslog",
                        content=line.encode(),
                        headers={"Content-Type": "text/plain"})
        assert r.status_code == 202
        data = r.json()
        assert data["accepted"] == 1
        # high-severity CEF targeting suspicious IP should alert
        assert data["alerts"] >= 1

    def test_events_reflect_ingested(self):
        """Events from /ingest must appear in /events."""
        # Ingest one unique event
        r = client.post("/ingest", json={
            "source": "vector",
            "events": [{"timestamp": "2026-03-15T14:00:00Z",
                        "host": "vector-relay", "event": "dns_query",
                        "query": "example.com"}]
        })
        assert r.status_code == 202
        events = client.get("/events").json()
        hosts = [e["host"] for e in events]
        assert "vector-relay" in hosts

    def test_source_label_preserved(self):
        """Events ingested via /ingest must carry the correct source label."""
        client.post("/ingest", json={
            "source": "syslog",
            "events": [{"timestamp": "2026-03-15T14:30:00Z",
                        "host": "syslog-test", "event": "auth"}]
        })
        events = client.get("/events").json()
        syslog_events = [e for e in events if e.get("host") == "syslog-test"]
        assert len(syslog_events) >= 1
        assert syslog_events[0]["source"] == "syslog"

    def test_ingest_source_appears_in_health(self):
        """After ingesting, /health.ingestion_sources must list the source."""
        client.post("/ingest", json={
            "source": "fixture",
            "events": [{"timestamp": "2026-03-15T15:00:00Z",
                        "host": "health-check-host", "event": "connection"}]
        })
        r = client.get("/health")
        assert "fixture" in r.json()["ingestion_sources"]

    def test_graph_includes_ingested_hosts(self):
        """Hosts from ingested events must appear as graph nodes."""
        client.post("/ingest", json={
            "source": "api",
            "events": [{"timestamp": "2026-03-15T15:30:00Z",
                        "host": "graph-test-host", "dst_ip": "1.2.3.4",
                        "event": "connection"}]
        })
        graph = client.get("/graph").json()
        node_labels = [n["label"] for n in graph["nodes"]]
        assert "graph-test-host" in node_labels

    def test_timeline_sorted_ascending(self):
        """GET /timeline must return events in ascending timestamp order."""
        timeline = client.get("/timeline").json()
        if len(timeline) >= 2:
            times = [e["timestamp"] for e in timeline if e.get("timestamp")]
            assert times == sorted(times)

    def test_post_ingest_empty_events_accepted(self):
        """Empty events list must return 202 with accepted=0."""
        r = client.post("/ingest", json={"source": "api", "events": []})
        assert r.status_code == 202
        assert r.json()["accepted"] == 0
