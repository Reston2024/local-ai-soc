"""
Unit tests for GET /api/detections/quality endpoint.

Tests verify response schema, zero-feedback graceful degradation, and TP/FP rate math.
All tests mock the SQLite store and do not require a running server.
"""
from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------
try:
    from backend.api.detection_quality import _compute_quality_metrics
    _MODULE_AVAILABLE = True
except ImportError:
    _MODULE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _MODULE_AVAILABLE,
    reason="detection_quality module not available",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_in_memory_db() -> sqlite3.Connection:
    """Build a minimal in-memory SQLite DB with detections + feedback tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE detections (
            id              TEXT PRIMARY KEY,
            rule_id         TEXT,
            rule_name       TEXT,
            severity        TEXT,
            attack_technique TEXT,
            attack_tactic   TEXT,
            created_at      TEXT NOT NULL
        );

        CREATE TABLE feedback (
            id           TEXT PRIMARY KEY,
            detection_id TEXT NOT NULL UNIQUE,
            verdict      TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        );
        """
    )
    return conn


# ---------------------------------------------------------------------------
# Test 1 — valid schema returned for empty database
# ---------------------------------------------------------------------------
def test_quality_empty_database():
    """Zero feedback + zero detections must return valid zeroed structure, not 500."""
    conn = _make_in_memory_db()
    result = _compute_quality_metrics(conn)

    # Top-level keys present
    assert "rule_metrics" in result
    assert "summary" in result
    assert "mitre_coverage" in result

    # Rule metrics is an empty list (no detections)
    assert result["rule_metrics"] == []

    # Summary has all required keys and zero values
    summary = result["summary"]
    assert summary["total_rules_fired"] == 0
    assert summary["rules_with_feedback"] == 0
    assert summary["overall_tp_rate"] == 0.0
    assert summary["overall_fp_rate"] == 0.0
    assert summary["total_detections"] == 0
    assert summary["analyst_reviewed"] == 0

    # MITRE coverage is empty
    mitre = result["mitre_coverage"]
    assert mitre["tactics_covered"] == []
    assert mitre["technique_count"] == 0


# ---------------------------------------------------------------------------
# Test 2 — valid schema returned when detections exist but no feedback
# ---------------------------------------------------------------------------
def test_quality_endpoint_returns_valid_schema():
    """Detections present but no feedback → zero rates, rule rows with correct fields."""
    conn = _make_in_memory_db()
    conn.execute(
        "INSERT INTO detections VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("d1", "sigma-T1059", "PowerShell Exec", "high", "T1059.001", "TA0002", "2026-04-17T10:00:00Z"),
    )
    conn.execute(
        "INSERT INTO detections VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("d2", "sigma-T1059", "PowerShell Exec", "high", "T1059.001", "TA0002", "2026-04-17T11:00:00Z"),
    )
    conn.execute(
        "INSERT INTO detections VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("d3", "sigma-T1003", "Credential Dump", "critical", "T1003", "TA0006", "2026-04-17T12:00:00Z"),
    )
    conn.commit()

    result = _compute_quality_metrics(conn)

    # Structural checks
    assert isinstance(result["rule_metrics"], list)
    assert len(result["rule_metrics"]) == 2  # two distinct rule_ids

    rule_fields = {
        "rule_id", "rule_name", "total_hits", "analyst_reviewed",
        "confirmed_tp", "confirmed_fp", "tp_rate", "fp_rate", "last_hit",
    }
    for rule in result["rule_metrics"]:
        assert rule_fields.issubset(rule.keys()), f"Missing keys in rule row: {rule}"

    summary = result["summary"]
    assert summary["total_detections"] == 3
    assert summary["total_rules_fired"] == 2
    assert summary["analyst_reviewed"] == 0
    assert summary["overall_tp_rate"] == 0.0
    assert summary["overall_fp_rate"] == 0.0

    # MITRE coverage
    mitre = result["mitre_coverage"]
    assert "TA0002" in mitre["tactics_covered"]
    assert "TA0006" in mitre["tactics_covered"]
    assert mitre["technique_count"] == 2


# ---------------------------------------------------------------------------
# Test 3 — TP/FP rate calculation correctness
# ---------------------------------------------------------------------------
def test_tp_fp_rate_calculation():
    """3 TP + 1 FP for one rule → tp_rate=0.75, fp_rate=0.25 at rule and summary level."""
    conn = _make_in_memory_db()

    # Insert 4 detections for same rule
    for i in range(4):
        conn.execute(
            "INSERT INTO detections VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                f"det-{i}",
                "sigma-T1059-001",
                "PowerShell Execution",
                "high",
                "T1059.001",
                "TA0002",
                f"2026-04-17T0{i}:00:00Z",
            ),
        )

    # 3 TP verdicts + 1 FP verdict
    for i in range(3):
        conn.execute(
            "INSERT INTO feedback VALUES (?, ?, ?, ?, ?)",
            (f"fb-{i}", f"det-{i}", "TP", "2026-04-17T10:00:00Z", "2026-04-17T10:00:00Z"),
        )
    conn.execute(
        "INSERT INTO feedback VALUES (?, ?, ?, ?, ?)",
        ("fb-3", "det-3", "FP", "2026-04-17T10:00:00Z", "2026-04-17T10:00:00Z"),
    )
    conn.commit()

    result = _compute_quality_metrics(conn)

    # Exactly one rule
    assert len(result["rule_metrics"]) == 1
    rule = result["rule_metrics"][0]

    assert rule["rule_id"] == "sigma-T1059-001"
    assert rule["rule_name"] == "PowerShell Execution"
    assert rule["total_hits"] == 4
    assert rule["analyst_reviewed"] == 4
    assert rule["confirmed_tp"] == 3
    assert rule["confirmed_fp"] == 1
    assert rule["tp_rate"] == pytest.approx(0.75, abs=1e-4)
    assert rule["fp_rate"] == pytest.approx(0.25, abs=1e-4)

    # Summary level
    summary = result["summary"]
    assert summary["total_detections"] == 4
    assert summary["rules_with_feedback"] == 1
    assert summary["analyst_reviewed"] == 4
    assert summary["overall_tp_rate"] == pytest.approx(0.75, abs=1e-4)
    assert summary["overall_fp_rate"] == pytest.approx(0.25, abs=1e-4)


# ---------------------------------------------------------------------------
# Test 4 — graceful degradation: broken connection returns zeros, not exception
# ---------------------------------------------------------------------------
def test_quality_broken_connection_returns_zeros():
    """A broken/closed connection must NOT raise — must return zeroed structure."""
    conn = sqlite3.connect(":memory:")
    conn.close()  # deliberately close it to trigger an error path

    result = _compute_quality_metrics(conn)

    # Must still return valid structure
    assert "rule_metrics" in result
    assert "summary" in result
    assert "mitre_coverage" in result
    assert result["rule_metrics"] == []
    assert result["summary"]["total_detections"] == 0
