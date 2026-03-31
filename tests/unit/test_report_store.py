"""
Unit tests for SQLiteStore report CRUD methods (Phase 18-01).

Uses an in-memory (tmp_path) SQLite database so tests are fully isolated
and leave no files behind.
"""

import tempfile
from pathlib import Path

import pytest

from backend.stores.sqlite_store import SQLiteStore


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    """Create a temporary SQLiteStore for each test."""
    return SQLiteStore(data_dir=str(tmp_path))


def _make_report(
    report_id: str = "rpt-001",
    report_type: str = "investigation",
    title: str = "Test Report",
    subject_id: str | None = "inv-abc",
    period_start: str | None = None,
    period_end: str | None = None,
    content_json: str = '{"pdf_b64": "aGVsbG8="}',
    created_at: str = "2026-03-31T12:00:00+00:00",
) -> dict:
    return {
        "id": report_id,
        "type": report_type,
        "title": title,
        "subject_id": subject_id,
        "period_start": period_start,
        "period_end": period_end,
        "content_json": content_json,
        "created_at": created_at,
    }


def test_insert_and_get_report(store: SQLiteStore) -> None:
    """Inserting a report and retrieving it by id returns all fields correctly."""
    data = _make_report()
    store.insert_report(data)

    result = store.get_report("rpt-001")

    assert result is not None
    assert result["id"] == "rpt-001"
    assert result["type"] == "investigation"
    assert result["title"] == "Test Report"
    assert result["subject_id"] == "inv-abc"
    assert result["period_start"] is None
    assert result["period_end"] is None
    assert result["content_json"] == '{"pdf_b64": "aGVsbG8="}'
    assert result["created_at"] == "2026-03-31T12:00:00+00:00"


def test_list_reports_ordered(store: SQLiteStore) -> None:
    """list_reports returns records in created_at DESC order."""
    older = _make_report(
        report_id="rpt-old",
        title="Old Report",
        created_at="2026-03-01T08:00:00+00:00",
    )
    newer = _make_report(
        report_id="rpt-new",
        title="New Report",
        created_at="2026-03-31T18:00:00+00:00",
    )
    # Insert older first, then newer
    store.insert_report(older)
    store.insert_report(newer)

    reports = store.list_reports()

    assert len(reports) == 2
    # Newest should be first (DESC)
    assert reports[0]["id"] == "rpt-new"
    assert reports[1]["id"] == "rpt-old"


def test_get_report_missing(store: SQLiteStore) -> None:
    """get_report on a non-existent id returns None."""
    result = store.get_report("does-not-exist")
    assert result is None
