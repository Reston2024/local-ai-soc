"""
Wave-0 test stub: output contract for backend/api/timeline.py.

These tests are intentionally RED until plan 14-03 implements
TimelineItem and merge_and_sort_timeline().
"""

import pytest

try:
    from backend.api.timeline import TimelineItem, merge_and_sort_timeline
except ImportError:
    TimelineItem = None  # type: ignore
    merge_and_sort_timeline = None  # type: ignore


# ---------------------------------------------------------------------------
# TimelineItem schema
# ---------------------------------------------------------------------------


def test_timeline_item_fields():
    """TimelineItem has all required fields with correct types."""
    assert TimelineItem is not None, "backend.api.timeline not implemented yet"
    item = TimelineItem(
        item_id="ev-abc123",
        item_type="event",
        timestamp="2026-01-01T10:00:00Z",
        title="User login from suspicious host",
        severity="high",
        attack_technique="T1078",
        attack_tactic="initial-access",
        entity_labels=["host1", "user_admin"],
        raw_id="ev-abc123",
    )
    assert item.item_id == "ev-abc123"
    assert item.item_type == "event"
    assert item.timestamp == "2026-01-01T10:00:00Z"
    assert isinstance(item.title, str)
    # Optional fields
    assert item.severity == "high"
    assert item.attack_technique == "T1078"
    assert item.attack_tactic == "initial-access"
    assert isinstance(item.entity_labels, list)
    assert item.raw_id == "ev-abc123"


def test_timeline_item_type_accepts_valid_values():
    """TimelineItem.item_type accepts 'event', 'detection', and 'edge'."""
    assert TimelineItem is not None, "backend.api.timeline not implemented yet"
    for item_type in ("event", "detection", "edge"):
        item = TimelineItem(
            item_id=f"id-{item_type}",
            item_type=item_type,  # type: ignore[arg-type]
            timestamp="2026-01-01T00:00:00Z",
            title=f"Test {item_type}",
            severity=None,
            attack_technique=None,
            attack_tactic=None,
            entity_labels=[],
            raw_id=f"id-{item_type}",
        )
        assert item.item_type == item_type


def test_merge_and_sort_timeline_sorted():
    """merge_and_sort_timeline returns list sorted ascending by timestamp."""
    assert merge_and_sort_timeline is not None, "backend.api.timeline not implemented yet"
    # Two-argument call — edge_rows and playbook_rows use defaults
    result = merge_and_sort_timeline(
        [("ev-1", "2026-01-01T10:00:00Z", "login", "low", "host1", None, None, None, None)],
        [
            {
                "id": "det-1",
                "rule_name": "Brute Force",
                "severity": "high",
                "attack_technique": None,
                "attack_tactic": None,
                "created_at": "2026-01-01T09:00:00Z",
            }
        ],
    )
    assert isinstance(result, list)
    assert len(result) == 2
    # Sorted ascending — detection (09:00) before event (10:00)
    assert result[0].timestamp <= result[1].timestamp
