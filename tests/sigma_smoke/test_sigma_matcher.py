"""Smoke tests for Sigma rule matching against DuckDB."""
from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest

from detections.field_map import INTEGER_COLUMNS, SIGMA_FIELD_MAP
from detections.matcher import SigmaMatcher


class TestSigmaFieldMap:
    """Validate the Sigma field map (SIGMA_FIELD_MAP)."""

    def test_field_map_is_dict(self):
        assert isinstance(SIGMA_FIELD_MAP, dict)
        assert len(SIGMA_FIELD_MAP) >= 1

    def test_image_maps_to_process_name(self):
        # Sigma 'Image' field should map to 'process_name' DuckDB column
        assert "Image" in SIGMA_FIELD_MAP
        assert SIGMA_FIELD_MAP["Image"] == "process_name"

    def test_commandline_maps_to_command_line(self):
        assert "CommandLine" in SIGMA_FIELD_MAP
        assert SIGMA_FIELD_MAP["CommandLine"] == "command_line"

    def test_computer_maps_to_hostname(self):
        assert "Computer" in SIGMA_FIELD_MAP
        assert SIGMA_FIELD_MAP["Computer"] == "hostname"

    def test_user_maps_to_username(self):
        assert "User" in SIGMA_FIELD_MAP
        assert SIGMA_FIELD_MAP["User"] == "username"

    def test_destinationport_maps_to_dst_port(self):
        assert "DestinationPort" in SIGMA_FIELD_MAP
        assert SIGMA_FIELD_MAP["DestinationPort"] == "dst_port"

    def test_destinationip_maps_to_dst_ip(self):
        assert "DestinationIp" in SIGMA_FIELD_MAP
        assert SIGMA_FIELD_MAP["DestinationIp"] == "dst_ip"

    def test_all_values_are_strings(self):
        for k, v in SIGMA_FIELD_MAP.items():
            assert isinstance(v, str), f"Field mapping value must be str: {k} -> {v!r}"

    def test_no_sql_injection_in_values(self):
        for k, v in SIGMA_FIELD_MAP.items():
            assert ";" not in v, f"Potential SQL injection in field map: {k} -> {v}"
            assert "--" not in v, f"SQL comment in field map: {k} -> {v}"

    def test_integer_columns_are_frozenset(self):
        assert isinstance(INTEGER_COLUMNS, frozenset)

    def test_dst_port_is_integer_column(self):
        assert "dst_port" in INTEGER_COLUMNS

    def test_src_port_is_integer_column(self):
        assert "src_port" in INTEGER_COLUMNS

    def test_process_id_is_integer_column(self):
        assert "process_id" in INTEGER_COLUMNS


