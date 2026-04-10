"""Unit tests for explain.py structured error response (Wave 0 stubs — 35-01)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.explain import ExplainRequest, ExplainResponse, _run_explanation


def _make_request() -> MagicMock:
    """Create a minimal mock request with app.state.ollama."""
    req = MagicMock()
    req.app.state.ollama = AsyncMock()
    req.app.state.stores = MagicMock()
    return req


async def test_run_explanation_empty_investigation_returns_structured_response():
    """When investigation is {} (detection not found), _run_explanation returns
    ExplainResponse with 'No investigation context found' — not an exception."""
    body = ExplainRequest(investigation={})
    req = _make_request()

    result = await _run_explanation(req, body)

    assert isinstance(result, ExplainResponse)
    assert "No investigation context found" in result.what_happened
    # Ollama must NOT be called when there is no investigation context
    req.app.state.ollama.assert_not_called()


async def test_run_explanation_missing_detection_id_returns_structured_response():
    """When detection_id is provided but detection does not exist in store,
    response.what_happened starts with 'No investigation context'."""
    body = ExplainRequest(detection_id="nonexistent-det-999")
    req = _make_request()
    # Stub _assemble_investigation to return {} (detection not found)
    # We do this by making the SQLite store return None for get_detection
    sqlite_mock = MagicMock()
    sqlite_mock._conn.execute.return_value.fetchone.return_value = None
    req.app.state.stores.sqlite = sqlite_mock

    # Patch asyncio.to_thread to call the lambda synchronously
    import backend.api.explain as explain_mod

    original_to_thread = asyncio.to_thread

    async def fake_to_thread(fn, *args, **kwargs):
        if callable(fn):
            return fn(*args, **kwargs)
        return await original_to_thread(fn, *args, **kwargs)

    import unittest.mock as mock

    with mock.patch("asyncio.to_thread", side_effect=fake_to_thread):
        result = await _run_explanation(req, body)

    assert isinstance(result, ExplainResponse)
    assert result.what_happened.startswith("No investigation context")
