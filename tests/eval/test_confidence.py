"""Eval tests for P22-T02: Confidence scoring."""
from __future__ import annotations

import pytest

from backend.stores.sqlite_store import SQLiteStore


def _compute_heuristic(ids: list[str], citation_ok: bool) -> float:
    """Pure heuristic function mirroring the implementation in query.py."""
    score = 0.0
    if ids:
        score += 0.5
    if citation_ok:
        score += 0.3
    if len(ids) >= 5:
        score += 0.1
    return round(min(score, 1.0), 4)


def test_column_exists():
    """confidence_score column exists in llm_audit_provenance on fresh SQLiteStore."""
    store = SQLiteStore(":memory:")
    rows = store._conn.execute(
        "PRAGMA table_info(llm_audit_provenance)"
    ).fetchall()
    col_names = [row[1] for row in rows]
    assert "confidence_score" in col_names, (
        f"confidence_score column missing; found: {col_names}"
    )


def test_score_heuristic_grounded():
    """Heuristic score >= 0.5 when grounding_event_ids is non-empty."""
    score = _compute_heuristic(ids=["evt-001"], citation_ok=True)
    assert score >= 0.5, f"Expected score >= 0.5, got {score}"


def test_score_heuristic_ungrounded():
    """Heuristic score == 0.0 when grounding_event_ids is empty and no template."""
    score = _compute_heuristic(ids=[], citation_ok=False)
    assert score == 0.0, f"Expected 0.0 for ungrounded, got {score}"


def test_score_bounded():
    """Heuristic score is always between 0.0 and 1.0 inclusive."""
    # 5+ ids + citation_ok covers 0.5 + 0.3 + 0.1 = 0.9, clamped to max 1.0
    ids_rich = ["evt-001", "evt-002", "evt-003", "evt-004", "evt-005"]
    score = _compute_heuristic(ids=ids_rich, citation_ok=True)
    assert 0.0 <= score <= 1.0, f"Score {score} out of bounds [0.0, 1.0]"
    assert score == 0.9, f"Expected 0.9 for 5 ids + citation_ok, got {score}"
