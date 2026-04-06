"""
Wave 0 stub test for Sigma SQL injection hardening requirement.

This test is pre-skipped. It is activated in 23.5-02.

Requirements covered: P23.5-T05

NOTE: The existing @pytest.mark.xfail stub in tests/security/test_injection.py
(test_sigma_sql_injection) remains untouched. This file is the correctly-named
replacement that will be activated when T05 is implemented.
"""
import pytest


@pytest.mark.skip(reason="stub — activated in 23.5-02")
def test_sigma_sql_injection():
    """
    T05: rule_to_sql must produce parameterised SQL and never interpolate values
    containing SQL metacharacters ('; DROP TABLE', '1=1', '--') directly into
    the query string.

    Verifies that all field values are bound via ? placeholders in the params list,
    not concatenated into the WHERE clause string.
    """
    from sigma.collection import SigmaCollection

    from detections.matcher import rule_to_sql

    # Sigma rule with SQL injection payload as the field value
    malicious_rule_yaml = """
title: SQL Injection Test
status: test
logsource:
    category: process_creation
detection:
    selection:
        CommandLine: "'; DROP TABLE events; --"
    condition: selection
"""
    collection = SigmaCollection.from_yaml(malicious_rule_yaml)
    rule = list(collection)[0]

    sql, params = rule_to_sql(rule)

    # The SQL string must NOT contain the raw injection payload
    assert "DROP TABLE" not in sql, "rule_to_sql must not interpolate values into SQL"
    assert "1=1" not in sql, "rule_to_sql must not interpolate truthy conditions"
    assert "--" not in sql or sql.count("--") == 0, "rule_to_sql must bind all values as params"

    # The payload must appear in the params list (bound safely)
    assert any("DROP TABLE" in str(p) for p in params), (
        "Injection payload must be in params list, not SQL string"
    )

    assert False, "stub — not yet implemented"
