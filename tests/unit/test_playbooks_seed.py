"""Phase 38/39: CISA seeding tests (19 playbooks after Phase 39 expansion)."""
import pytest
import sqlite3
from backend.data.builtin_playbooks import BUILTIN_PLAYBOOKS

_EXPECTED_COUNT = 19  # Phase 39 expanded set


def _make_playbooks_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE playbooks (
            playbook_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            trigger_conditions TEXT NOT NULL DEFAULT '[]',
            steps TEXT NOT NULL DEFAULT '[]',
            version TEXT NOT NULL DEFAULT '1.0',
            is_builtin INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'custom',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()


def test_builtin_playbooks_is_four():
    """BUILTIN_PLAYBOOKS must have the expected CISA playbook count."""
    assert len(BUILTIN_PLAYBOOKS) == _EXPECTED_COUNT


def test_all_builtins_have_source_cisa():
    """Every entry in BUILTIN_PLAYBOOKS must have source='cisa'."""
    for pb in BUILTIN_PLAYBOOKS:
        assert pb.get("source") == "cisa", f"Missing source=cisa on {pb['name']}"


def test_all_builtins_have_is_builtin_true():
    """Every entry must declare is_builtin=True."""
    for pb in BUILTIN_PLAYBOOKS:
        assert pb.get("is_builtin") is True, f"Missing is_builtin=True on {pb['name']}"


def test_all_builtins_have_steps():
    """Every CISA playbook must have at least 6 steps."""
    for pb in BUILTIN_PLAYBOOKS:
        assert len(pb.get("steps", [])) >= 6, (
            f"{pb['name']} has only {len(pb.get('steps', []))} steps (expected >= 6)"
        )