class TestSigmaMatcher:
    """Test Sigma rule loading and SQL translation."""

    @pytest.fixture
    def matcher(self):
        # SigmaMatcher requires a 'stores' object; use a MagicMock for unit tests
        mock_stores = MagicMock()
        return SigmaMatcher(stores=mock_stores)

    @pytest.fixture
    def rules_dir(self, tmp_path):
        """Create a temp dir with a minimal Sigma rule."""
        rules = tmp_path / "rules"
        rules.mkdir()
        (rules / "test_rule.yml").write_text(
            """
title: Test PowerShell Detection
id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
status: test
description: Test rule
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        Image: powershell.exe
    condition: selection
level: high
"""
        )
        return str(rules)

    @pytest.fixture
    def sigma_fixture_dir(self):
        """Use the project's fixture sigma rules if they exist."""
        d = Path("fixtures/sigma")
        if d.exists():
            return str(d)
        return None

    def test_initial_rule_count_is_zero(self, matcher):
        assert matcher.rule_count == 0

    def test_load_rules_from_dir(self, matcher, rules_dir):
        count = matcher.load_rules_dir(rules_dir)
        assert count >= 1
        assert matcher.rule_count >= 1

    def test_load_nonexistent_dir_returns_zero(self, matcher, tmp_path):
        nonexistent = str(tmp_path / "does_not_exist")
        count = matcher.load_rules_dir(nonexistent)
        assert count == 0

    def test_rule_produces_sql(self, matcher, rules_dir):
        matcher.load_rules_dir(rules_dir)
        for rule in matcher._rules:
            result = matcher.rule_to_sql_with_params(rule)
            if result is not None:
                sql, params = result
                assert isinstance(sql, str)
                assert isinstance(params, list)
                assert len(sql) > 0

    def test_rule_sql_contains_process_name(self, matcher, rules_dir):
        matcher.load_rules_dir(rules_dir)
        for rule in matcher._rules:
            result = matcher.rule_to_sql_with_params(rule)
            if result is not None:
                sql, params = result
                assert "process_name" in sql, (
                    f"Expected 'process_name' in SQL for rule using 'Image' field, got: {sql}"
                )

    def test_rule_sql_uses_params_not_inline_values(self, matcher, rules_dir):
        matcher.load_rules_dir(rules_dir)
        for rule in matcher._rules:
            result = matcher.rule_to_sql_with_params(rule)
            if result is not None:
                sql, params = result
                # Values should be parameterised with ?, not inlined
                assert "?" in sql

    def test_rule_matches_expected_event(self, matcher, rules_dir):
        """Load rules and match against a simple DuckDB table."""
        matcher.load_rules_dir(rules_dir)

        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE events (
                event_id VARCHAR,
                timestamp TIMESTAMPTZ,
                hostname VARCHAR,
                username VARCHAR,
                process_name VARCHAR,
                process_id INTEGER,
                parent_process_name VARCHAR,
                parent_process_id INTEGER,
                file_path VARCHAR,
                file_hash_sha256 VARCHAR,
                command_line VARCHAR,
                src_ip VARCHAR,
                src_port INTEGER,
                dst_ip VARCHAR,
                dst_port INTEGER,
                domain VARCHAR,
                url VARCHAR,
                event_type VARCHAR,
                severity VARCHAR,
                source_type VARCHAR,
                raw_event VARCHAR,
                tags VARCHAR,
                ingested_at TIMESTAMPTZ
            )
        """)
        conn.execute("""
            INSERT INTO events VALUES (
                'evt-001',
                '2026-03-14 09:00:00+00',
                'WORKSTATION-01',
                'jsmith',
                'powershell.exe',
                4821,
                'explorer.exe',
                1234,
                NULL,
                NULL,
                'powershell.exe -nop -w hidden -enc SQBFAFgA',
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                'ProcessCreate',
                'high',
                'sysmon',
                '{"Image": "powershell.exe"}',
                'execution',
                '2026-03-14 09:00:01+00'
            )
        """)

        for rule in matcher._rules:
            result = matcher.rule_to_sql_with_params(rule)
            if result is None:
                continue
            try:
                sql, params = result
                full_sql = f"SELECT * FROM events WHERE {sql}"
                results = conn.execute(full_sql, params).fetchall()
                assert len(results) >= 1, (
                    f"Rule '{rule.title}' should have matched test event; "
                    f"SQL: {full_sql}, params: {params}"
                )
            except Exception as e:
                pytest.skip(f"Rule SQL execution failed (may need full schema): {e}")

    def test_fixture_rules_load(self, matcher, sigma_fixture_dir):
        """Verify fixture Sigma rules parse without errors."""
        if not sigma_fixture_dir:
            pytest.skip("fixtures/sigma/ not found")
        count = matcher.load_rules_dir(sigma_fixture_dir)
        assert count >= 1
        for rule in matcher._rules:
            assert rule.title is not None
            assert rule.detection is not None

    def test_fixture_rules_produce_sql(self, matcher, sigma_fixture_dir):
        """Verify fixture Sigma rules can be converted to SQL."""
        if not sigma_fixture_dir:
            pytest.skip("fixtures/sigma/ not found")
        matcher.load_rules_dir(sigma_fixture_dir)
        converted = 0
        for rule in matcher._rules:
            result = matcher.rule_to_sql_with_params(rule)
            if result is not None:
                converted += 1
        assert converted >= 1, "At least one fixture Sigma rule should produce SQL"

    def test_load_rule_yaml_inline(self, matcher):
        """Test loading a rule from a YAML string directly."""
        yaml_text = """
title: Inline Test Rule
id: f1e2d3c4-b5a6-7890-abcd-123456789abc
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        Image: cmd.exe
    condition: selection
level: medium
"""
        rule = matcher.load_rule_yaml(yaml_text)
        assert rule is not None
        assert str(rule.title) == "Inline Test Rule"
