"""
Unit tests for ingestion/parsers/evtx_parser.py.

All tests use hand-crafted dicts and unittest.mock — no real .evtx binary files
are read.  This allows full coverage of every code path without binary fixtures.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from ingestion.parsers.evtx_parser import (
    EvtxParser,
    _determine_event_type,
    _extract_field,
    _parse_timestamp,
    _safe_int,
)

# ---------------------------------------------------------------------------
# Shared fixture records
# ---------------------------------------------------------------------------

_NOW = datetime(2023, 1, 15, 14, 23, 1, tzinfo=timezone.utc)

SYSMON_PROCESS_CREATE = {
    "event_record_id": 1,
    "timestamp": "2023-01-15T14:23:01Z",
    "data": json.dumps(
        {
            "Event": {
                "System": {
                    "EventID": 1,
                    "Channel": "Microsoft-Windows-Sysmon/Operational",
                    "Computer": "WORKSTATION01",
                    "EventRecordID": 1,
                    "TimeCreated": {"@SystemTime": "2023-01-15T14:23:01Z"},
                },
                "EventData": {
                    "Data": [
                        {"@Name": "Image", "#text": "C:\\Windows\\System32\\cmd.exe"},
                        {"@Name": "CommandLine", "#text": "cmd.exe /c whoami"},
                        {"@Name": "ProcessId", "#text": "4321"},
                        {"@Name": "ParentImage", "#text": "C:\\Windows\\explorer.exe"},
                        {"@Name": "User", "#text": "WORKSTATION01\\jdoe"},
                    ]
                },
            }
        }
    ),
}

SECURITY_LOGON = {
    "event_record_id": 2,
    "timestamp": "2023-01-15T14:24:00Z",
    "data": json.dumps(
        {
            "Event": {
                "System": {
                    "EventID": 4624,
                    "Channel": "Security",
                    "Computer": "WORKSTATION01",
                    "EventRecordID": 2,
                    "TimeCreated": {"@SystemTime": "2023-01-15T14:24:00Z"},
                },
                "EventData": {
                    "Data": [
                        {"@Name": "SubjectUserName", "#text": "jdoe"},
                        {"@Name": "IpAddress", "#text": "192.168.1.100"},
                    ]
                },
            }
        }
    ),
}

SYSMON_NETWORK_CONNECT = {
    "event_record_id": 3,
    "timestamp": "2023-01-15T14:25:00Z",
    "data": json.dumps(
        {
            "Event": {
                "System": {
                    "EventID": 3,
                    "Channel": "Microsoft-Windows-Sysmon/Operational",
                    "Computer": "WORKSTATION01",
                    "EventRecordID": 3,
                    "TimeCreated": {"@SystemTime": "2023-01-15T14:25:00Z"},
                },
                "EventData": {
                    "Data": [
                        {"@Name": "DestinationIp", "#text": "10.0.0.1"},
                        {"@Name": "DestinationPort", "#text": "443"},
                        {"@Name": "SourceIp", "#text": "192.168.1.50"},
                        {"@Name": "SourcePort", "#text": "52100"},
                        {"@Name": "DestinationHostname", "#text": "evil.example.com"},
                    ]
                },
            }
        }
    ),
}

SYSMON_WITH_HASHES = {
    "event_record_id": 4,
    "timestamp": "2023-01-15T14:26:00Z",
    "data": json.dumps(
        {
            "Event": {
                "System": {
                    "EventID": 7,
                    "Channel": "Microsoft-Windows-Sysmon/Operational",
                    "Computer": "WORKSTATION01",
                    "EventRecordID": 4,
                    "TimeCreated": {"@SystemTime": "2023-01-15T14:26:00Z"},
                },
                "EventData": {
                    "Data": [
                        {
                            "@Name": "Hashes",
                            "#text": "MD5=abc123,SHA256=deadbeef1234567890abcdef12345678deadbeef1234567890abcdef12345678,SHA1=aabbcc",
                        },
                        {"@Name": "ImageLoaded", "#text": "C:\\evil.dll"},
                    ]
                },
            }
        }
    ),
}

CORRUPT_DATA_RECORD = {
    "event_record_id": 99,
    "timestamp": "2023-01-15T14:27:00Z",
    "data": "NOT VALID JSON {{{",
}


# ---------------------------------------------------------------------------
# TestParseTimestamp
# ---------------------------------------------------------------------------


class TestParseTimestamp:
    def test_valid_iso_z(self):
        """Standard pyevtx-rs timestamp with Z suffix parses to UTC datetime."""
        result = _parse_timestamp("2023-01-15T14:23:01.123456Z")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14

    def test_no_tz_suffix(self):
        """Timestamp without timezone suffix parses without raising."""
        result = _parse_timestamp("2023-01-15T14:23:01")
        assert isinstance(result, datetime)
        # Should be UTC-aware (tzinfo assigned) or fallback to utcnow()
        assert result is not None

    def test_empty_string(self):
        """Empty string returns a datetime (fallback to utcnow), never raises."""
        result = _parse_timestamp("")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_garbage_string(self):
        """Unparseable string returns a datetime (fallback to utcnow), never raises."""
        result = _parse_timestamp("not-a-date")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_none_input(self):
        """None input returns a datetime fallback, never raises."""
        result = _parse_timestamp(None)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# TestExtractField
# ---------------------------------------------------------------------------


class TestExtractField:
    def _sample_data(self):
        return {
            "SubjectUserName": "jdoe",
            "IpAddress": "192.168.1.1",
            "EmptyField": "  ",
        }

    def test_first_key_found(self):
        """Returns value for the first key present in data."""
        data = self._sample_data()
        assert _extract_field(data, "SubjectUserName") == "jdoe"

    def test_first_match_wins(self):
        """When multiple keys present, returns the first non-empty match."""
        data = self._sample_data()
        result = _extract_field(data, "MissingKey", "SubjectUserName")
        assert result == "jdoe"

    def test_all_none(self):
        """Returns None when no key matches."""
        data = self._sample_data()
        assert _extract_field(data, "NoSuchKey1", "NoSuchKey2") is None

    def test_whitespace_only_skipped(self):
        """Fields with only whitespace are treated as absent."""
        data = self._sample_data()
        result = _extract_field(data, "EmptyField", "SubjectUserName")
        assert result == "jdoe"

    def test_empty_data_dict(self):
        """Empty dict always returns None."""
        assert _extract_field({}, "AnyKey") is None

    def test_strips_whitespace(self):
        """Values with surrounding whitespace are stripped."""
        data = {"Key": "  value  "}
        assert _extract_field(data, "Key") == "value"


# ---------------------------------------------------------------------------
# TestSafeInt
# ---------------------------------------------------------------------------


class TestSafeInt:
    def test_int_input(self):
        assert _safe_int(42) == 42

    def test_str_int(self):
        assert _safe_int("42") == 42

    def test_none_returns_none(self):
        assert _safe_int(None) is None

    def test_bad_string_returns_none(self):
        assert _safe_int("abc") is None

    def test_float_truncates(self):
        """float() -> int() path; verify it at least doesn't crash."""
        result = _safe_int(3.7)
        assert result == 3

    def test_empty_string_returns_none(self):
        assert _safe_int("") is None


