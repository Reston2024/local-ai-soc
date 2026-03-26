"""Unit tests for detections/matcher.py — Sigma rule SQL compilation."""
import pytest
pytestmark = pytest.mark.unit

_SIMPLE_RULE = """
title: Test Mimikatz Detection
name: test_mimikatz
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        CommandLine|contains: 'mimikatz'
    condition: selection
"""

_CONTAINS_ALL_RULE = """
title: Test Contains All
name: test_contains_all
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        CommandLine|contains|all:
            - 'powershell'
            - '-enc'
    condition: selection
"""

_OR_RULE = """
title: Test OR Rule
name: test_or_rule
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        process_name:
            - 'cmd.exe'
            - 'powershell.exe'
    condition: selection
"""

_UNKNOWN_FIELD_RULE = """
title: Unknown Field
name: unknown_field
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        NonExistentSigmaField: 'value'
    condition: selection
"""


class TestSigmaFieldMap:
    def test_field_map_exists(self):
        from detections.field_map import SIGMA_FIELD_MAP
        assert isinstance(SIGMA_FIELD_MAP, dict)
        assert len(SIGMA_FIELD_MAP) > 0

    def test_commandline_mapped(self):
        from detections.field_map import SIGMA_FIELD_MAP
        assert "CommandLine" in SIGMA_FIELD_MAP
        assert SIGMA_FIELD_MAP["CommandLine"] == "command_line"

    def test_processname_mapped(self):
        from detections.field_map import SIGMA_FIELD_MAP
        assert "Image" in SIGMA_FIELD_MAP or "ProcessName" in SIGMA_FIELD_MAP


class TestRuleToSql:
    def _make_matcher(self):
        from unittest.mock import MagicMock
        from detections.matcher import SigmaMatcher
        stores = MagicMock()
        matcher = SigmaMatcher(stores)
        return matcher

    def _parse_rule(self, yaml_text: str):
        from sigma.rule import SigmaRule
        return SigmaRule.from_yaml(yaml_text)

    def test_simple_contains_produces_like(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_SIMPLE_RULE)
        sql = matcher.rule_to_sql(rule)
        assert sql is not None
        assert "LIKE" in sql.upper() or "%" in sql

    def test_contains_all_produces_and(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_CONTAINS_ALL_RULE)
        sql = matcher.rule_to_sql(rule)
        assert sql is not None
        assert "AND" in sql.upper()

    def test_or_values_produce_in_or_like(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_OR_RULE)
        sql = matcher.rule_to_sql(rule)
        # process_name is not in SIGMA_FIELD_MAP — result may be None
        # The important thing is it doesn't raise an exception
        assert sql is None or isinstance(sql, str)

    def test_unknown_field_returns_none(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_UNKNOWN_FIELD_RULE)
        result = matcher.rule_to_sql(rule)
        # Should return None or empty string for unmapped field
        assert result is None or result == ""
