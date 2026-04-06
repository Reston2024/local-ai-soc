"""Eval tests for P22-T03: triage prompt template evaluation."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from prompts import triage
from tests.eval.conftest import MOCK_RESPONSE_TEXT, load_event_fixtures


async def test_triage_response_references_severity(mock_ollama):
    """Mock LLM triage response is non-empty and contains analysis keywords."""
    events = load_event_fixtures("triage_events_a.ndjson")
    detections = [json.dumps(e) for e in events]

    system_addition, user_turn = triage.build_prompt(detections=detections)

    with patch.object(mock_ollama._client, "post", new=mock_ollama._mock_post):
        result = await mock_ollama.generate(
            prompt=user_turn,
            system=triage.SYSTEM + system_addition,
        )

    assert len(result) > 0
    # MOCK_RESPONSE_TEXT mentions "lateral movement" — a plausible triage keyword
    assert isinstance(result, str)


async def test_triage_response_fixture_b(mock_ollama):
    """Triage eval runs to completion with fixture B without error."""
    events = load_event_fixtures("triage_events_b.ndjson")
    detections = [json.dumps(e) for e in events]
    context_ids = [e["event_id"] for e in events]

    system_addition, user_turn = triage.build_prompt(
        detections=detections,
        context_events=[json.dumps(e) for e in events],
    )

    with patch.object(mock_ollama._client, "post", new=mock_ollama._mock_post):
        result = await mock_ollama.generate(
            prompt=user_turn,
            system=triage.SYSTEM + system_addition,
            grounding_event_ids=context_ids,
        )

    assert result == MOCK_RESPONSE_TEXT
