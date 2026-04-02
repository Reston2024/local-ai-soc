"""Eval tests for P22-T02: Confidence scoring."""
from __future__ import annotations

import pytest

from backend.stores.sqlite_store import SQLiteStore  # noqa: F401


@pytest.mark.skip(reason="stub — implemented in 22-02")
def test_column_exists():
    """confidence_score column exists in llm_audit_provenance on fresh SQLiteStore."""
    pass


@pytest.mark.skip(reason="stub — implemented in 22-02")
def test_score_heuristic_grounded():
    """Heuristic score >= 0.5 when grounding_event_ids is non-empty."""
    pass


@pytest.mark.skip(reason="stub — implemented in 22-02")
def test_score_heuristic_ungrounded():
    """Heuristic score == 0.0 when grounding_event_ids is empty and no template."""
    pass


@pytest.mark.skip(reason="stub — implemented in 22-02")
def test_score_bounded():
    """Heuristic score is always between 0.0 and 1.0 inclusive."""
    pass
