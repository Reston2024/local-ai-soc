"""Eval tests for P22-T03: threat_hunt prompt template evaluation."""
from __future__ import annotations

import pytest

from prompts import threat_hunt as _threat_hunt  # noqa: F401


@pytest.mark.skip(reason="stub — implemented in 22-03")
async def test_threat_hunt_hypothesis_fixture_a(mock_ollama):
    """Mock LLM response for threat_hunt fixture A includes hypothesis keyword."""
    pass


@pytest.mark.skip(reason="stub — implemented in 22-03")
async def test_threat_hunt_hypothesis_fixture_b(mock_ollama):
    """Mock LLM response for threat_hunt fixture B completes without error."""
    pass
