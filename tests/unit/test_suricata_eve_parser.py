"""Unit tests for SuricataEveParser — Phase 23 P23-T02.

Wave 0: all tests pre-skipped. Wave 1 (23-02-PLAN.md) activates them.
"""
from __future__ import annotations

import pytest

try:
    from ingestion.parsers.suricata_eve_parser import SuricataEveParser
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(not _IMPORT_OK, reason="SuricataEveParser not implemented — Wave 1")

FIXTURE_EVE = "fixtures/suricata_eve_sample.ndjson"


class TestSuricataSeverityMapping:
    """P23-T02: alert.severity 1=critical, 2=high, 3=medium, 4=low."""

    @pytest.mark.skip(reason="not implemented — Wave 1")
    def test_severity_mapping(self):
        parser = SuricataEveParser()
        events = list(parser.parse(FIXTURE_EVE))
        alert_events = [e for e in events if e.event_type in ("network_connect", "detection")]
        assert len(alert_events) >= 1
        # Severity must be one of the four valid values
        valid = {"critical", "high", "medium", "low", "info"}
        for e in alert_events:
            assert e.severity in valid


class TestSuricataMITREExtraction:
    """P23-T02: MITRE ATT&CK tactic/technique extracted from alert.metadata."""

    @pytest.mark.skip(reason="not implemented — Wave 1")
    def test_mitre_metadata_extracted(self):
        import json
        # Build a synthetic alert record with MITRE metadata
        record = {
            "timestamp": "2024-01-15T10:00:00.000000+0000",
            "event_type": "alert",
            "src_ip": "10.0.0.1",
            "dest_ip": "10.0.0.2",
            "proto": "TCP",
            "alert": {
                "action": "blocked",
                "signature_id": 2100498,
                "signature": "ET MALWARE Test",
                "category": "Malware",
                "severity": 1,
                "metadata": {
                    "mitre_attack_id": ["T1071.001"],
                    "mitre_tactic_name": ["Command and Control"],
                },
            },
        }
        parser = SuricataEveParser()
        event = parser.parse_record(record)
        assert event is not None
        assert event.attack_technique == "T1071.001"
        assert event.attack_tactic == "Command and Control"


class TestSuricataDnsHttpFlow:
    """P23-T02: dns, http, and flow event types parse without crashing."""

    @pytest.mark.skip(reason="not implemented — Wave 1")
    def test_dns_flow_http_parsed(self):
        parser = SuricataEveParser()
        events = list(parser.parse(FIXTURE_EVE))
        types = {e.event_type for e in events}
        # Fixture contains at least one of these
        assert len(types) >= 1


class TestSuricataDestIpMapping:
    """P23-T02: EVE dest_ip maps to NormalizedEvent.dst_ip."""

    @pytest.mark.skip(reason="not implemented — Wave 1")
    def test_dest_ip_mapped(self):
        record = {
            "timestamp": "2024-01-15T10:00:00.000000+0000",
            "event_type": "flow",
            "src_ip": "192.168.1.5",
            "dest_ip": "8.8.8.8",
            "src_port": 54321,
            "dest_port": 80,
            "proto": "TCP",
            "flow": {"state": "closed"},
        }
        parser = SuricataEveParser()
        event = parser.parse_record(record)
        assert event is not None
        assert event.dst_ip == "8.8.8.8"
        assert event.src_ip == "192.168.1.5"
