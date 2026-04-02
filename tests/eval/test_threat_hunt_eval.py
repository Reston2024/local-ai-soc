"""Eval tests for P22-T03: threat_hunt prompt template evaluation."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from prompts import threat_hunt
from tests.eval.conftest import MOCK_RESPONSE_TEXT, load_event_fixtures


async def test_threat_hunt_hypothesis_fixture_a(mock_ollama):
    """Threat hunt eval with fixture A produces non-empty response."""
    events = load_event_fixtures("threat_hunt_events_a.ndjson")
    event_strs = [json.dumps(e) for e in events]

    prompt = threat_hunt.build_prompt(
        hypothesis="Attacker may have established persistence via SQL Server xp_cmdshell",
        context_events=event_strs,
    )

    with patch.object(mock_ollama._client, "post", new=mock_ollama._mock_post):
        result = await mock_ollama.generate(
            prompt=prompt,
            system=threat_hunt.SYSTEM,
        )

    assert len(result) > 0


async def test_threat_hunt_hypothesis_fixture_b(mock_ollama):
    """Threat hunt eval with fixture B completes without error."""
    events = load_event_fixtures("threat_hunt_events_b.ndjson")
    event_strs = [json.dumps(e) for e in events]

    prompt = threat_hunt.build_prompt(
        hypothesis="Attacker may have deployed a scheduled task for persistence",
        context_events=event_strs,
    )

    with patch.object(mock_ollama._client, "post", new=mock_ollama._mock_post):
        result = await mock_ollama.generate(
            prompt=prompt,
            system=threat_hunt.SYSTEM,
        )

    assert result == MOCK_RESPONSE_TEXT
