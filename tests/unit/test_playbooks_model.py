"""Phase 38: PlaybookStep model extension stubs."""
import pytest
from pydantic import ValidationError
from backend.models.playbook import PlaybookStep, PlaybookRunAdvance


def test_playbook_step_new_fields():
    step = PlaybookStep(step_number=1, title="t", description="d")
    assert hasattr(step, "attack_techniques")
    assert hasattr(step, "escalation_threshold")
    assert hasattr(step, "escalation_role")
    assert hasattr(step, "time_sla_minutes")
    assert hasattr(step, "containment_actions")


def test_playbook_step_defaults():
    step = PlaybookStep(step_number=1, title="t", description="d")
    assert step.attack_techniques == []
    assert step.containment_actions == []
    assert step.escalation_threshold is None
    assert step.time_sla_minutes is None


def test_playbook_run_advance_containment():
    adv = PlaybookRunAdvance()
    assert hasattr(adv, "containment_action")
    assert adv.containment_action is None


def test_escalation_threshold_literal():
    step = PlaybookStep(step_number=1, title="t", description="d", escalation_threshold="critical")
    assert step.escalation_threshold == "critical"
    with pytest.raises(ValidationError):
        PlaybookStep(step_number=1, title="t", description="d", escalation_threshold="invalid")
