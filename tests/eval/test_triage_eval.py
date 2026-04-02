"""Eval tests for P22-T03: triage prompt template evaluation."""
from __future__ import annotations

import pytest

from prompts import triage as _triage  # noqa: F401


@pytest.mark.skip(reason="stub — implemented in 22-03")
async def test_triage_response_references_severity(mock_ollama):
    """Mock LLM response for triage fixture A includes severity assessment."""
    pass


@pytest.mark.skip(reason="stub — implemented in 22-03")
async def test_triage_response_fixture_b(mock_ollama):
    """Mock LLM response for triage fixture B completes without error."""
    pass
