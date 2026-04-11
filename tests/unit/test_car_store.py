"""
Wave 0 TDD stubs for Phase 39 CARStore.
P39-T01 (SQLite DDL + bulk_insert + analytic_count),
P39-T02 (get_analytics_for_technique + sub-technique normalization),
P39-T03 (detection enrichment contract).

Uses in-memory SQLite — no disk I/O.
All stubs fail RED until Plan 02 implements CARStore.
"""
from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing CARStore — skip individual tests if not available
# ---------------------------------------------------------------------------
try:
    from backend.services.car.car_store import CARStore
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _make_conn() -> sqlite3.Connection:
    """Create in-memory SQLite connection with row_factory set."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row  # CRITICAL — must set this or dict(row) fails in tests
    return conn


# ---------------------------------------------------------------------------
# Sample analytics for seeding tests
# ---------------------------------------------------------------------------

SAMPLE_ANALYTICS = [
    {
        "analytic_id": "CAR-2020-09-001",
        "technique_id": "T1053",
        "title": "Scheduled Task - FileAccess",
        "description": "Detects scheduled task file access.",
        "log_sources": "file/create/file_path",
        "analyst_notes": "",
        "pseudocode": "files = search File:Create\n...",
        "coverage_level": "Low",
        "platforms": '["Windows"]',
    },
    {
        "analytic_id": "CAR-2021-01-001",
        "technique_id": "T1059",
        "title": "Detecting Cmd.exe Usage",
        "description": "Detects cmd.exe execution.",
        "log_sources": "process/create",
        "analyst_notes": "Focus on unusual parent processes.",
        "pseudocode": "processes = search Process:Create WHERE exe == 'cmd.exe'",
        "coverage_level": "Moderate",
        "platforms": '["Windows"]',
    },
]


# ---------------------------------------------------------------------------
# test_car_store_table_exists
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — CARStore not yet implemented")
def test_car_store_table_exists():
    """CARStore(conn) runs DDL and car_analytics table appears in sqlite_master."""
    conn = _make_conn()
    _store = CARStore(conn)

    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    assert "car_analytics" in tables, f"car_analytics table not found; found: {tables}"


# ---------------------------------------------------------------------------
# test_bulk_insert_seeding
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — CARStore not yet implemented")
def test_bulk_insert_seeding():
    """bulk_insert(list_of_dicts) inserts all entries; analytic_count() == len(entries)."""
    conn = _make_conn()
    store = CARStore(conn)

    store.bulk_insert(SAMPLE_ANALYTICS)

    assert store.analytic_count() == len(SAMPLE_ANALYTICS), (
        f"Expected {len(SAMPLE_ANALYTICS)} analytics after bulk_insert, "
        f"got {store.analytic_count()}"
    )


# ---------------------------------------------------------------------------
# test_analytic_count
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — CARStore not yet implemented")
def test_analytic_count():
    """Fresh store returns 0; after bulk_insert returns > 0."""
    conn = _make_conn()
    store = CARStore(conn)

    assert store.analytic_count() == 0, "Expected 0 analytics in fresh store"

    store.bulk_insert(SAMPLE_ANALYTICS)

    assert store.analytic_count() > 0, "Expected > 0 analytics after bulk_insert"


# ---------------------------------------------------------------------------
# test_get_analytics_for_technique
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — CARStore not yet implemented")
def test_get_analytics_for_technique():
    """get_analytics_for_technique('T1059') returns non-empty list ordered by analytic_id."""
    conn = _make_conn()
    store = CARStore(conn)
    store.bulk_insert(SAMPLE_ANALYTICS)

    results = store.get_analytics_for_technique("T1059")

    assert isinstance(results, list), "Expected list result"
    assert len(results) > 0, "Expected at least one result for T1059"
    assert results[0]["analytic_id"] == "CAR-2021-01-001", (
        f"Expected CAR-2021-01-001, got {results[0]['analytic_id']}"
    )


# ---------------------------------------------------------------------------
# test_subtechnique_normalization
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — CARStore not yet implemented")
def test_subtechnique_normalization():
    """get_analytics_for_technique('T1059.001') falls back to parent T1059 lookup."""
    conn = _make_conn()
    store = CARStore(conn)
    store.bulk_insert(SAMPLE_ANALYTICS)

    # T1059.001 is a sub-technique of T1059 — should return T1059 analytics
    results = store.get_analytics_for_technique("T1059.001")

    assert isinstance(results, list), "Expected list result"
    assert len(results) > 0, (
        "Expected at least one result for T1059.001 via parent T1059 fallback"
    )
    # Should return the same analytic as querying T1059 directly
    assert any(r["analytic_id"] == "CAR-2021-01-001" for r in results), (
        "Expected CAR-2021-01-001 in sub-technique results"
    )


# ---------------------------------------------------------------------------
# test_no_match_returns_empty
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — CARStore not yet implemented")
def test_no_match_returns_empty():
    """get_analytics_for_technique('T9999') returns empty list without error."""
    conn = _make_conn()
    store = CARStore(conn)
    store.bulk_insert(SAMPLE_ANALYTICS)

    results = store.get_analytics_for_technique("T9999")

    assert isinstance(results, list), "Expected list result"
    assert results == [], f"Expected empty list for non-existent technique, got {results}"


# ---------------------------------------------------------------------------
# test_detection_enrichment_field
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — CARStore not yet implemented")
def test_detection_enrichment_field():
    """CARStore.get_analytics_for_technique returns matching analytic for T1053."""
    conn = _make_conn()
    store = CARStore(conn)
    store.bulk_insert(SAMPLE_ANALYTICS)

    # Simulate what detection enrichment would do: look up by attack_technique
    detection = {"attack_technique": "T1053", "rule_id": "sigma_123"}
    results = store.get_analytics_for_technique(detection["attack_technique"])

    assert len(results) == 1, f"Expected 1 result for T1053, got {len(results)}"
    assert results[0]["analytic_id"] == "CAR-2020-09-001", (
        f"Expected CAR-2020-09-001, got {results[0]['analytic_id']}"
    )


# ---------------------------------------------------------------------------
# test_detection_no_technique_null
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — CARStore not yet implemented")
def test_detection_no_technique_null():
    """get_analytics_for_technique(None) and get_analytics_for_technique('') return [] gracefully."""
    conn = _make_conn()
    store = CARStore(conn)
    store.bulk_insert(SAMPLE_ANALYTICS)

    # Empty string should return empty list
    result_empty = store.get_analytics_for_technique("")
    assert isinstance(result_empty, list), "Expected list for empty string"
    assert result_empty == [], f"Expected [] for empty string, got {result_empty}"

    # None should return empty list without raising
    result_none = store.get_analytics_for_technique(None)
    assert isinstance(result_none, list), "Expected list for None"
    assert result_none == [], f"Expected [] for None, got {result_none}"
