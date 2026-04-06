"""Eval tests for P22-T03: analyst_qa prompt template evaluation."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from prompts import analyst_qa
from tests.eval.conftest import MOCK_RESPONSE_TEXT, load_event_fixtures


async def test_analyst_qa_response_contains_event_reference(mock_ollama):
    """Mock LLM response for analyst_qa references fixture event IDs."""
    events = load_event_fixtures("analyst_qa_events.ndjson")
    context_events = [json.dumps(e) for e in events]
    context_ids = [e["event_id"] for e in events]

    system_addition, user_turn = analyst_qa.build_prompt(
        question="What lateral movement activity is present?",
        context_events=context_events,
    )

    with patch.object(mock_ollama._client, "post", new=mock_ollama._mock_post):
        result = await mock_ollama.generate(
            prompt=user_turn,
            system=analyst_qa.SYSTEM + system_addition,
            grounding_event_ids=context_ids,
            prompt_template_name=analyst_qa.TEMPLATE_NAME,
            prompt_template_sha256=analyst_qa.TEMPLATE_SHA256,
        )

    # MOCK_RESPONSE_TEXT contains "evt-001" and "evt-002"
    assert "evt-001" in result or "evt-002" in result
    assert len(result) > 0


async def test_analyst_qa_no_hallucinated_ids(mock_ollama):
    """Citations in mock response all appear in the context_ids list."""
    from backend.api.query import verify_citations

    events = load_event_fixtures("analyst_qa_events.ndjson")
    context_ids = [e["event_id"] for e in events]

    with patch.object(mock_ollama._client, "post", new=mock_ollama._mock_post):
        result = await mock_ollama.generate(prompt="test", system=analyst_qa.SYSTEM)

    # verify_citations checks that every [id] in response exists in context_ids
    # MOCK_RESPONSE_TEXT cites evt-001 and evt-002, both present in analyst_qa fixtures
    assert verify_citations(result, context_ids) is True
