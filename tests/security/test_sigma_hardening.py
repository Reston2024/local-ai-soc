"""
Security test: Sigma SQL injection parameterization (P23.5-T05 / E1-01 / E10-01).

Verifies that SigmaMatcher.rule_to_sql_with_params() never interpolates
Sigma rule field values directly into the SQL WHERE clause string.  All
values must be passed as ? bound parameters.

Does NOT require a running DuckDB service — uses a lightweight mock.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

INJECTION_VALUE = "'; DROP TABLE events; --"

INJECTION_RULE_YAML = f"""
title: SQL Injection Test Rule
id: 00000000-0000-0000-0000-000000000099
status: test
logsource:
    category: network
    product: ipfire
detection:
    selection:
        DestinationIp: "{INJECTION_VALUE}"
    condition: selection
"""

INJECTION_RULE_YAML_COMMANDLINE = f"""
title: SQL Injection Test Rule CommandLine
id: 00000000-0000-0000-0000-000000000098
status: test
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        CommandLine: "{INJECTION_VALUE}"
    condition: selection
"""


def _make_matcher() -> "SigmaMatcher":
    """Return a SigmaMatcher wired to a mock Stores object (no real DB needed)."""
    from detections.matcher import SigmaMatcher

    stores = MagicMock()
    return SigmaMatcher(stores=stores)


def test_sigma_sql_injection_dst_ip():
    """
    DestinationIp (→ dst_ip column) with SQL injection payload must be
    bound as a ? parameter, never interpolated into the WHERE clause string.
    """
    from sigma.rule import SigmaRule
    from detections.matcher import SigmaMatcher

    rule = SigmaRule.from_yaml(INJECTION_RULE_YAML)
    matcher = _make_matcher()

    result = matcher.rule_to_sql_with_params(rule)

    # The rule should be convertible (DestinationIp is in the field map)
    assert result is not None, (
        "rule_to_sql_with_params returned None — DestinationIp must be in SIGMA_FIELD_MAP"
    )

    where_clause, params = result

    # The WHERE clause must use ? placeholders, not embed the payload
    assert "DROP TABLE" not in where_clause, (
        f"SQL injection payload found in WHERE clause: {where_clause!r}"
    )
    assert "'; DROP TABLE" not in where_clause, (
        "Raw injection string must not appear in the generated SQL"
    )
    # '--' appearing in the clause would indicate interpolation
    assert "--" not in where_clause, (
        f"SQL comment marker found in WHERE clause: {where_clause!r}"
    )

    # The ? placeholder must be present (parameterized binding)
    assert "?" in where_clause, (
        f"WHERE clause must use ? placeholder, got: {where_clause!r}"
    )

    # The payload must be safely in the params list
    assert any(INJECTION_VALUE in str(p) for p in params), (
        f"Injection payload must appear in params list, not SQL. params={params!r}"
    )


def test_sigma_sql_injection_commandline():
    """
    CommandLine (→ command_line column) with SQL injection payload must be
    bound as a ? parameter, never interpolated into the WHERE clause string.
    """
    from sigma.rule import SigmaRule

    rule = SigmaRule.from_yaml(INJECTION_RULE_YAML_COMMANDLINE)
    matcher = _make_matcher()

    result = matcher.rule_to_sql_with_params(rule)

    assert result is not None, (
        "rule_to_sql_with_params returned None — CommandLine must be in SIGMA_FIELD_MAP"
    )

    where_clause, params = result

    assert "DROP TABLE" not in where_clause, (
        f"SQL injection payload found in WHERE clause: {where_clause!r}"
    )
    assert "--" not in where_clause, (
        f"SQL comment marker found in WHERE clause: {where_clause!r}"
    )
    assert "?" in where_clause, (
        f"WHERE clause must use ? placeholder, got: {where_clause!r}"
    )
    assert any(INJECTION_VALUE in str(p) for p in params), (
        f"Injection payload must appear in params list. params={params!r}"
    )


def test_sigma_sql_injection_multiple_metacharacters():
    """
    Values with multiple SQL metacharacters (quotes, semicolons, comment markers,
    LIKE wildcards) must all be safely bound via params, not interpolated.
    """
    from sigma.rule import SigmaRule

    payloads = [
        "1' OR '1'='1",
        "admin'--",
        "' UNION SELECT * FROM users--",
        "100% match",   # LIKE wildcard
        "file_name.exe",  # LIKE single-char wildcard
    ]

    for payload in payloads:
        yaml_text = f"""
