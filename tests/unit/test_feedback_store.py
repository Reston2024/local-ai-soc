"""
Wave 0 TDD stubs for Phase 44 FeedbackStore.
P44-T01: SQLite feedback table, upsert, get_verdict, get_feedback_stats.

All stubs SKIP until Plan 44-02 adds feedback methods to SQLiteStore.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Import guard — skip all stubs if SQLiteStore not yet importable
# ---------------------------------------------------------------------------
try:
    from backend.stores.sqlite_store import SQLiteStore
    _SQLITE_AVAILABLE = True
except ImportError:
    _SQLITE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _SQLITE_AVAILABLE,
    reason="SQLiteStore not available"
)

# All behavioral stubs skip until Plan 44-02 implements the methods
_stub = pytest.mark.skip(reason="stub — implemented in Plan 44-02")


# ---------------------------------------------------------------------------
# Stub 1 — feedback table exists after init
# ---------------------------------------------------------------------------
@_stub
def test_feedback_table_exists(tmp_path):
    """After SQLiteStore init, the 'feedback' table exists in sqlite_master."""
    store = SQLiteStore(path=tmp_path / "test.db")
    row = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='feedback'"
    ).fetchone()
    assert row is not None


# ---------------------------------------------------------------------------
# Stub 2 — upsert_feedback TP persists
# ---------------------------------------------------------------------------
@_stub
def test_upsert_feedback_tp(tmp_path):
    """upsert_feedback('det-001', 'TP') → get_verdict_for_detection returns 'TP'."""
    store = SQLiteStore(path=tmp_path / "test.db")
    store.upsert_feedback("det-001", "TP")
    assert store.get_verdict_for_detection("det-001") == "TP"


# ---------------------------------------------------------------------------
# Stub 3 — upsert_feedback FP persists
# ---------------------------------------------------------------------------
@_stub
def test_upsert_feedback_fp(tmp_path):
    """upsert_feedback('det-002', 'FP') → get_verdict_for_detection returns 'FP'."""
    store = SQLiteStore(path=tmp_path / "test.db")
    store.upsert_feedback("det-002", "FP")
    assert store.get_verdict_for_detection("det-002") == "FP"


# ---------------------------------------------------------------------------
# Stub 4 — upsert semantics: second write wins
# ---------------------------------------------------------------------------
@_stub
def test_verdict_update(tmp_path):
    """upsert_feedback('det-003', 'TP') then 'FP' → get_verdict returns 'FP'."""
    store = SQLiteStore(path=tmp_path / "test.db")
    store.upsert_feedback("det-003", "TP")
    store.upsert_feedback("det-003", "FP")
    assert store.get_verdict_for_detection("det-003") == "FP"


# ---------------------------------------------------------------------------
# Stub 5 — missing detection_id returns None
# ---------------------------------------------------------------------------
@_stub
def test_verdict_missing(tmp_path):
    """get_verdict_for_detection('nonexistent-id') returns None."""
    store = SQLiteStore(path=tmp_path / "test.db")
    assert store.get_verdict_for_detection("nonexistent-id") is None


# ---------------------------------------------------------------------------
# Stub 6 — stats on empty store
# ---------------------------------------------------------------------------
@_stub
def test_get_feedback_stats_empty(tmp_path):
    """get_feedback_stats() on a fresh store returns verdicts_given=0, tp_rate=0.0, fp_rate=0.0."""
    store = SQLiteStore(path=tmp_path / "test.db")
    stats = store.get_feedback_stats()
    assert stats["verdicts_given"] == 0
    assert stats["tp_rate"] == 0.0
    assert stats["fp_rate"] == 0.0


# ---------------------------------------------------------------------------
# Stub 7 — stats after 3 TP + 1 FP
# ---------------------------------------------------------------------------
@_stub
def test_get_feedback_stats_mixed(tmp_path):
    """After 3 TP + 1 FP, get_feedback_stats() returns verdicts_given=4, tp_rate=0.75, fp_rate=0.25."""
    store = SQLiteStore(path=tmp_path / "test.db")
    store.upsert_feedback("d1", "TP")
    store.upsert_feedback("d2", "TP")
    store.upsert_feedback("d3", "TP")
    store.upsert_feedback("d4", "FP")
    stats = store.get_feedback_stats()
    assert stats["verdicts_given"] == 4
    assert stats["tp_rate"] == 0.75
    assert stats["fp_rate"] == 0.25
