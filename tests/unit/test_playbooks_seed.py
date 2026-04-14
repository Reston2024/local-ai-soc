"""Phase 38/39/46: Playbook seeding tests (30 playbooks after Phase 46 expansion)."""
import pytest
import sqlite3
from backend.data.builtin_playbooks import BUILTIN_PLAYBOOKS

_EXPECTED_COUNT = 30  # Phase 46 expanded set (added community/aws/cert_sg/guardsight/microsoft)
_VALID_SOURCES = {"cisa", "aws", "cert_sg", "community", "guardsight", "microsoft"}


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
    """Every entry in BUILTIN_PLAYBOOKS must have a valid source.
    Phase 46 expanded sources beyond 'cisa' to include aws, cert_sg, community, guardsight, microsoft.
    """
    for pb in BUILTIN_PLAYBOOKS:
        src = pb.get("source")
        assert src in _VALID_SOURCES, (
            f"{pb['name']} has invalid source={src!r} (expected one of {_VALID_SOURCES})"
        )


def test_all_builtins_have_is_builtin_true():
    """Every entry must declare is_builtin=True."""
    for pb in BUILTIN_PLAYBOOKS:
        assert pb.get("is_builtin") is True, f"Missing is_builtin=True on {pb['name']}"


def test_all_builtins_have_steps():
    """Every playbook must have at least 4 steps.
    CISA playbooks have >= 6; community/cert_sg/aws/guardsight/microsoft may have 4-5.
    """
    for pb in BUILTIN_PLAYBOOKS:
        assert len(pb.get("steps", [])) >= 4, (
            f"{pb['name']} has only {len(pb.get('steps', []))} steps (expected >= 4)"
        )
