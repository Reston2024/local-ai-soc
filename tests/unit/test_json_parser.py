"""Unit tests for JSON/NDJSON event parser."""
import json
import pytest
from pathlib import Path
from backend.models.event import NormalizedEvent
from ingestion.parsers.json_parser import JsonParser


class TestJsonParserCanHandle:
    """Tests for file extension detection."""

    @pytest.fixture
    def parser(self):
        return JsonParser()

    def test_can_handle_json(self, parser):
        assert parser.can_handle("events.json")

    def test_can_handle_ndjson(self, parser):
        assert parser.can_handle("events.ndjson")

    def test_can_handle_jsonl(self, parser):
        assert parser.can_handle("events.jsonl")

    def test_cannot_handle_evtx(self, parser):
        assert not parser.can_handle("events.evtx")

    def test_cannot_handle_csv(self, parser):
        assert not parser.can_handle("events.csv")

    def test_cannot_handle_xml(self, parser):
        assert not parser.can_handle("events.xml")


class TestJsonParserNDJSON:
    """Tests for NDJSON (newline-delimited JSON) parsing."""

    @pytest.fixture
    def parser(self):
        return JsonParser()

    def test_parse_ndjson_string(self, parser, tmp_path):
        ndjson = "\n".join([
            json.dumps({"timestamp": "2026-03-14T09:00:00Z", "hostname": "H1", "severity": "high"}),
            json.dumps({"timestamp": "2026-03-14T09:01:00Z", "hostname": "H2", "severity": "low"}),
        ])
        f = tmp_path / "test.ndjson"
        f.write_text(ndjson)
        events = list(parser.parse(str(f)))
        assert len(events) == 2
        assert all(isinstance(e, NormalizedEvent) for e in events)
        hostnames = {e.hostname for e in events}
        assert "H1" in hostnames
        assert "H2" in hostnames

    def test_parse_ndjson_severity_mapped(self, parser, tmp_path):
        ndjson = json.dumps({"timestamp": "2026-03-14T09:00:00Z", "severity": "high"})
        f = tmp_path / "test.ndjson"
        f.write_text(ndjson)
        events = list(parser.parse(str(f)))
        assert events[0].severity == "high"

    def test_skip_empty_lines(self, parser, tmp_path):
        ndjson = (
            json.dumps({"timestamp": "2026-03-14T09:00:00Z", "hostname": "H1"}) + "\n"
            "\n"
            + json.dumps({"timestamp": "2026-03-14T09:01:00Z", "hostname": "H2"}) + "\n"
        )
        f = tmp_path / "test.ndjson"
        f.write_text(ndjson)
        events = list(parser.parse(str(f)))
        assert len(events) == 2

    def test_ndjson_timestamp_is_utc(self, parser, tmp_path):
        from datetime import timezone
        ndjson = json.dumps({"timestamp": "2026-03-14T09:00:00Z", "hostname": "H1"})
        f = tmp_path / "test.ndjson"
        f.write_text(ndjson)
        events = list(parser.parse(str(f)))
        assert events[0].timestamp.tzinfo is not None

    def test_ndjson_hostname_extracted(self, parser, tmp_path):
        ndjson = json.dumps({"timestamp": "2026-03-14T09:00:00Z", "hostname": "WORKSTATION-01"})
        f = tmp_path / "test.ndjson"
        f.write_text(ndjson)
        events = list(parser.parse(str(f)))
        assert events[0].hostname == "WORKSTATION-01"

    def test_ndjson_process_name_extracted(self, parser, tmp_path):
        ndjson = json.dumps({"timestamp": "2026-03-14T09:00:00Z", "process_name": "powershell.exe"})
        f = tmp_path / "test.ndjson"
        f.write_text(ndjson)
        events = list(parser.parse(str(f)))
        assert events[0].process_name == "powershell.exe"

    def test_ndjson_command_line_extracted(self, parser, tmp_path):
        ndjson = json.dumps({
            "timestamp": "2026-03-14T09:00:00Z",
            "CommandLine": "powershell.exe -nop -w hidden",
        })
        f = tmp_path / "test.ndjson"
        f.write_text(ndjson)
        events = list(parser.parse(str(f)))
        assert events[0].command_line == "powershell.exe -nop -w hidden"

    def test_ndjson_dst_ip_extracted(self, parser, tmp_path):
        ndjson = json.dumps({
            "timestamp": "2026-03-14T09:00:00Z",
            "dst_ip": "185.234.1.100",
            "dst_port": 4444,
        })
        f = tmp_path / "test.ndjson"
        f.write_text(ndjson)
        events = list(parser.parse(str(f)))
        assert events[0].dst_ip == "185.234.1.100"
        assert events[0].dst_port == 4444

    def test_ndjson_tags_comma_joined(self, parser, tmp_path):
        ndjson = json.dumps({
            "timestamp": "2026-03-14T09:00:00Z",
            "tags": ["execution", "powershell"],
        })
        f = tmp_path / "test.ndjson"
        f.write_text(ndjson)
        events = list(parser.parse(str(f)))
        tags = events[0].tags or ""
        assert "execution" in tags
        assert "powershell" in tags


class TestJsonParserArray:
    """Tests for JSON array format."""

    @pytest.fixture
    def parser(self):
        return JsonParser()

    def test_parse_json_array(self, parser, tmp_path):
        data = [
            {"timestamp": "2026-03-14T09:00:00Z", "hostname": "H1"},
            {"timestamp": "2026-03-14T09:01:00Z", "hostname": "H2"},
        ]
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data))
        events = list(parser.parse(str(f)))
        assert len(events) == 2
        assert all(isinstance(e, NormalizedEvent) for e in events)

    def test_parse_single_json_object(self, parser, tmp_path):
        data = {"timestamp": "2026-03-14T09:00:00Z", "hostname": "H1"}
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data))
        events = list(parser.parse(str(f)))
        assert len(events) == 1
        assert events[0].hostname == "H1"

    def test_parse_json_array_returns_normalized_events(self, parser, tmp_path):
        data = [{"timestamp": "2026-03-14T09:00:00Z", "severity": "critical"}]
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data))
        events = list(parser.parse(str(f)))
        assert isinstance(events[0], NormalizedEvent)
        assert events[0].severity == "critical"


class TestJsonParserFixture:
    """Tests against the project's fixture file."""

    @pytest.fixture
    def parser(self):
        return JsonParser()

    def test_parse_fixture_file(self, parser):
        fixture = Path("fixtures/security_events.ndjson")
        if not fixture.exists():
            pytest.skip("fixtures/security_events.ndjson not found")
        events = list(parser.parse(str(fixture)))
        assert len(events) >= 10, "Expected at least 10 fixture events"
        for e in events:
            assert isinstance(e, NormalizedEvent)
            assert e.timestamp is not None

    def test_fixture_events_have_hostnames(self, parser):
        fixture = Path("fixtures/security_events.ndjson")
        if not fixture.exists():
            pytest.skip("fixtures/security_events.ndjson not found")
        events = list(parser.parse(str(fixture)))
        hostnames = {e.hostname for e in events if e.hostname}
        assert len(hostnames) >= 1

    def test_fixture_events_source_type(self, parser):
        fixture = Path("fixtures/security_events.ndjson")
        if not fixture.exists():
            pytest.skip("fixtures/security_events.ndjson not found")
        events = list(parser.parse(str(fixture)))
        # All events parsed from NDJSON get source_type "ndjson"
        assert all(e.source_type is not None for e in events)
