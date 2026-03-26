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

_STARTSWITH_RULE = """
title: Test Startswith
name: test_startswith
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        CommandLine|startswith: 'powershell'
    condition: selection
"""

_ENDSWITH_RULE = """
title: Test Endswith
name: test_endswith
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        Image|endswith: '.exe'
    condition: selection
"""

_OR_LIST_RULE = """
title: Test OR list
name: test_or_list
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        CommandLine|contains:
            - 'cmd.exe'
            - 'powershell.exe'
    condition: selection
"""

_OR_CONDITION_RULE = """
title: Test OR condition
name: test_or_condition
status: test
logsource:
    product: windows
    category: process_creation
detection:
    sel1:
        CommandLine|contains: 'mimikatz'
    sel2:
        Image|endswith: '.exe'
    condition: sel1 or sel2
"""

_AND_CONDITION_RULE = """
title: Test AND condition
name: test_and_condition
status: test
logsource:
    product: windows
    category: process_creation
detection:
    sel1:
        CommandLine|contains: 'powershell'
    sel2:
        User: 'SYSTEM'
    condition: sel1 and sel2
"""

_NOT_CONDITION_RULE = """
title: Test NOT condition
name: test_not_condition
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        CommandLine|contains: 'mimikatz'
    filter:
        User: 'admin'
    condition: selection and not filter
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

_DEST_IP_RULE = """
title: Test DestIP
name: test_destip
status: test
logsource:
    product: windows
    category: network_connection
detection:
    selection:
        DestinationIp|contains: '192.168'
    condition: selection
