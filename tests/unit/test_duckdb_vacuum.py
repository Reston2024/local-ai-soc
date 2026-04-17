"""Unit tests for DuckDB VACUUM + configurable retention.

Covers:
1. DuckDBStore.vacuum() enqueues exactly one "VACUUM" write
2. _purge_old_events calls vacuum() after a successful DELETE
3. _purge_old_events skips vacuum when settings.VACUUM_ENABLED is False
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Test 1 — vacuum() calls execute_write("VACUUM", []) exactly once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vacuum_calls_execute_write_once():
    """DuckDBStore.vacuum() should issue exactly one execute_write call with VACUUM."""
    from backend.stores.duckdb_store import DuckDBStore

    # Build the object without running __init__ so we skip real DuckDB I/O.
    store = DuckDBStore.__new__(DuckDBStore)
    store.execute_write = AsyncMock(return_value=None)  # type: ignore[method-assign]

    await store.vacuum()

    store.execute_write.assert_awaited_once_with("VACUUM", [])


# ---------------------------------------------------------------------------
# Test 2 — _purge_old_events calls vacuum after successful delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purge_old_events_calls_vacuum_on_success(monkeypatch):
    """When DELETE succeeds and VACUUM_ENABLED=True, vacuum() must be invoked."""
    from backend.startup import workers

    # Force VACUUM_ENABLED=True and provide a predictable retention window.
    monkeypatch.setattr(workers.settings, "VACUUM_ENABLED", True, raising=False)
    monkeypatch.setattr(workers.settings, "RETENTION_DAYS", 30, raising=False)

    duckdb_mock = SimpleNamespace(
        execute_write=AsyncMock(return_value=None),
        vacuum=AsyncMock(return_value=None),
    )
    stores = SimpleNamespace(duckdb=duckdb_mock)

    await workers._purge_old_events(stores, retention_days=30)

    duckdb_mock.execute_write.assert_awaited_once()
    called_sql = duckdb_mock.execute_write.await_args.args[0]
    assert "DELETE FROM events" in called_sql
    assert "INTERVAL '30 days'" in called_sql
    duckdb_mock.vacuum.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 3 — vacuum NOT called when VACUUM_ENABLED=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purge_old_events_skips_vacuum_when_disabled(monkeypatch):
    """When VACUUM_ENABLED=False, vacuum() must NOT be invoked even on success."""
    from backend.startup import workers

    monkeypatch.setattr(workers.settings, "VACUUM_ENABLED", False, raising=False)
    monkeypatch.setattr(workers.settings, "RETENTION_DAYS", 45, raising=False)

    duckdb_mock = SimpleNamespace(
        execute_write=AsyncMock(return_value=None),
        vacuum=AsyncMock(return_value=None),
    )
    stores = SimpleNamespace(duckdb=duckdb_mock)

    await workers._purge_old_events(stores, retention_days=45)

    duckdb_mock.execute_write.assert_awaited_once()
    duckdb_mock.vacuum.assert_not_awaited()


# ---------------------------------------------------------------------------
# Bonus — vacuum is skipped when the purge itself fails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purge_old_events_skips_vacuum_on_delete_failure(monkeypatch):
    """If DELETE raises, vacuum must not run (do not compound the error)."""
    from backend.startup import workers

    monkeypatch.setattr(workers.settings, "VACUUM_ENABLED", True, raising=False)
    monkeypatch.setattr(workers.settings, "RETENTION_DAYS", 90, raising=False)

    duckdb_mock = SimpleNamespace(
        execute_write=AsyncMock(side_effect=RuntimeError("boom")),
        vacuum=AsyncMock(return_value=None),
    )
    stores = SimpleNamespace(duckdb=duckdb_mock)

    # _purge_old_events swallows exceptions and logs a warning; no raise expected.
    await workers._purge_old_events(stores, retention_days=90)

    duckdb_mock.execute_write.assert_awaited_once()
    duckdb_mock.vacuum.assert_not_awaited()


# ---------------------------------------------------------------------------
# Defaults — RETENTION_DAYS / VACUUM_ENABLED live on Settings
# ---------------------------------------------------------------------------


def test_settings_defaults(monkeypatch):
    """Settings exposes RETENTION_DAYS=90 and VACUUM_ENABLED=True by default."""
    # Isolate from any developer .env by passing _env_file=None and a valid token.
    monkeypatch.setenv("AUTH_TOKEN", "a" * 32)
    from backend.core.config import Settings

    s = Settings(_env_file=None)
    assert s.RETENTION_DAYS == 90
    assert s.VACUUM_ENABLED is True
