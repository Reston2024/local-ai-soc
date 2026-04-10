"""
Risk score computation and decay arithmetic for Phase 33 TIP.

Pure functions — no I/O, no external dependencies.
"""

from __future__ import annotations

from math import floor


# Feed base confidence scores (matching what feed_sync.py sets)
_FEED_BASE_SCORES: dict[str, int] = {
    "feodo": 50,
    "threatfox": 50,
    "cisa_kev": 40,
}


def base_score_for_feed(feed_source: str) -> int:
    """
    Return the base confidence score for a given feed source.

    Args:
        feed_source: One of "feodo", "threatfox", "cisa_kev".

    Returns:
        Integer confidence score. Defaults to 30 for unknown feeds.
    """
    return _FEED_BASE_SCORES.get(feed_source.lower(), 30)


def apply_weekly_decay(score: int, days_elapsed: int) -> int:
    """
    Apply weekly decay arithmetic: 5 pts/week, floor at 0.

    Args:
        score:        Current confidence score (0-100).
        days_elapsed: Number of days since IOC was first seen.

    Returns:
        Decayed score, clamped to [0, score].
    """
    decay = floor(days_elapsed * 5 / 7)
    return max(0, score - decay)
