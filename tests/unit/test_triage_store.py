"""
Wave 0 stubs: Unit tests for triage DDL and store methods using :memory: SQLite.

Tests cover:
  1. triage_results table exists after SQLiteStore init
  2. detections table has triaged_at column after init
  3. save_triage_result() inserts one row
  4. get_latest_triage() returns most-recent row (by created_at DESC); None when empty
  5. save_triage_result() is idempotent (same run_id via INSERT OR REPLACE)
"""

import pytest

from backend.stores.sqlite_store import SQLiteStore


@pytest.fixture()
def store():
    """Yield an in-memory SQLiteStore and close it after the test."""
    s = SQLiteStore(":memory:")
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Test 1: triage_results table exists after init
# ---------------------------------------------------------------------------


def test_triage_results_table_exists(store):
    row = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='triage_results'"
    ).fetchone()
    assert row is not None, "triage_results table was not created by SQLiteStore.__init__"


# ---------------------------------------------------------------------------
# Test 2: detections table has triaged_at column after init
# ---------------------------------------------------------------------------


def test_detections_has_triaged_at_column(store):
    cols = [
        info[1]
        for info in store._conn.execute(
            "PRAGMA table_info('detections')"
        ).fetchall()
    ]
    assert "triaged_at" in cols, (
        f"triaged_at column missing from detections; found columns: {cols}"
    )


# ---------------------------------------------------------------------------
# Test 3: save_triage_result() inserts one row
# ---------------------------------------------------------------------------


_SAMPLE = {
    "run_id": "r1",
    "severity_summary": "Critical",
    "result_text": "3 high-severity detections found.",
    "detection_count": 3,
    "model_name": "llama3",
    "created_at": "2026-04-10T00:00:00Z",
}


def test_save_triage_result_inserts_row(store):
    store.save_triage_result(_SAMPLE)
    count = store._conn.execute(
        "SELECT COUNT(*) FROM triage_results WHERE run_id = ?", ("r1",)
    ).fetchone()[0]
    assert count == 1


# ---------------------------------------------------------------------------
# Test 4: get_latest_triage() returns dict with correct data; None when empty
# ---------------------------------------------------------------------------


def test_get_latest_triage_returns_none_when_empty(store):
    result = store.get_latest_triage()
    assert result is None


def test_get_latest_triage_returns_most_recent(store):
    older = {**_SAMPLE, "run_id": "r_older", "created_at": "2026-04-09T00:00:00Z"}
    newer = {**_SAMPLE, "run_id": "r_newer", "created_at": "2026-04-10T12:00:00Z"}
    store.save_triage_result(older)
    store.save_triage_result(newer)
    result = store.get_latest_triage()
    assert result is not None
    assert result["run_id"] == "r_newer"
    assert result["severity_summary"] == "Critical"
    assert result["detection_count"] == 3


# ---------------------------------------------------------------------------
# Test 5: save_triage_result() is idempotent (INSERT OR REPLACE)
# ---------------------------------------------------------------------------


def test_save_triage_result_idempotent(store):
    store.save_triage_result(_SAMPLE)
    # Same run_id — should not raise, should stay at one row
    store.save_triage_result({**_SAMPLE, "severity_summary": "High"})
    count = store._conn.execute(
        "SELECT COUNT(*) FROM triage_results WHERE run_id = ?", ("r1",)
    ).fetchone()[0]
    assert count == 1
    # Confirm updated value was stored
    row = store._conn.execute(
        "SELECT severity_summary FROM triage_results WHERE run_id = ?", ("r1",)
    ).fetchone()
    assert row[0] == "High"