# ---------------------------------------------------------------------------
# TestDetermineEventType
# ---------------------------------------------------------------------------


class TestDetermineEventType:
    def test_sysmon_channel_event_id_1(self):
        result = _determine_event_type(1, "Microsoft-Windows-Sysmon/Operational")
        assert result == "process_create"

    def test_sysmon_channel_event_id_3(self):
        result = _determine_event_type(3, "Microsoft-Windows-Sysmon/Operational")
        assert result == "network_connect"

    def test_security_channel_4624(self):
        result = _determine_event_type(4624, "Security")
        assert result == "logon_success"

    def test_security_channel_4625(self):
        result = _determine_event_type(4625, "Security")
        assert result == "logon_failure"

    def test_none_event_id_returns_none(self):
        result = _determine_event_type(None, "Security")
        assert result is None

    def test_none_channel_falls_through_to_security_map(self):
        """None channel tries security map."""
        result = _determine_event_type(4624, None)
        assert result == "logon_success"

    def test_unknown_event_id_returns_none(self):
        result = _determine_event_type(9999, "Security")
        assert result is None

    def test_sysmon_case_insensitive_channel(self):
        """Channel matching should be case-insensitive for 'sysmon'."""
        result = _determine_event_type(1, "microsoft-windows-sysmon/operational")
        assert result == "process_create"


