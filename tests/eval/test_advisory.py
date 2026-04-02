"""Eval tests for P22-T05: advisory separation."""
from __future__ import annotations

import pytest

from prompts import analyst_qa as _analyst_qa  # noqa: F401


@pytest.mark.skip(reason="stub — implemented in 22-05")
def test_advisory_prefix():
    """analyst_qa.SYSTEM starts with '[AI Advisory' prefix."""
    pass


@pytest.mark.skip(reason="stub — implemented in 22-05")
def test_advisory_prefix_present_in_triage():
    """triage.SYSTEM also contains advisory prefix."""
    pass