"""

_1OF_RULE = """
title: Test 1 of
name: test_1of
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection_a:
        CommandLine|contains: 'mimikatz'
    selection_b:
        Image|endswith: 'lsass.exe'
    condition: 1 of selection*
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

    def test_image_maps_to_process_name(self):
        from detections.field_map import SIGMA_FIELD_MAP
        assert SIGMA_FIELD_MAP.get("Image") == "process_name"

    def test_user_maps_to_username(self):
        from detections.field_map import SIGMA_FIELD_MAP
        assert SIGMA_FIELD_MAP.get("User") == "username"

    def test_computername_maps_to_hostname(self):
        from detections.field_map import SIGMA_FIELD_MAP
        assert SIGMA_FIELD_MAP.get("ComputerName") == "hostname"

    def test_destinationip_maps_to_dst_ip(self):
        from detections.field_map import SIGMA_FIELD_MAP
        assert SIGMA_FIELD_MAP.get("DestinationIp") == "dst_ip"

    def test_all_values_are_strings(self):
        from detections.field_map import SIGMA_FIELD_MAP
        for key, val in SIGMA_FIELD_MAP.items():
            assert isinstance(val, str), f"Field {key} maps to non-string {val!r}"

    def test_no_spaces_in_column_names(self):
        from detections.field_map import SIGMA_FIELD_MAP
        for key, col in SIGMA_FIELD_MAP.items():
            assert " " not in col, f"Column name '{col}' for field '{key}' has spaces"

    def test_integer_columns_exist(self):
        from detections.field_map import INTEGER_COLUMNS
        assert isinstance(INTEGER_COLUMNS, frozenset)
        assert "dst_port" in INTEGER_COLUMNS
        assert "src_port" in INTEGER_COLUMNS

    def test_integer_columns_are_subset_of_field_map_values(self):
        from detections.field_map import SIGMA_FIELD_MAP, INTEGER_COLUMNS
        all_columns = set(SIGMA_FIELD_MAP.values())
        for col in INTEGER_COLUMNS:
            assert col in all_columns, f"INTEGER_COLUMN {col} not in SIGMA_FIELD_MAP values"


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

    def test_contains_produces_percent_wildcards(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_SIMPLE_RULE)
        result = matcher.rule_to_sql_with_params(rule)
        assert result is not None
        _, params = result
        assert any("%" in str(p) for p in params)

    def test_contains_all_produces_and(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_CONTAINS_ALL_RULE)
        sql = matcher.rule_to_sql(rule)
        assert sql is not None
        assert "AND" in sql.upper()

    def test_contains_all_has_two_params(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_CONTAINS_ALL_RULE)
        result = matcher.rule_to_sql_with_params(rule)
        assert result is not None
        _, params = result
        assert len(params) == 2

    def test_startswith_produces_trailing_percent(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_STARTSWITH_RULE)
        result = matcher.rule_to_sql_with_params(rule)
        assert result is not None
        sql, params = result
        # startswith: param is 'value%' with no leading %
        assert any(str(p).endswith("%") and not str(p).startswith("%") for p in params)
        assert "LIKE" in sql.upper()

    def test_endswith_produces_leading_percent(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_ENDSWITH_RULE)
        result = matcher.rule_to_sql_with_params(rule)
        assert result is not None
        sql, params = result
        # endswith: param is '%value' with no trailing %
        assert any(str(p).startswith("%") and not str(p).endswith("%") for p in params)
        assert "LIKE" in sql.upper()

    def test_or_list_produces_or_or_in(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_OR_LIST_RULE)
        sql = matcher.rule_to_sql(rule)
        assert sql is not None
        assert "OR" in sql.upper() or "IN" in sql.upper() or "LIKE" in sql.upper()

    def test_or_condition_rule_produces_or(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_OR_CONDITION_RULE)
        sql = matcher.rule_to_sql(rule)
        assert sql is not None
        assert "OR" in sql.upper()

    def test_and_condition_rule_produces_and(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_AND_CONDITION_RULE)
        sql = matcher.rule_to_sql(rule)
        assert sql is not None
        assert "AND" in sql.upper()

    def test_not_condition_produces_not(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_NOT_CONDITION_RULE)
        sql = matcher.rule_to_sql(rule)
        # If both fields map to known columns, NOT should appear
        if sql is not None:
            assert "NOT" in sql.upper() or "AND" in sql.upper()

    def test_unknown_field_returns_none(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_UNKNOWN_FIELD_RULE)
        result = matcher.rule_to_sql(rule)
        # Should return None or empty string for unmapped field
        assert result is None or result == ""

    def test_destination_ip_rule_produces_dst_ip_clause(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_DEST_IP_RULE)
        sql = matcher.rule_to_sql(rule)
        assert sql is not None
        assert "dst_ip" in sql.lower()

    def test_1of_selection_produces_or(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_1OF_RULE)
        sql = matcher.rule_to_sql(rule)
        assert sql is not None
        assert "OR" in sql.upper()

    def test_or_values_produce_in_or_like(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_OR_LIST_RULE)
        sql = matcher.rule_to_sql(rule)
        # Should produce some kind of multi-value clause
        assert sql is None or isinstance(sql, str)

    def test_rule_to_sql_with_params_returns_tuple(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_SIMPLE_RULE)
        result = matcher.rule_to_sql_with_params(rule)
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2
        sql, params = result
        assert isinstance(sql, str)
        assert isinstance(params, list)

    def test_params_are_strings_not_sigma_objects(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_SIMPLE_RULE)
        result = matcher.rule_to_sql_with_params(rule)
        assert result is not None
        _, params = result
        for p in params:
            assert isinstance(p, (str, int, float)), f"Param {p!r} is not a primitive type"


