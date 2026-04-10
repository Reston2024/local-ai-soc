"""Unit tests for playbook_rows support in merge_and_sort_timeline (Wave 0 stubs — 35-01)."""
from __future__ import annotations

import pytest

from backend.api.timeline import merge_and_sort_timeline, TimelineItem


def _make_playbook_row(
    run_id: str = "run-abc123",
    playbook_name: str = "Isolation Response",
    status: str = "completed",
    started_at: str = "2026-04-10T12:00:00Z",
    investigation_id: str = "inv-001",
) -> dict:
    return {
        "run_id": run_id,
        "playbook_name": playbook_name,
        "status": status,
        "started_at": started_at,
        "investigation_id": investigation_id,
    }


def test_playbook_row_produces_timeline_item():
    """merge_and_sort_timeline with one playbook_row yields one item_type='playbook'."""
    rows = [_make_playbook_row()]
    result = merge_and_sort_timeline([], [], [], rows)
    playbook_items = [i for i in result if i.item_type == "playbook"]
    assert len(playbook_items) == 1


def test_playbook_row_title_format():
    """Title format is 'Playbook: [name] — [status]' exactly."""
    row = _make_playbook_row(playbook_name="Isolation Response", status="completed")
    result = merge_and_sort_timeline([], [], [], [row])
    playbook_items = [i for i in result if i.item_type == "playbook"]
    assert playbook_items[0].title == "Playbook: Isolation Response — completed"


def test_playbook_row_timestamp_matches_started_at():
    """Playbook item's timestamp matches started_at from the dict."""
    started = "2026-04-10T12:00:00Z"
    row = _make_playbook_row(started_at=started)
    result = merge_and_sort_timeline([], [], [], [row])
    playbook_items = [i for i in result if i.item_type == "playbook"]
    assert playbook_items[0].timestamp == started


def test_empty_playbook_rows_produces_no_playbook_items():
    """merge_and_sort_timeline with [] playbook_rows yields no playbook items (no regression)."""
    result = merge_and_sort_timeline([], [], [], [])
    playbook_items = [i for i in result if i.item_type == "playbook"]
    assert playbook_items == []
