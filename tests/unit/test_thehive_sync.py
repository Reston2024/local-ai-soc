"""
Phase 52 Wave 0 stubs: TheHive sync/retry queue tests (Plan 52-01).
All 3 stubs SKIP cleanly until Plan 52-03 implements backend/services/thehive_sync.py.
"""
from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

import pytest

# Per-test guard pattern (matches Phase 44/45/48 convention)
_TH_SYNC_AVAILABLE = False
try:
    from backend.services.thehive_sync import (  # noqa: F401
        drain_pending_cases,
        sync_thehive_closures,
    )
    _TH_SYNC_AVAILABLE = True
except ImportError:
    pass


def test_retry_queue_drains():
    """drain_pending_cases() retries pending rows, calls create_case, deletes on success."""
    if not _TH_SYNC_AVAILABLE:
        pytest.skip("backend.services.thehive_sync not yet implemented (Plan 52-03)")

    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE thehive_pending_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detection_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        "INSERT INTO thehive_pending_cases (detection_json, created_at) VALUES (?, datetime('now'))",
        ('{"rule_id": "sigma-1", "severity": "high", "rule_name": "Rule 1", "src_ip": "1.1.1.1"}',),
    )
    conn.execute(
        "INSERT INTO thehive_pending_cases (detection_json, created_at) VALUES (?, datetime('now'))",
        ('{"rule_id": "sigma-2", "severity": "critical", "rule_name": "Rule 2", "src_ip": "2.2.2.2"}',),
    )
    conn.commit()

    mock_client = MagicMock()
    mock_client.create_case.return_value = {"_id": "case-abc", "number": 42}

    drain_pending_cases(mock_client, conn)

    remaining = conn.execute("SELECT COUNT(*) FROM thehive_pending_cases").fetchone()[0]
    assert remaining == 0, f"Expected 0 rows after drain, got {remaining}"
    assert mock_client.create_case.call_count == 2, (
        f"Expected create_case called twice, got {mock_client.create_case.call_count}"
    )


def test_closure_sync_writes_sqlite():
    """sync_thehive_closures() updates detections with TheHive resolution data."""
    if not _TH_SYNC_AVAILABLE:
        pytest.skip("backend.services.thehive_sync not yet implemented (Plan 52-03)")

    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE detections (
            id INTEGER PRIMARY KEY,
            rule_id TEXT,
            thehive_case_id TEXT,
            thehive_status TEXT,
            thehive_analyst TEXT,
            thehive_closed_at TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO detections (id, rule_id, thehive_case_id) VALUES (1, 'sigma-mimikatz', 'TH-001')"
    )
    conn.commit()

    resolved_case = {
        "_id": "TH-001",
        "number": 7,
        "resolutionStatus": "TruePositive",
        "endDate": 1713220800000,
        "assignee": "analyst1",
    }

    mock_client = MagicMock()
    mock_client.find_resolved_cases.return_value = [resolved_case]

    sync_thehive_closures(mock_client, conn)

    row = conn.execute(
        "SELECT thehive_status, thehive_analyst FROM detections WHERE id = 1"
    ).fetchone()
    assert row is not None, "detections row should still exist"
    assert row[0] == "TruePositive", f"Expected thehive_status='TruePositive', got {row[0]}"
    assert row[1] == "analyst1", f"Expected thehive_analyst='analyst1', got {row[1]}"


def test_closure_sync_tolerates_failure():
    """sync_thehive_closures() does not raise when TheHive client raises an exception."""
    if not _TH_SYNC_AVAILABLE:
        pytest.skip("backend.services.thehive_sync not yet implemented (Plan 52-03)")

    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE detections (
            id INTEGER PRIMARY KEY,
            rule_id TEXT,
            thehive_case_id TEXT,
            thehive_status TEXT,
            thehive_analyst TEXT,
            thehive_closed_at TEXT
        )"""
    )
    conn.commit()

    mock_client = MagicMock()
    mock_client.find_resolved_cases.side_effect = Exception("TheHive connection refused")

    result = sync_thehive_closures(mock_client, conn)

    assert result is None, f"Expected None return on error, got {result}"
