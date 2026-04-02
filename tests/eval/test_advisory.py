"""Eval tests for P22-T05: advisory separation."""
from __future__ import annotations

import pytest


def test_advisory_prefix():
    """analyst_qa.SYSTEM starts with the AI Advisory prefix."""
    from prompts import analyst_qa
    assert analyst_qa.SYSTEM.startswith("[AI Advisory"), (
        f"Expected SYSTEM to start with '[AI Advisory', got: {analyst_qa.SYSTEM[:80]!r}"
    )


def test_advisory_prefix_present_in_triage():
    """triage.SYSTEM also contains the advisory prefix."""
    from prompts import triage
    assert triage.SYSTEM.startswith("[AI Advisory"), (
        f"Expected triage.SYSTEM to start with '[AI Advisory', got: {triage.SYSTEM[:80]!r}"
    )
