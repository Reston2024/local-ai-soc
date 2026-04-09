"""
Unit tests for hunt engine — validate_hunt_sql, _rank_results, HuntResult.

TDD RED phase: all tests fail with ImportError because hunt_engine.py does not exist yet.
"""

import pytest

from backend.services.hunt_engine import HuntEngine, HuntResult, _rank_results, validate_hunt_sql


# ---------------------------------------------------------------------------
# validate_hunt_sql — allowed queries
# ---------------------------------------------------------------------------

def test_validate_hunt_sql_valid_select():
    """Test 1: valid SELECT against normalized_events returns True."""
    result = validate_hunt_sql("SELECT * FROM normalized_events LIMIT 10")
    assert result is True


# ---------------------------------------------------------------------------
# validate_hunt_sql — DDL / DML rejections
# ---------------------------------------------------------------------------

def test_validate_hunt_sql_ddl_drop():
    """Test 2: DROP TABLE is rejected as DDL."""
    with pytest.raises(ValueError, match="DDL not allowed"):
        validate_hunt_sql("DROP TABLE normalized_events")


def test_validate_hunt_sql_delete():
    """Test 3: DELETE is rejected — only SELECT allowed."""
    with pytest.raises(ValueError, match="only SELECT allowed"):
        validate_hunt_sql("DELETE FROM normalized_events WHERE 1=1")


def test_validate_hunt_sql_system_table():
    """Test 4: SELECT from sqlite_master is rejected — system table."""
    with pytest.raises(ValueError, match="only normalized_events table allowed"):
        validate_hunt_sql("SELECT * FROM sqlite_master")


def test_validate_hunt_sql_multi_statement():
    """Test 5: multiple statements separated by semicolons are rejected."""
    with pytest.raises(ValueError, match="multiple statements"):
        validate_hunt_sql("SELECT * FROM normalized_events; DROP TABLE x")


def test_validate_hunt_sql_attach():
    """Test 6: ATTACH DATABASE is rejected."""
    with pytest.raises(ValueError, match="ATTACH not allowed"):
        validate_hunt_sql("ATTACH DATABASE '/etc/passwd' AS x")


def test_validate_hunt_sql_copy():
    """Test 7: COPY statement is rejected."""
    with pytest.raises(ValueError, match="COPY not allowed"):
        validate_hunt_sql("COPY normalized_events TO '/tmp/out'")


# ---------------------------------------------------------------------------
# _rank_results — severity ordering
# ---------------------------------------------------------------------------

def test_rank_results_severity_order():
    """Test 8: _rank_results returns rows sorted critical > high > medium by severity, then ts descending."""
    rows = [
        {"severity": "medium", "ts": "2024-01-01T10:00:00Z"},
        {"severity": "critical", "ts": "2024-01-01T09:00:00Z"},
        {"severity": "high", "ts": "2024-01-01T08:00:00Z"},
        {"severity": "critical", "ts": "2024-01-01T12:00:00Z"},
    ]
    ranked = _rank_results(rows)
    severities = [r["severity"] for r in ranked]
    # critical rows first (most recent first), then high, then medium
    assert severities[0] == "critical"
    assert severities[1] == "critical"
    assert severities[2] == "high"
    assert severities[3] == "medium"
    # Among criticals, most recent first
    assert ranked[0]["ts"] > ranked[1]["ts"]


# ---------------------------------------------------------------------------
# HuntResult — dataclass fields
# ---------------------------------------------------------------------------

def test_hunt_result_dataclass_fields():
    """Test 9: HuntResult dataclass has expected fields."""
    result = HuntResult(
        hunt_id="test-id",
        query="show all events",
        sql="SELECT * FROM normalized_events LIMIT 5",
        rows=[{"event_id": "1"}],
        row_count=1,
    )
    assert result.hunt_id == "test-id"
    assert result.query == "show all events"
    assert result.sql == "SELECT * FROM normalized_events LIMIT 5"
    assert result.rows == [{"event_id": "1"}]
    assert result.row_count == 1
    assert result.ranked is True
    assert result.created_at is not None
