"""Eval tests for P22-T04: model drift detection."""
from __future__ import annotations

import pytest

from backend.stores.sqlite_store import SQLiteStore  # noqa: F401


@pytest.mark.skip(reason="stub — implemented in 22-04")
def test_table_exists():
    """model_change_events table and system_kv table exist after SQLiteStore init."""
    pass


@pytest.mark.skip(reason="stub — implemented in 22-04")
def test_drift_recorded():
    """record_model_change() writes a row to model_change_events."""
    pass


@pytest.mark.skip(reason="stub — implemented in 22-04")
async def test_status_endpoint():
    """GET /api/settings/model-status returns 200 with active_model field."""
    pass