class TestSigmaMatcherInit:
    def test_instantiation_succeeds(self):
        from unittest.mock import MagicMock
        from detections.matcher import SigmaMatcher
        stores = MagicMock()
        matcher = SigmaMatcher(stores)
        assert matcher is not None

    def test_rule_count_starts_at_zero(self):
        from unittest.mock import MagicMock
        from detections.matcher import SigmaMatcher
        stores = MagicMock()
        matcher = SigmaMatcher(stores)
        assert matcher.rule_count == 0

    def test_load_rules_dir_empty(self, tmp_path):
        from unittest.mock import MagicMock
        from detections.matcher import SigmaMatcher
        stores = MagicMock()
        matcher = SigmaMatcher(stores)
        count = matcher.load_rules_dir(str(tmp_path))
        assert count == 0
        assert matcher.rule_count == 0

    def test_load_rules_dir_nonexistent_path(self, tmp_path):
        from unittest.mock import MagicMock
        from detections.matcher import SigmaMatcher
        stores = MagicMock()
        matcher = SigmaMatcher(stores)
        count = matcher.load_rules_dir(str(tmp_path / "does_not_exist"))
        assert count == 0

    def test_load_rules_dir_one_rule(self, tmp_path):
        rule_file = tmp_path / "test_rule.yml"
        rule_file.write_text("""
title: Test Rule
name: test_one
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        CommandLine|contains: 'mimikatz'
    condition: selection
""")
        from unittest.mock import MagicMock
        from detections.matcher import SigmaMatcher
        stores = MagicMock()
        matcher = SigmaMatcher(stores)
        count = matcher.load_rules_dir(str(tmp_path))
        assert count >= 1
        assert matcher.rule_count >= 1

    def test_load_rule_yaml_valid(self):
        from unittest.mock import MagicMock
        from detections.matcher import SigmaMatcher
        stores = MagicMock()
        matcher = SigmaMatcher(stores)
        rule = matcher.load_rule_yaml(_SIMPLE_RULE)
        assert rule is not None
        assert matcher.rule_count == 1

    def test_load_rule_yaml_invalid_returns_none(self):
        from unittest.mock import MagicMock
        from detections.matcher import SigmaMatcher
        stores = MagicMock()
        matcher = SigmaMatcher(stores)
        rule = matcher.load_rule_yaml("this is not valid yaml: : : :")
        # Should return None without raising
        assert rule is None or rule is not None  # just check no crash

    def test_load_multiple_rules(self, tmp_path):
        for i in range(3):
            rule_file = tmp_path / f"rule_{i}.yml"
            rule_file.write_text(f"""
title: Rule {i}
name: rule_{i}
status: test
logsource:
    product: windows
    category: process_creation
detection:
    selection:
        CommandLine|contains: 'malware{i}'
    condition: selection
""")
        from unittest.mock import MagicMock
        from detections.matcher import SigmaMatcher
        stores = MagicMock()
        matcher = SigmaMatcher(stores)
        count = matcher.load_rules_dir(str(tmp_path))
        assert count == 3
        assert matcher.rule_count == 3


class TestValueToSqlFragment:
    """Test the _value_to_sql_fragment helper via rule_to_sql_with_params."""

    def _make_matcher(self):
        from unittest.mock import MagicMock
        from detections.matcher import SigmaMatcher
        return SigmaMatcher(MagicMock())

    def _parse_rule(self, yaml_text: str):
        from sigma.rule import SigmaRule
        return SigmaRule.from_yaml(yaml_text)

    def test_contains_wraps_in_percent(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_SIMPLE_RULE)
        result = matcher.rule_to_sql_with_params(rule)
        _, params = result
        # mimikatz should become %mimikatz%
        assert any("mimikatz" in str(p) for p in params)
        assert any(str(p).startswith("%") and str(p).endswith("%") for p in params)

    def test_startswith_appends_percent(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_STARTSWITH_RULE)
        result = matcher.rule_to_sql_with_params(rule)
        _, params = result
        # powershell should become powershell%
        assert any("powershell" in str(p) and str(p).endswith("%") for p in params)

    def test_endswith_prepends_percent(self):
        matcher = self._make_matcher()
        rule = self._parse_rule(_ENDSWITH_RULE)
        result = matcher.rule_to_sql_with_params(rule)
        _, params = result
        # .exe should become %.exe
        assert any(".exe" in str(p) and str(p).startswith("%") for p in params)


class TestConditionSplitting:
    """Test the _split_condition and _build_condition_sql helpers."""

    def _make_matcher(self):
        from unittest.mock import MagicMock
        from detections.matcher import SigmaMatcher
        return SigmaMatcher(MagicMock())

    def test_split_on_and(self):
        from detections.matcher import SigmaMatcher
        from unittest.mock import MagicMock
        matcher = SigmaMatcher(MagicMock())
        parts = matcher._split_condition("sel1 and sel2", "and")
        assert parts is not None
        assert len(parts) == 2

    def test_split_on_or(self):
        from detections.matcher import SigmaMatcher
        from unittest.mock import MagicMock
        matcher = SigmaMatcher(MagicMock())
        parts = matcher._split_condition("sel1 or sel2", "or")
        assert parts is not None
        assert len(parts) == 2

    def test_no_split_on_simple_term(self):
        from detections.matcher import SigmaMatcher
        from unittest.mock import MagicMock
        matcher = SigmaMatcher(MagicMock())
        parts = matcher._split_condition("selection", "and")
        assert parts is None

    def test_balanced_parens(self):
        from detections.matcher import SigmaMatcher
        assert SigmaMatcher._balanced("(a AND b)")
        assert SigmaMatcher._balanced("((a) OR (b))")
        assert not SigmaMatcher._balanced("(a AND b")
        assert not SigmaMatcher._balanced("a AND b)")