# ---------------------------------------------------------------------------
# TestFlattenEventData
# ---------------------------------------------------------------------------


class TestFlattenEventData:
    def setup_method(self):
        self.parser = EvtxParser()

    def test_list_of_dicts(self):
        """Standard pyevtx-rs list-of-dicts shape."""
        event_data = {
            "Data": [
                {"@Name": "Image", "#text": "cmd.exe"},
                {"@Name": "CommandLine", "#text": "cmd.exe /c whoami"},
            ]
        }
        result = self.parser._flatten_event_data(event_data)
        assert result == {"Image": "cmd.exe", "CommandLine": "cmd.exe /c whoami"}

    def test_single_dict(self):
        """Single dict (non-list) Data value."""
        event_data = {"Data": {"@Name": "ProcessId", "#text": "1234"}}
        result = self.parser._flatten_event_data(event_data)
        assert result == {"ProcessId": "1234"}

    def test_already_flat_dict(self):
        """EventData with no 'Data' key is returned as-is."""
        event_data = {"Image": "cmd.exe", "ProcessId": "1234"}
        result = self.parser._flatten_event_data(event_data)
        assert result == {"Image": "cmd.exe", "ProcessId": "1234"}

    def test_empty_dict(self):
        """Empty EventData returns empty dict without raising."""
        result = self.parser._flatten_event_data({})
        assert result == {}

    def test_none_input(self):
        """None EventData returns empty dict without raising."""
        result = self.parser._flatten_event_data(None)
        assert result == {}

    def test_string_data_stored_under_text_key(self):
        """Free-text Data string is stored under '_text'."""
        event_data = {"Data": "some free text"}
        result = self.parser._flatten_event_data(event_data)
        assert result == {"_text": "some free text"}

    def test_dict_without_name_attribute_copies_fields(self):
        """A Data dict without @Name copies all non-@ fields directly."""
        event_data = {"Data": {"field1": "val1", "@attr": "skip"}}
        result = self.parser._flatten_event_data(event_data)
        assert "field1" in result
        assert "@attr" not in result


# ---------------------------------------------------------------------------
# TestParseRecord
# ---------------------------------------------------------------------------


