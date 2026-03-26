"""Unit tests for ingestion/parsers/csv_parser.py."""
import pytest
pytestmark = pytest.mark.unit


class TestCsvParser:
    def test_basic_parse_returns_events(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "timestamp,hostname,process_name,username\n"
            "2026-01-01T00:00:00,host1,cmd.exe,SYSTEM\n"
            "2026-01-01T00:01:00,host2,powershell.exe,user1\n"
        )
        from ingestion.parsers.csv_parser import CsvParser
        parser = CsvParser()
        events = list(parser.parse(str(csv_file)))
        assert len(events) == 2
        assert events[0].hostname == "host1"
        assert events[1].hostname == "host2"

    def test_event_has_event_id(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "timestamp,hostname\n"
            "2026-01-01T00:00:00,host1\n"
        )
        from ingestion.parsers.csv_parser import CsvParser
        parser = CsvParser()
        events = list(parser.parse(str(csv_file)))
        assert events[0].event_id is not None

    def test_process_name_mapped(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "timestamp,process_name\n"
            "2026-01-01T00:00:00,svchost.exe\n"
        )
        from ingestion.parsers.csv_parser import CsvParser
        parser = CsvParser()
        events = list(parser.parse(str(csv_file)))
        assert events[0].process_name == "svchost.exe"

    def test_empty_csv_returns_no_events(self, tmp_path):
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("timestamp,hostname\n")  # header only
        from ingestion.parsers.csv_parser import CsvParser
        parser = CsvParser()
        events = list(parser.parse(str(csv_file)))
        assert events == []

    def test_alternate_field_names_mapped(self, tmp_path):
        """csv_parser maps 'host' -> hostname, 'user' -> username, etc."""
        csv_file = tmp_path / "alt.csv"
        csv_file.write_text(
            "timestamp,host,user,image\n"
            "2026-01-01T00:00:00,dc01,alice,lsass.exe\n"
        )
        from ingestion.parsers.csv_parser import CsvParser
        parser = CsvParser()
        events = list(parser.parse(str(csv_file)))
        assert events[0].hostname == "dc01"
        assert events[0].username == "alice"

    def test_source_type_is_csv(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("timestamp,hostname\n2026-01-01T00:00:00,host1\n")
        from ingestion.parsers.csv_parser import CsvParser
        parser = CsvParser()
        events = list(parser.parse(str(csv_file)))
        assert events[0].source_type == "csv"
