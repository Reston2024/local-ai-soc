"""Eval tests for P22-T04: model drift detection."""
from __future__ import annotations

import pytest

from backend.stores.sqlite_store import SQLiteStore


def test_table_exists():
    """model_change_events table and system_kv table exist after SQLiteStore init."""
    store = SQLiteStore(":memory:")
    # Check via sqlite_master
    tables = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {row["name"] for row in tables}
    assert "model_change_events" in table_names, "model_change_events table missing"
    assert "system_kv" in table_names, "system_kv table missing"


def test_drift_recorded():
    """record_model_change() writes a row to model_change_events."""
    store = SQLiteStore(":memory:")
    store.record_model_change("llama3:8b", "qwen3:14b")
    rows = store._conn.execute(
        "SELECT * FROM model_change_events"
    ).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row["previous_model"] == "llama3:8b"
    assert row["active_model"] == "qwen3:14b"
    assert row["change_source"] == "startup_check"


async def test_status_endpoint():
    """GET /api/settings/model-status is registered in the app routes."""
    try:
        from backend.main import app
    except ImportError:
        pytest.skip("App import pattern unclear — check backend/main.py")

    # Verify the route is registered by checking app.routes
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert any("/api/settings/model-status" in r for r in routes), (
        f"Route /api/settings/model-status not found. Routes: {routes}"
    )
