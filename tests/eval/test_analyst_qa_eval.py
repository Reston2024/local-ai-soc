"""Eval tests for P22-T03: analyst_qa prompt template evaluation."""
from __future__ import annotations

import pytest

from prompts import analyst_qa as _analyst_qa  # noqa: F401


@pytest.mark.skip(reason="stub — implemented in 22-03")
async def test_analyst_qa_response_contains_event_reference(mock_ollama, load_event_fixtures):
    """Mock LLM response for analyst_qa contains event ID reference from fixtures."""
    pass


@pytest.mark.skip(reason="stub — implemented in 22-03")
async def test_analyst_qa_no_hallucinated_ids(mock_ollama):
    """analyst_qa does not cite event IDs not present in context."""
    pass