class TestParseRecord:
    def setup_method(self):
        self.parser = EvtxParser()
        self.ingested_at = datetime.now(tz=timezone.utc)

    def test_sysmon_process_create(self):
        """EventID 1 Sysmon: Image -> process_name, CommandLine, ProcessId."""
        event = self.parser._parse_record(
            SYSMON_PROCESS_CREATE, "test.evtx", None, self.ingested_at
        )
        assert event is not None
        assert "cmd.exe" in event.process_name
        assert event.command_line == "cmd.exe /c whoami"
        assert event.process_id == 4321
        assert event.event_type == "process_create"
        assert event.hostname == "WORKSTATION01"
        assert event.source_type == "evtx"

    def test_sysmon_process_create_parent_fields(self):
        """ParentImage maps to parent_process_name."""
        event = self.parser._parse_record(
            SYSMON_PROCESS_CREATE, "test.evtx", None, self.ingested_at
        )
        assert event.parent_process_name is not None
        assert "explorer" in event.parent_process_name.lower()

    def test_security_logon(self):
        """EventID 4624 Security: event_type is logon_success."""
        event = self.parser._parse_record(
            SECURITY_LOGON, "test.evtx", None, self.ingested_at
        )
        assert event is not None
        assert event.event_type == "logon_success"
        assert event.username == "jdoe"

    def test_network_connect(self):
        """EventID 3 Sysmon: network fields populated."""
        event = self.parser._parse_record(
            SYSMON_NETWORK_CONNECT, "test.evtx", None, self.ingested_at
        )
        assert event.dst_ip == "10.0.0.1"
        assert event.dst_port == 443
        assert event.src_ip == "192.168.1.50"
        assert event.domain == "evil.example.com"
        assert event.event_type == "network_connect"

    def test_sha256_extraction(self):
        """Hashes field with SHA256=<hash> populates file_hash_sha256."""
        event = self.parser._parse_record(
            SYSMON_WITH_HASHES, "test.evtx", None, self.ingested_at
        )
        assert event.file_hash_sha256 is not None
        assert "deadbeef" in event.file_hash_sha256.lower()
        # Should not include the "SHA256=" prefix
        assert "SHA256=" not in event.file_hash_sha256

    def test_corrupt_data_does_not_raise(self):
        """Invalid JSON in record['data'] returns a NormalizedEvent (not raises)."""
        event = self.parser._parse_record(
            CORRUPT_DATA_RECORD, "test.evtx", None, self.ingested_at
        )
        # Either None (if implementation returns None on corrupt) or a valid event
        # The parser does NOT raise — it degrades gracefully.
        # The current implementation returns a NormalizedEvent with empty fields.
        assert event is not None
        assert event.source_type == "evtx"

    def test_missing_fields_yield_none(self):
        """A minimal record with no EventData produces None for optional fields."""
        minimal = {
            "event_record_id": 5,
            "timestamp": "2023-01-15T14:23:01Z",
            "data": json.dumps(
                {
                    "Event": {
                        "System": {
                            "EventID": 9999,
                            "Channel": "Application",
                            "Computer": "MYPC",
                            "EventRecordID": 5,
                            "TimeCreated": {"@SystemTime": "2023-01-15T14:23:01Z"},
                        },
                        "EventData": {},
                    }
                }
            ),
        }
        event = self.parser._parse_record(minimal, "test.evtx", None, self.ingested_at)
        assert event.process_name is None
        assert event.command_line is None
        assert event.username is None
        assert event.event_type is None  # 9999 maps to nothing

    def test_case_id_propagated(self):
        """case_id passed to _parse_record appears in the returned event."""
        event = self.parser._parse_record(
            SYSMON_PROCESS_CREATE, "test.evtx", "case-abc", self.ingested_at
        )
        assert event.case_id == "case-abc"

    def test_deterministic_event_id(self):
        """When computer and event_record_id are present, event_id is deterministic."""
        event1 = self.parser._parse_record(
            SYSMON_PROCESS_CREATE, "test.evtx", None, self.ingested_at
        )
        event2 = self.parser._parse_record(
            SYSMON_PROCESS_CREATE, "test.evtx", None, self.ingested_at
        )
        assert event1.event_id == event2.event_id
        assert "WORKSTATION01" in event1.event_id

    def test_ingested_at_preserved(self):
        """ingested_at passed to _parse_record is stored on the event."""
        fixed = datetime(2023, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        event = self.parser._parse_record(
            SYSMON_PROCESS_CREATE, "test.evtx", None, fixed
        )
        assert event.ingested_at == fixed


# ---------------------------------------------------------------------------
# TestEvtxParserParse
# ---------------------------------------------------------------------------


class TestEvtxParserParse:
    def test_happy_path_yields_events(self):
        """Mock returns 1 record → 1 NormalizedEvent yielded."""
        mock_parser_instance = MagicMock()
        mock_parser_instance.records_json.return_value = [SYSMON_PROCESS_CREATE]

        with patch(
            "ingestion.parsers.evtx_parser.evtx.PyEvtxParser",
            return_value=mock_parser_instance,
        ):
            events = list(EvtxParser().parse("fake.evtx"))

        assert len(events) == 1
        assert events[0].source_type == "evtx"
        assert "cmd.exe" in events[0].process_name

    def test_file_open_failure_returns_empty_iterator(self):
        """When PyEvtxParser raises OSError, parse() returns an empty iterator."""
        with patch(
            "ingestion.parsers.evtx_parser.evtx.PyEvtxParser",
            side_effect=OSError("file not found"),
        ):
            events = list(EvtxParser().parse("nonexistent.evtx"))

        assert events == []

    def test_file_open_generic_exception_returns_empty_iterator(self):
        """When PyEvtxParser raises a generic Exception, parse() returns empty."""
        with patch(
            "ingestion.parsers.evtx_parser.evtx.PyEvtxParser",
            side_effect=RuntimeError("unexpected"),
        ):
            events = list(EvtxParser().parse("bad.evtx"))

        assert events == []

    def test_per_record_exception_skips_and_continues(self):
        """First record is corrupt, second is valid — yields 1 event (skips bad)."""
        mock_parser_instance = MagicMock()
        mock_parser_instance.records_json.return_value = [
            CORRUPT_DATA_RECORD,  # degrades gracefully → still yields an event
            SECURITY_LOGON,
        ]

        with patch(
            "ingestion.parsers.evtx_parser.evtx.PyEvtxParser",
            return_value=mock_parser_instance,
        ):
            events = list(EvtxParser().parse("fake.evtx"))

        # The corrupt record doesn't raise (it degrades), so both yield events.
        # Important: the parse loop does NOT abort.
        assert len(events) >= 1
        # The Security logon should always be in the results
        event_types = [e.event_type for e in events]
        assert "logon_success" in event_types

    def test_per_record_hard_exception_skips(self):
        """A record that raises during _parse_record is skipped; valid records continue."""
        mock_parser_instance = MagicMock()

        # Construct a record that will cause _parse_record to raise:
        # a dict where 'data' is not a string and not a dict
        bad_record = {
            "event_record_id": None,
            "timestamp": None,
            "data": object(),  # not JSON-serialisable string — will raise
        }
        mock_parser_instance.records_json.return_value = [bad_record, SYSMON_PROCESS_CREATE]

        with patch(
            "ingestion.parsers.evtx_parser.evtx.PyEvtxParser",
            return_value=mock_parser_instance,
        ):
            events = list(EvtxParser().parse("fake.evtx"))

        # At least the valid SYSMON_PROCESS_CREATE record should be yielded.
        assert len(events) >= 1
        has_process_create = any(e.event_type == "process_create" for e in events)
        assert has_process_create

    def test_multiple_records(self):
        """Multiple records all yield NormalizedEvents."""
        records = [SYSMON_PROCESS_CREATE, SECURITY_LOGON, SYSMON_NETWORK_CONNECT]
        mock_parser_instance = MagicMock()
        mock_parser_instance.records_json.return_value = records

        with patch(
            "ingestion.parsers.evtx_parser.evtx.PyEvtxParser",
            return_value=mock_parser_instance,
        ):
            events = list(EvtxParser().parse("fake.evtx"))

        assert len(events) == 3

    def test_empty_file_returns_empty_iterator(self):
        """An EVTX file with zero records yields nothing."""
        mock_parser_instance = MagicMock()
        mock_parser_instance.records_json.return_value = []

        with patch(
            "ingestion.parsers.evtx_parser.evtx.PyEvtxParser",
            return_value=mock_parser_instance,
        ):
            events = list(EvtxParser().parse("empty.evtx"))

        assert events == []

    def test_source_file_propagated(self):
        """The file_path argument is stored on each yielded event as source_file."""
        mock_parser_instance = MagicMock()
        mock_parser_instance.records_json.return_value = [SYSMON_PROCESS_CREATE]

        with patch(
            "ingestion.parsers.evtx_parser.evtx.PyEvtxParser",
            return_value=mock_parser_instance,
        ):
            events = list(EvtxParser().parse("/logs/Security.evtx"))

        assert events[0].source_file == "/logs/Security.evtx"
