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

    def test_dst_ip_mapped(self, tmp_path):
        csv_file = tmp_path / "net.csv"
        csv_file.write_text("timestamp,dst_ip\n2026-01-01T00:00:00,192.168.1.1\n")
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].dst_ip == "192.168.1.1"

    def test_unix_epoch_timestamp(self, tmp_path):
        csv_file = tmp_path / "epoch.csv"
        # 1735689600 = 2026-01-01T00:00:00Z
        csv_file.write_text("timestamp,hostname\n1735689600,host1\n")
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].timestamp is not None

    def test_dest_ip_alternate_key(self, tmp_path):
        """dest_ip is an alternate key that should map to dst_ip."""
        csv_file = tmp_path / "destip.csv"
        csv_file.write_text("timestamp,dest_ip\n2026-01-01T00:00:00,10.0.0.1\n")
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].dst_ip == "10.0.0.1"

    def test_source_file_set(self, tmp_path):
        csv_file = tmp_path / "events.csv"
        csv_file.write_text("timestamp,hostname\n2026-01-01T00:00:00,host1\n")
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].source_file == str(csv_file)

    def test_username_mapped_from_user_column(self, tmp_path):
        csv_file = tmp_path / "user.csv"
        csv_file.write_text("timestamp,user\n2026-01-01T00:00:00,bob\n")
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].username == "bob"

    def test_command_line_mapped(self, tmp_path):
        csv_file = tmp_path / "cmd.csv"
        csv_file.write_text(
            "timestamp,command_line\n"
            "2026-01-01T00:00:00,powershell -enc abc\n"
        )
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].command_line == "powershell -enc abc"

    def test_cmdline_alternate_key(self, tmp_path):
        """'cmdline' alternate key maps to command_line."""
        csv_file = tmp_path / "cmdline.csv"
        csv_file.write_text(
            "timestamp,cmdline\n"
            "2026-01-01T00:00:00,cmd /c whoami\n"
        )
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].command_line == "cmd /c whoami"

    def test_image_maps_to_process_name(self, tmp_path):
        csv_file = tmp_path / "img.csv"
        csv_file.write_text(
            "timestamp,image\n"
            "2026-01-01T00:00:00,notepad.exe\n"
        )
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].process_name == "notepad.exe"

    def test_severity_mapped(self, tmp_path):
        csv_file = tmp_path / "sev.csv"
        csv_file.write_text(
            "timestamp,hostname,severity\n"
            "2026-01-01T00:00:00,host1,high\n"
        )
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].severity == "high"

    def test_invalid_severity_not_set(self, tmp_path):
        """Severity values not in the valid set should be set to None."""
        csv_file = tmp_path / "badsev.csv"
        csv_file.write_text(
            "timestamp,hostname,severity\n"
            "2026-01-01T00:00:00,host1,superurgent\n"
        )
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].severity is None

    def test_two_rows_get_different_event_ids(self, tmp_path):
        csv_file = tmp_path / "two.csv"
        csv_file.write_text(
            "timestamp,hostname\n"
            "2026-01-01T00:00:00,host1\n"
            "2026-01-01T00:01:00,host2\n"
        )
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].event_id != events[1].event_id

    def test_parse_nonexistent_file_returns_empty(self, tmp_path):
        """Parsing a nonexistent file should yield nothing (not raise)."""
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(tmp_path / "does_not_exist.csv")))
        assert events == []

    def test_src_ip_mapped(self, tmp_path):
        csv_file = tmp_path / "srcip.csv"
        csv_file.write_text("timestamp,src_ip\n2026-01-01T00:00:00,10.1.1.1\n")
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].src_ip == "10.1.1.1"

    def test_dst_port_mapped(self, tmp_path):
        csv_file = tmp_path / "port.csv"
        csv_file.write_text("timestamp,dst_port\n2026-01-01T00:00:00,443\n")
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file)))
        assert events[0].dst_port == 443

    def test_case_id_propagated(self, tmp_path):
        csv_file = tmp_path / "case.csv"
        csv_file.write_text("timestamp,hostname\n2026-01-01T00:00:00,host1\n")
        from ingestion.parsers.csv_parser import CsvParser
        events = list(CsvParser().parse(str(csv_file), case_id="case-xyz"))
        assert events[0].case_id == "case-xyz"
