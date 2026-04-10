"""
Wave 0 test stubs for Phase 34 ATT&CK tagging and coverage scan.
P34-T02 (Sigma tag extraction), P34-T04 (coverage scan).

All tests use in-memory or tmp_path — no network I/O.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing the tag extraction functions
# ---------------------------------------------------------------------------
try:
    from backend.services.attack.attack_store import (
        extract_attack_techniques_from_rule,
        scan_rules_dir_for_coverage,
    )
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


# ---------------------------------------------------------------------------
# test_extract_techniques
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_extract_techniques():
    """SigmaRule with attack.t1059 and attack.execution tags → only ['T1059'] returned."""
    from sigma.rule import SigmaRule

    yaml_text = """
title: Test Rule
status: test
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        CommandLine|contains: 'evil'
    condition: selection
tags:
    - attack.t1059
    - attack.execution
"""
    rule = SigmaRule.from_yaml(yaml_text)
    result = extract_attack_techniques_from_rule(rule)
    assert result == ["T1059"]


# ---------------------------------------------------------------------------
# test_tag_case_insensitive
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_tag_case_insensitive():
    """attack.T1059 (upper-case T) is normalised to 'T1059'."""
    from sigma.rule import SigmaRule

    yaml_text = """
title: Case Test
status: test
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        CommandLine|contains: 'evil'
    condition: selection
tags:
    - attack.T1059
"""
    rule = SigmaRule.from_yaml(yaml_text)
    result = extract_attack_techniques_from_rule(rule)
    assert "T1059" in result


# ---------------------------------------------------------------------------
# test_subtechnique_tag
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_subtechnique_tag():
    """attack.t1059.001 (sub-technique) → ['T1059'] (parent ID only, .001 dropped)."""
    from sigma.rule import SigmaRule

    yaml_text = """
title: Subtechnique Test
status: test
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        CommandLine|contains: 'powershell'
    condition: selection
tags:
    - attack.t1059.001
"""
    rule = SigmaRule.from_yaml(yaml_text)
    result = extract_attack_techniques_from_rule(rule)
    assert result == ["T1059"]


# ---------------------------------------------------------------------------
# test_coverage_scan
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_coverage_scan(tmp_path):
    """scan_rules_dir_for_coverage() finds T1059 in a single .yml file."""
    from pathlib import Path

    rule_yml = tmp_path / "test_rule.yml"
    rule_yml.write_text(
        """
title: Coverage Scan Rule
status: test
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        CommandLine|contains: 'evil'
    condition: selection
tags:
    - attack.t1059
    - attack.execution
""",
        encoding="utf-8",
    )

    coverage = scan_rules_dir_for_coverage(tmp_path)

    assert "T1059" in coverage
    assert isinstance(coverage["T1059"], list)
    assert len(coverage["T1059"]) == 1
    assert coverage["T1059"][0] == "Coverage Scan Rule"
