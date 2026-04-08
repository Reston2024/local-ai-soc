"""Stub tests for Phase 27 Malcolm field normalization (P27-T02). Activated in plan 27-03."""
from __future__ import annotations

import pytest

try:
    from ingestion.jobs.malcolm_collector import MalcolmCollector
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

# Normalization methods (_normalize_alert, _normalize_syslog) are stubs in plan 27-02.
# They are fully implemented in plan 27-03. This flag keeps the normalizer tests skipped
# until plan 27-03 removes this guard and sets it to True.
_NORMALIZER_IMPLEMENTED = False

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK or not _NORMALIZER_IMPLEMENTED,
    reason="Malcolm normalizer methods not implemented — Wave 3 (plan 27-03)",
)


def test_normalize_alert_extracts_src_ip():
    """_normalize_alert() extracts source.ip (ECS) with fallback to src_ip (flat)
    from doc, returns NormalizedEvent with source_type='suricata_eve'."""
    collector = MalcolmCollector()

    # ECS-style doc
    doc_ecs = {"source": {"ip": "10.0.0.1"}, "destination": {"ip": "8.8.8.8"}}
    event = collector._normalize_alert(doc_ecs)
    assert event is not None
    assert event.source_ip == "10.0.0.1"
    assert event.source_type == "suricata_eve"

    # Flat-style fallback
    doc_flat = {"src_ip": "192.168.1.5", "dst_ip": "1.1.1.1"}
    event_flat = collector._normalize_alert(doc_flat)
    assert event_flat is not None
    assert event_flat.source_ip == "192.168.1.5"


def test_normalize_alert_extracts_dst_ip():
    """_normalize_alert() extracts destination.ip with fallback to dst_ip."""
    collector = MalcolmCollector()

    doc_ecs = {"source": {"ip": "10.0.0.2"}, "destination": {"ip": "93.184.216.34"}}
    event = collector._normalize_alert(doc_ecs)
    assert event is not None
    assert event.dest_ip == "93.184.216.34"

    doc_flat = {"src_ip": "10.0.0.3", "dst_ip": "172.16.0.1"}
    event_flat = collector._normalize_alert(doc_flat)
    assert event_flat is not None
    assert event_flat.dest_ip == "172.16.0.1"


def test_normalize_alert_severity_mapping():
    """event.severity or alert.severity becomes NormalizedEvent.severity."""
    collector = MalcolmCollector()

    doc_event_sev = {
        "source": {"ip": "10.0.0.1"},
        "destination": {"ip": "8.8.8.8"},
        "event": {"severity": 3},
    }
    event = collector._normalize_alert(doc_event_sev)
    assert event is not None
    assert event.severity == 3

    doc_alert_sev = {
        "source": {"ip": "10.0.0.1"},
        "destination": {"ip": "8.8.8.8"},
        "alert": {"severity": 2, "signature": "ET SCAN"},
    }
    event2 = collector._normalize_alert(doc_alert_sev)
    assert event2 is not None
    assert event2.severity == 2


def test_normalize_alert_detection_source():
    """rule.name or alert.signature becomes NormalizedEvent.detection_source."""
    collector = MalcolmCollector()

    doc_rule = {
        "source": {"ip": "10.0.0.1"},
        "destination": {"ip": "8.8.8.8"},
        "rule": {"name": "ET POLICY RDP"},
    }
    event = collector._normalize_alert(doc_rule)
    assert event is not None
    assert event.detection_source == "ET POLICY RDP"

    doc_sig = {
        "source": {"ip": "10.0.0.1"},
        "destination": {"ip": "8.8.8.8"},
        "alert": {"signature": "ET SCAN Nmap", "severity": 2},
    }
    event2 = collector._normalize_alert(doc_sig)
    assert event2 is not None
    assert event2.detection_source == "ET SCAN Nmap"


def test_normalize_syslog_source_type():
    """_normalize_syslog() returns NormalizedEvent with source_type='ipfire_syslog'."""
    collector = MalcolmCollector()

    raw_line = "Apr  7 12:00:00 ipfire kernel: FORWARDFW IN=green0 SRC=10.0.0.1 DST=8.8.8.8"
    event = collector._normalize_syslog(raw_line)
    assert event is not None
    assert event.source_type == "ipfire_syslog"


def test_normalize_alert_raw_event_truncated():
    """raw_event in NormalizedEvent is truncated to 8192 characters when doc JSON exceeds 8KB."""
    import json

    collector = MalcolmCollector()

    # Create a doc whose JSON representation exceeds 8192 characters
    large_doc = {
        "source": {"ip": "10.0.0.1"},
        "destination": {"ip": "8.8.8.8"},
        "padding": "x" * 9000,
    }
    assert len(json.dumps(large_doc)) > 8192

    event = collector._normalize_alert(large_doc)
    assert event is not None
    assert len(event.raw_event) <= 8192


def test_normalize_alert_returns_none_on_missing_ip():
    """_normalize_alert() returns None when both source.ip and src_ip/srcip are absent."""
    collector = MalcolmCollector()

    # No IP fields at all
    doc = {"alert": {"signature": "ET SCAN", "severity": 2}, "destination": {"ip": "8.8.8.8"}}
    result = collector._normalize_alert(doc)
    assert result is None
