"""
Wave 0 TDD stubs for Phase 48 Hayabusa EVTX threat hunting integration.
P48-T01: Record mapping, level normalization, MITRE tag filter, no-binary,
         dedup skip, migration idempotence.

All tests skip via pytest.importorskip if ingestion.hayabusa_scanner is absent.
Per-test @pytest.mark.skip ensures stubs don't run even if module is present
before Plan 48-02 implements the full behaviour.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

# Skip the entire file if the implementation module does not yet exist.
# This is the same importorskip pattern used in Phase 44 and Phase 45.
pytest.importorskip(
    "ingestion.hayabusa_scanner",
    reason="Wave 0 stub — implementation pending in Plan 48-02",
)


# ---------------------------------------------------------------------------
# HAY-01: Record mapping
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Wave 0 stub — implementation pending")
def test_record_mapping():
    """hayabusa_record_to_detection(sample_record) returns a DetectionRecord with
    rule_id starting with 'hayabusa-', correct rule_name, correct severity,
    and attack_technique matching a T#### entry (HAY-01).
    """
    pytest.skip("Wave 0 stub")


# ---------------------------------------------------------------------------
# HAY-02: Level normalisation
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Wave 0 stub — implementation pending")
def test_level_normalization():
    """_LEVEL_MAP maps 'crit'->'critical', 'high'->'high', 'med'->'medium',
    'medium'->'medium', 'low'->'low', 'info'->'informational'; unknown values
    default to 'medium' (HAY-02).
    """
    pytest.skip("Wave 0 stub")


# ---------------------------------------------------------------------------
# HAY-03: MITRE tag filter
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Wave 0 stub — implementation pending")
def test_mitre_tag_filter():
    """MitreTags ['T1059.001', 'G0016', 'S0002', 'T1078'] -> attack_technique
    == 'T1059.001'; G#### and S#### entries are excluded (HAY-03).
    """
    pytest.skip("Wave 0 stub")


# ---------------------------------------------------------------------------
# HAY-04: No-binary guard
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Wave 0 stub — implementation pending")
def test_no_binary():
    """When HAYABUSA_BIN is None/empty, scan_evtx('any.evtx') yields zero
    records and does not raise (HAY-04).
    """
    pytest.skip("Wave 0 stub")


# ---------------------------------------------------------------------------
# HAY-05: Dedup skip
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Wave 0 stub — implementation pending")
def test_dedup_skip():
    """HayabusaScanner.scan() with a SHA-256 already in hayabusa_scanned_files
    returns 0 findings without calling subprocess (HAY-05).
    """
    pytest.skip("Wave 0 stub")


# ---------------------------------------------------------------------------
# HAY-06: Migration idempotence
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Wave 0 stub — implementation pending")
def test_migration_idempotent():
    """Calling SQLiteStore._run_migrations() twice on the same in-memory SQLite
    db does not raise; detection_source column exists after both calls (HAY-06).
    """
    pytest.skip("Wave 0 stub")
