"""Unit tests for auto-triage background worker (_auto_triage_loop).

Tests verify:
1. Worker calls _run_triage at least once given a mock app
2. Worker continues (does not raise) when _run_triage raises an exception
3. Worker exits cleanly on asyncio.CancelledError
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_minimal_app():
    """Return a minimal fake app (worker will call _run_triage(app))."""
    sqlite_mock = MagicMock()
    sqlite_mock._conn = MagicMock()
    sqlite_mock._conn.execute.return_value.fetchall.return_value = []
    sqlite_mock.get_latest_triage.return_value = None

    stores = SimpleNamespace(sqlite=sqlite_mock)
    ollama_mock = AsyncMock()
    ollama_mock.generate = AsyncMock(return_value="CRITICAL: test")
    ollama_mock.model = "test-model"

    return SimpleNamespace(
        state=SimpleNamespace(stores=stores, ollama=ollama_mock)
    )


# ---------------------------------------------------------------------------
# Test 1: Worker calls _run_triage at least once
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_calls_run_triage_at_least_once():
    """_auto_triage_loop invokes _run_triage at least once before being cancelled."""
    from backend.api import triage as triage_module

    app = _make_minimal_app()
    call_count = 0

    async def mock_run_triage(a):
        nonlocal call_count
        call_count += 1
        # Cancel ourselves after first call so the loop exits cleanly
        raise asyncio.CancelledError()

    with patch.object(triage_module, "_run_triage", side_effect=mock_run_triage):
        task = asyncio.ensure_future(triage_module._auto_triage_loop(app))
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    assert call_count >= 1, "_run_triage should have been called at least once"


# ---------------------------------------------------------------------------
# Test 2: Worker continues when _run_triage raises a non-fatal exception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_continues_on_error():
    """_auto_triage_loop continues running after _run_triage raises an exception."""
    from backend.api import triage as triage_module

    app = _make_minimal_app()
    call_count = 0

    async def mock_run_triage_error(a):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated transient error")
        # Second call: cancel the loop to end the test
        raise asyncio.CancelledError()

    # Patch sleep to return immediately so the loop iterates fast
    async def mock_sleep(_seconds):
        pass

    with patch.object(triage_module, "_run_triage", side_effect=mock_run_triage_error):
        with patch("asyncio.sleep", side_effect=mock_sleep):
            task = asyncio.ensure_future(triage_module._auto_triage_loop(app))
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

    assert call_count >= 2, "Worker should have continued after error and called _run_triage again"


# ---------------------------------------------------------------------------
# Test 3: Worker exits cleanly on asyncio.CancelledError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_exits_on_cancelled_error():
    """_auto_triage_loop propagates CancelledError cleanly (no unhandled exception)."""
    from backend.api import triage as triage_module

    app = _make_minimal_app()

    async def mock_run_triage_ok(a):
        return {"detection_count": 0, "message": "No untriaged detections"}

    async def mock_sleep(_seconds):
        # On first sleep, cancel the task
        raise asyncio.CancelledError()

    with patch.object(triage_module, "_run_triage", side_effect=mock_run_triage_ok):
        with patch("asyncio.sleep", side_effect=mock_sleep):
            task = asyncio.ensure_future(triage_module._auto_triage_loop(app))
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except asyncio.CancelledError:
                pass  # Expected: CancelledError should propagate cleanly

    # If we reach here without an unhandled exception, the test passes
    assert task.done(), "Task should be done (cancelled)"
