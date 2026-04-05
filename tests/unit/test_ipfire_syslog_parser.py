"""Unit tests for IPFireSyslogParser — Phase 23 P23-T01.

Wave 0: all tests pre-skipped. Wave 1 (23-01-PLAN.md) activates them.
"""
from __future__ import annotations

import pytest

try:
    from ingestion.parsers.ipfire_syslog_parser import IPFireSyslogParser
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(not _IMPORT_OK, reason="IPFireSyslogParser not implemented — Wave 1")

FIXTURE_LOG = "fixtures/syslog/ipfire_sample.log"


class TestIPFireParserForwardFW:
    """P23-T01: FORWARDFW line parsed to NormalizedEvent with correct fields."""

    def test_forwardfw_fields(self):
        parser = IPFireSyslogParser()
        events = list(parser.parse(FIXTURE_LOG))
        fw_events = [e for e in events if e.event_type == "network_connect"]
        assert len(fw_events) >= 1
        e = fw_events[0]
        assert e.src_ip == "192.168.1.100"
        assert e.dst_ip == "54.230.45.152"
        assert e.dst_port == 443
        assert e.network_protocol == "TCP"
        assert e.event_outcome == "success"
        assert e.raw_event is not None


class TestIPFireParserDropReject:
    """P23-T01: DROP and REJECT lines map to event_outcome='failure'."""

    def test_drop_ctinvalid(self):
        parser = IPFireSyslogParser()
        events = list(parser.parse(FIXTURE_LOG))
        drop_events = [e for e in events if e.event_outcome == "failure"]
        assert len(drop_events) >= 2

    def test_raw_event_preserved(self):
        parser = IPFireSyslogParser()
        events = list(parser.parse(FIXTURE_LOG))
        assert all(e.raw_event for e in events)


class TestIPFireParserICMP:
    """P23-T01: ICMP lines (no SPT/DPT) parsed without crashing."""

    def test_icmp_no_ports(self):
        parser = IPFireSyslogParser()
        events = list(parser.parse(FIXTURE_LOG))
        icmp_events = [e for e in events if e.network_protocol == "ICMP"]
        assert len(icmp_events) >= 1
        e = icmp_events[0]
        assert e.src_port is None
        assert e.dst_port is None


class TestIPFireParserSingleLine:
    """P23-T01: parse_line() convenience method works on a single string."""

    def test_parse_line_returns_event(self):
        parser = IPFireSyslogParser()
        line = (
            "Aug 10 18:44:55 ipfire kernel: FORWARDFW IN=green0 OUT=red0 "
            "MAC=d0:50:99:4e:bc:d0:00:1a:2b:3c:4d:5e:08:00 SRC=192.168.1.100 "
            "DST=54.230.45.152 LEN=60 TOS=0x00 PREC=0x00 TTL=63 ID=6995 DF "
            "PROTO=TCP SPT=34995 DPT=443 WINDOW=14600 RES=0x00 SYN URGP=0"
        )
        event = parser.parse_line(line)
        assert event is not None
        assert event.src_ip == "192.168.1.100"
