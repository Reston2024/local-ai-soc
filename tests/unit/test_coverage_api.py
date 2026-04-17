"""Phase 40: ATT&CK coverage API tests."""
import pytest
from backend.api.coverage import (
    _build_playbook_coverage,
    _PRIORITY_TECHNIQUES,
    _T_PATTERN,
)


class TestPriorityTechniques:
    def test_all_have_valid_technique_ids(self):
        for tid in _PRIORITY_TECHNIQUES:
            assert _T_PATTERN.match(tid), f"Invalid T-ID in priority list: {tid}"

    def test_all_have_name_and_tactic(self):
        for tid, meta in _PRIORITY_TECHNIQUES.items():
            assert meta.get("name"), f"Missing name for {tid}"
            assert meta.get("tactic"), f"Missing tactic for {tid}"

    def test_covers_all_tactics(self):
        tactics = {m["tactic"] for m in _PRIORITY_TECHNIQUES.values()}
        expected = {
            "Initial Access", "Execution", "Persistence",
            "Privilege Escalation", "Defense Evasion", "Credential Access",
            "Discovery", "Lateral Movement", "Command & Control",
            "Exfiltration", "Impact",
        }
        missing = expected - tactics
        assert not missing, f"Tactics not covered in priority list: {missing}"

    def test_minimum_technique_count(self):
        # Must have at least 40 high-priority techniques
        assert len(_PRIORITY_TECHNIQUES) >= 40


class TestPlaybookCoverage:
    def test_returns_dict(self):
        cov = _build_playbook_coverage()
        assert isinstance(cov, dict)

    def test_all_keys_are_valid_technique_ids(self):
        cov = _build_playbook_coverage()
        for tid in cov:
            assert _T_PATTERN.match(tid), f"Invalid T-ID in playbook coverage: {tid}"

    def test_all_values_are_lists(self):
        cov = _build_playbook_coverage()
        for tid, pbs in cov.items():
            assert isinstance(pbs, list), f"Expected list for {tid}"
            assert all(isinstance(p, str) for p in pbs)

    def test_core_playbooks_covered(self):
        cov = _build_playbook_coverage()
        all_pbs = {pb for pbs in cov.values() for pb in pbs}
        assert "Phishing / BEC Response" in all_pbs
        assert "Ransomware Response" in all_pbs

    def test_no_duplicate_playbooks_per_technique(self):
        cov = _build_playbook_coverage()
        for tid, pbs in cov.items():
            assert len(pbs) == len(set(pbs)), f"Duplicate playbooks for {tid}: {pbs}"

    def test_reasonable_coverage_count(self):
        cov = _build_playbook_coverage()
        # 19 playbooks × multiple techniques each → should cover 20+ distinct T-IDs
        assert len(cov) >= 20

    def test_phishing_techniques_covered(self):
        cov = _build_playbook_coverage()
        # T1566 (Phishing) should appear — it's in trigger_conditions of Phishing playbook
        assert "T1566" in cov or "T1566.001" in cov or "T1566.002" in cov, (
            "Expected phishing techniques in playbook coverage"
        )

    def test_ransomware_techniques_covered(self):
        cov = _build_playbook_coverage()
        # Ransomware playbook should cover T1486 (Data Encrypted for Impact)
        assert "T1486" in cov, "Expected T1486 (ransomware encryption) in playbook coverage"