title: Metachar Test
id: 00000000-0000-0000-0000-0000000000{abs(hash(payload)) % 90 + 10}
status: test
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        CommandLine: "{payload}"
    condition: selection
"""
        rule = SigmaRule.from_yaml(yaml_text)
        matcher = _make_matcher()
        result = matcher.rule_to_sql_with_params(rule)

        # If the field is mapped, verify parameterization
        if result is not None:
            where_clause, params = result
            assert "?" in where_clause, (
                f"Payload {payload!r} — WHERE clause must use ?: {where_clause!r}"
            )
            # The raw payload must not appear verbatim in the WHERE clause
            assert payload not in where_clause, (
                f"Payload {payload!r} must not appear verbatim in WHERE clause: {where_clause!r}"
            )


def test_where_clause_structure_with_injection_value():
    """
    Structural check: the WHERE clause for an injection value must consist
    only of column references, operators, and ? placeholders — no raw string data.
    """
    from sigma.rule import SigmaRule

    rule = SigmaRule.from_yaml(INJECTION_RULE_YAML_COMMANDLINE)
    matcher = _make_matcher()
    result = matcher.rule_to_sql_with_params(rule)

    assert result is not None
    where_clause, params = result

    # WHERE clause should only contain: column names, operators (=, LIKE, !=),
    # SQL keywords (AND, OR, NOT, IN), parentheses, and ? placeholders.
    # It should NOT contain any single-quote characters (which would indicate
    # value interpolation).
    assert "'" not in where_clause, (
        f"Single quotes in WHERE clause indicate value interpolation: {where_clause!r}"
    )
    assert '"' not in where_clause, (
        f"Double quotes in WHERE clause indicate value interpolation: {where_clause!r}"
    )


def test_sigma_sql_injection():
    """
    rule_to_sql must produce parameterized SQL for Sigma rules with SQL
    metacharacter values (P23.5-T05).

    Verifies:
    - The WHERE clause string does NOT contain the injection payload literally.
    - The params list DOES contain the value (with LIKE wildcards from |contains).
    - A ? placeholder is present in the SQL string.
    - Multiple metacharacter variants (1=1, OR 1=1, --, /**/, UNION SELECT) are
      all safely bound via params, never interpolated.

    NOTE: rule_to_sql is implemented as SigmaMatcher.rule_to_sql_with_params().
    This test calls it directly without executing against DuckDB (pure unit test).
    """
    from sigma.rule import SigmaRule
    from detections.matcher import rule_to_sql

    # Adversarial Sigma rule: field value contains SQL injection metacharacters
    adversarial_yaml = """
title: SQL Injection Test
id: 00000000-0000-0000-0000-000000000001
status: test
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        CommandLine|contains: "'; DROP TABLE normalized_events; --"
    condition: selection
"""
    rule = SigmaRule.from_yaml(adversarial_yaml)
    sql_fragment, params = rule_to_sql(rule)

    # The SQL string must NOT contain the injection payload literally
    injection_payload = "'; DROP TABLE normalized_events; --"
    assert injection_payload not in sql_fragment, (
        f"SQL injection payload found in SQL string (should be in params): {sql_fragment!r}"
    )

    # The params list MUST contain the value (with LIKE wildcards added by |contains)
    assert any(
        "DROP TABLE" in str(p) for p in params
    ), f"Injection payload not found in params list: {params}"

    # SQL string must use ? placeholder
    assert "?" in sql_fragment, f"No ? placeholder in SQL fragment: {sql_fragment!r}"

    # Additional metacharacter variants
    for payload in ["1=1", "OR 1=1", "--", "/**/", "UNION SELECT"]:
        test_yaml = f"""
title: Test {payload}
id: 00000000-0000-0000-0000-000000000002
status: test
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        CommandLine|contains: "{payload}"
    condition: selection
"""
        rule2 = SigmaRule.from_yaml(test_yaml)
        sql2, params2 = rule_to_sql(rule2)
        assert payload not in sql2, (
            f"Metacharacter '{payload}' found literally in SQL: {sql2!r}"
        )
        assert any(payload in str(p) for p in params2), (
            f"Metacharacter '{payload}' not in params: {params2}"
        )
