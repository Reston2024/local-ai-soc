"""Shared fixtures for the tests/eval/ eval harness."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

MOCK_RESPONSE_TEXT = (
    "Based on the evidence, the alert [evt-001] indicates lateral movement. "
    "Process [evt-002] spawned an unusual child. Possible: credential dumping via lsass."
)


@pytest.fixture
def mock_ollama():
    """OllamaClient with HTTP layer mocked to return MOCK_RESPONSE_TEXT."""
    from backend.services.ollama_client import OllamaClient

    client = OllamaClient(base_url="http://mock-ollama", model="test-model")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"response": MOCK_RESPONSE_TEXT})
    client._mock_post = AsyncMock(return_value=mock_resp)
    return client


def load_event_fixtures(filename: str) -> list[dict[str, Any]]:
    """Load a NDJSON fixture file from tests/eval/fixtures/ and return list of dicts."""
    path = FIXTURES_DIR / filename
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events
