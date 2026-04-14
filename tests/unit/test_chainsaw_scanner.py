"""
Unit tests for Phase 49 Chainsaw EVTX threat hunting integration.
CHA-01..CHA-03: Record mapping, level normalization, MITRE tag extraction,
                tactic extraction, no-binary guard, dedup skip, migration idempotence.

The importorskip at module level causes the entire file to skip atomically
when ingestion.chainsaw_scanner is absent (matches Phase 48 pattern).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

# Skip the entire file if the implementation module does not yet exist.
chainsaw_scanner = pytest.importorskip(
    "ingestion.chainsaw_scanner",
    reason="Implementation not yet present — will be created in Plan 49-02",
)


# ---------------------------------------------------------------------------
# CHA-02: Record mapping
# ---------------------------------------------------------------------------
def test_record_mapping():
    """chainsaw_record_to_detection(sample_record) returns DetectionRecord with
    rule_id starting 'chainsaw-', correct rule_name, correct severity,
    attack_technique from tags list (CHA-02).
    """
    from ingestion.chainsaw_scanner import chainsaw_record_to_detection

    rec = {
        "name": "Mimikatz",
        "level": "high",
        "tags": ["attack.credential_access", "attack.t1003"],
        "id": "abc",
        "group": "Sigma",
        "status": "experimental",
    }
    det = chainsaw_record_to_detection(rec, "test.evtx")
    assert det.rule_id == "chainsaw-abc"
    assert det.rule_name == "Mimikatz"
    assert det.severity == "high"
    assert det.attack_technique == "T1003"
    assert det.attack_tactic == "Credential Access"
    assert "[Chainsaw]" in det.explanation


# ---------------------------------------------------------------------------
# CHA-02: Level normalisation
# ---------------------------------------------------------------------------
def test_level_normalization():
    """_LEVEL_MAP maps critical/high/medium/low/informational/info strings
    correctly; unknown values default to 'medium' (CHA-02).
    """
    from ingestion.chainsaw_scanner import _LEVEL_MAP

    assert _LEVEL_MAP["critical"] == "critical"
    assert _LEVEL_MAP["high"] == "high"
    assert _LEVEL_MAP["medium"] == "medium"
    assert _LEVEL_MAP["low"] == "low"
    assert _LEVEL_MAP["informational"] == "informational"
    assert _LEVEL_MAP["info"] == "informational"
    assert _LEVEL_MAP.get("bogus", "medium") == "medium"


# ---------------------------------------------------------------------------
# CHA-02: MITRE technique extraction from tags
# ---------------------------------------------------------------------------
def test_mitre_tag_extraction():
    """MITRE technique extracted from tags list: 'attack.t1003.001' -> 'T1003.001',
    'attack.t1003' -> 'T1003'; entries without t#### pattern ignored (CHA-02).
    """
    from ingestion.chainsaw_scanner import chainsaw_record_to_detection

    # Sub-technique
    rec1 = {"name": "Test", "level": "high", "tags": ["attack.t1003.001"], "id": "x1"}
    det1 = chainsaw_record_to_detection(rec1, "test.evtx")
    assert det1.attack_technique == "T1003.001"

    # Base technique
    rec2 = {"name": "Test", "level": "high", "tags": ["attack.t1003"], "id": "x2"}
    det2 = chainsaw_record_to_detection(rec2, "test.evtx")
    assert det2.attack_technique == "T1003"

    # Tactic only (no technique)
    rec3 = {"name": "Test", "level": "high", "tags": ["attack.credential_access"], "id": "x3"}
    det3 = chainsaw_record_to_detection(rec3, "test.evtx")
    assert det3.attack_technique is None

    # Empty tags
    rec4 = {"name": "Test", "level": "high", "tags": [], "id": "x4"}
    det4 = chainsaw_record_to_detection(rec4, "test.evtx")
    assert det4.attack_technique is None


# ---------------------------------------------------------------------------
# CHA-02: MITRE tactic extraction from tags
# ---------------------------------------------------------------------------
def test_tactic_extraction():
    """MITRE tactic extracted from tags list: 'attack.credential_access' ->
    'Credential Access'; unknown tactic tags return None (CHA-02).
    """
    from ingestion.chainsaw_scanner import chainsaw_record_to_detection

    rec1 = {"name": "Test", "level": "high", "tags": ["attack.credential_access"], "id": "y1"}
    det1 = chainsaw_record_to_detection(rec1, "test.evtx")
    assert det1.attack_tactic == "Credential Access"

    rec2 = {"name": "Test", "level": "high", "tags": ["attack.lateral_movement"], "id": "y2"}
    det2 = chainsaw_record_to_detection(rec2, "test.evtx")
    assert det2.attack_tactic == "Lateral Movement"

    # Technique tag only — no tactic slug
    rec3 = {"name": "Test", "level": "high", "tags": ["attack.t1003"], "id": "y3"}
    det3 = chainsaw_record_to_detection(rec3, "test.evtx")
    assert det3.attack_tactic is None


# ---------------------------------------------------------------------------
# CHA-01: No-binary guard
# ---------------------------------------------------------------------------
def test_no_binary(monkeypatch):
    """When CHAINSAW_BIN is None, scan_evtx('any.evtx') yields zero records
    and does not raise (CHA-01).
    """
    import ingestion.chainsaw_scanner as cs
    from ingestion.chainsaw_scanner import scan_evtx

    monkeypatch.setattr(cs, "CHAINSAW_BIN", None)
    records = list(scan_evtx("any.evtx"))
    assert records == []


# ---------------------------------------------------------------------------
# CHA-03: Dedup skip
# ---------------------------------------------------------------------------
def test_dedup_skip():
    """SQLiteStore.mark_chainsaw_scanned() + is_chainsaw_scanned() provide
    SHA-256-based dedup; files already scanned return True (CHA-03).
    """
    from backend.stores.sqlite_store import SQLiteStore

    store = SQLiteStore(path=":memory:")
    assert store.is_chainsaw_scanned("abc") is False
    store.mark_chainsaw_scanned("abc", "test.evtx", 5)
    assert store.is_chainsaw_scanned("abc") is True
    assert store.is_chainsaw_scanned("other") is False


# ---------------------------------------------------------------------------
# CHA-03: Migration idempotence
# ---------------------------------------------------------------------------
def test_migration_idempotent():
    """chainsaw_scanned_files table exists after SQLiteStore(:memory:) instantiation;
    second CREATE IF NOT EXISTS does not raise (CHA-03).
    """
    import sqlite3
    from backend.stores.sqlite_store import SQLiteStore, _CHAINSAW_DDL

    store = SQLiteStore(path=":memory:")
    # Table must exist
    tables = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chainsaw_scanned_files'"
    ).fetchall()
    assert len(tables) == 1
    # Second execution is idempotent (CREATE IF NOT EXISTS)
    store._conn.execute(_CHAINSAW_DDL)  # must not raise
