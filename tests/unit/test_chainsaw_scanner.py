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
pytest.importorskip(
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
    pass


# ---------------------------------------------------------------------------
# CHA-02: Level normalisation
# ---------------------------------------------------------------------------
def test_level_normalization():
    """_LEVEL_MAP maps critical/high/medium/low/informational/info strings
    correctly; unknown values default to 'medium' (CHA-02).
    """
    pass


# ---------------------------------------------------------------------------
# CHA-02: MITRE technique extraction from tags
# ---------------------------------------------------------------------------
def test_mitre_tag_extraction():
    """MITRE technique extracted from tags list: 'attack.t1003.001' -> 'T1003.001',
    'attack.t1003' -> 'T1003'; entries without t#### pattern ignored (CHA-02).
    """
    pass


# ---------------------------------------------------------------------------
# CHA-02: MITRE tactic extraction from tags
# ---------------------------------------------------------------------------
def test_tactic_extraction():
    """MITRE tactic extracted from tags list: 'attack.credential_access' ->
    'Credential Access'; unknown tactic tags return None (CHA-02).
    """
    pass


# ---------------------------------------------------------------------------
# CHA-01: No-binary guard
# ---------------------------------------------------------------------------
def test_no_binary(monkeypatch):
    """When CHAINSAW_BIN is None, scan_evtx('any.evtx') yields zero records
    and does not raise (CHA-01).
    """
    pass


# ---------------------------------------------------------------------------
# CHA-03: Dedup skip
# ---------------------------------------------------------------------------
def test_dedup_skip():
    """SQLiteStore.mark_chainsaw_scanned() + is_chainsaw_scanned() provide
    SHA-256-based dedup; files already scanned return True (CHA-03).
    """
    pass


# ---------------------------------------------------------------------------
# CHA-03: Migration idempotence
# ---------------------------------------------------------------------------
def test_migration_idempotent():
    """chainsaw_scanned_files table exists after SQLiteStore(:memory:) instantiation;
    second CREATE IF NOT EXISTS does not raise (CHA-03).
    """
    pass
