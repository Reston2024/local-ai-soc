"""Phase 38/39: CISA playbook content quality tests."""
import re
import pytest
from backend.data.builtin_playbooks import BUILTIN_PLAYBOOKS

CONTROLLED_VOCAB = {
    # Original Phase 38
    "isolate_host", "reset_credentials", "block_ip", "block_domain",
    "preserve_evidence", "notify_management", "engage_ir_team",
    # Phase 39 expanded set (new playbooks)
    "disable_account", "revoke_access", "patch_system",
    "notify_legal",
}
# Core 4 from Phase 38 — always expected
CORE_NAMES = {
    "Phishing / BEC Response",
    "Ransomware Response",
    "Credential / Account Compromise Response",
    "Malware / Intrusion Response",
}
T_PATTERN = re.compile(r'^T\d{4}(\.\d{3})?$')

_EXPECTED_COUNT = 30  # Phase 46 expanded set (added community/aws/cert_sg/guardsight/microsoft)


def test_four_cisa_playbooks_exist():
    """All core playbooks present and total count matches expected."""
    names = {pb["name"] for pb in BUILTIN_PLAYBOOKS}
    missing = CORE_NAMES - names
    assert not missing, f"Core playbooks missing: {missing}"
    assert len(BUILTIN_PLAYBOOKS) == _EXPECTED_COUNT, (
        f"Expected {_EXPECTED_COUNT} playbooks, got {len(BUILTIN_PLAYBOOKS)}"
    )


def test_technique_ids():
    for pb in BUILTIN_PLAYBOOKS:
        for step in pb["steps"]:
            techs = step.get("attack_techniques", [])
            assert techs, f"Step {step['step_number']} of {pb['name']} has no attack_techniques"
            for t in techs:
                assert T_PATTERN.match(t), f"Invalid technique ID: {t}"


def test_escalation_fields():
    for pb in BUILTIN_PLAYBOOKS:
        for step in pb["steps"]:
            thresh = step.get("escalation_threshold")
            if thresh is not None:
                assert thresh in ("critical", "high"), f"Bad threshold: {thresh}"
                assert step.get("escalation_role"), f"escalation_role missing on step {step['step_number']}"


def test_sla_fields():
    for pb in BUILTIN_PLAYBOOKS:
        for step in pb["steps"]:
            sla = step.get("time_sla_minutes")
            assert isinstance(sla, int) and sla > 0, (
                f"Bad SLA on step {step['step_number']} of {pb['name']}: {sla}"
            )


def test_containment_actions_vocab():
    for pb in BUILTIN_PLAYBOOKS:
        for step in pb["steps"]:
            for action in step.get("containment_actions", []):
                assert action in CONTROLLED_VOCAB, f"Unknown action: {action}"


def test_trigger_conditions_include_ttp():
    for pb in BUILTIN_PLAYBOOKS:
        ttps = [tc for tc in pb["trigger_conditions"] if T_PATTERN.match(tc)]
        assert ttps, (
            f"{pb['name']} trigger_conditions has no ATT&CK T-numbers. "
            f"Current trigger_conditions: {pb['trigger_conditions']}"
        )
