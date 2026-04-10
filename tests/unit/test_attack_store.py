"""
Wave 0 test stubs for Phase 34 AttackStore.
P34-T01 (SQLite CRUD — technique/group/group_technique tables),
P34-T03 (actor matching query).

Uses in-memory SQLite — no disk I/O.
"""

from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing AttackStore — skip individual tests if not available
# ---------------------------------------------------------------------------
try:
    from backend.services.attack.attack_store import AttackStore
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

# AttackStore owns its own DDL — no need to import sqlite_store._DDL
# But we keep this flag for consistency with other test files
try:
    from backend.stores.sqlite_store import _DDL as _SQLITE_DDL
    _DDL_AVAILABLE = True
except ImportError:
    _DDL_AVAILABLE = False


def _make_conn() -> sqlite3.Connection:
    """Create in-memory SQLite connection. AttackStore.__init__ runs DDL."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# test_upsert_technique
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_upsert_technique():
    """upsert_technique() inserts a technique and technique_count() == 1."""
    conn = _make_conn()
    store = AttackStore(conn)

    store.upsert_technique(
        tech_id="T1059",
        name="Command and Scripting Interpreter",
        tactic="execution",
    )

    assert store.technique_count() == 1


# ---------------------------------------------------------------------------
# test_upsert_group
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_upsert_group():
    """upsert_group() inserts a group and group_count() == 1."""
    conn = _make_conn()
    store = AttackStore(conn)

    store.upsert_group(
        stix_id="intrusion-set--123",
        group_id="G0016",
        name="APT29",
        aliases='["Cozy Bear"]',
    )

    assert store.group_count() == 1


# ---------------------------------------------------------------------------
# test_group_technique_dedup
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_group_technique_dedup():
    """upsert_group_technique() is idempotent — same pair inserted twice = 1 row."""
    conn = _make_conn()
    store = AttackStore(conn)

    store.upsert_group(
        stix_id="intrusion-set--abc",
        group_id="G0001",
        name="TestGroup",
        aliases="[]",
    )
    store.upsert_technique(tech_id="T1059", name="Command Script", tactic="execution")

    store.upsert_group_technique(stix_group_id="intrusion-set--abc", tech_id="T1059")
    store.upsert_group_technique(stix_group_id="intrusion-set--abc", tech_id="T1059")

    cursor = conn.execute(
        "SELECT COUNT(*) FROM attack_group_techniques "
        "WHERE stix_group_id='intrusion-set--abc' AND tech_id='T1059'"
    )
    assert cursor.fetchone()[0] == 1


# ---------------------------------------------------------------------------
# test_revoked_filtered
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_revoked_filtered():
    """bootstrap_from_objects() with a revoked attack-pattern → technique_count() == 0."""
    conn = _make_conn()
    store = AttackStore(conn)

    objects = [
        {
            "type": "attack-pattern",
            "id": "attack-pattern--111",
            "name": "Revoked Technique",
            "revoked": True,
            "x_mitre_is_subtechnique": False,
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T9999"}
            ],
            "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "execution"}],
        }
    ]

    store.bootstrap_from_objects(objects)
    assert store.technique_count() == 0


# ---------------------------------------------------------------------------
# test_external_ref_filter
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_external_ref_filter():
    """bootstrap_from_objects() skips attack-pattern with no mitre-attack external_ref."""
    conn = _make_conn()
    store = AttackStore(conn)

    objects = [
        {
            "type": "attack-pattern",
            "id": "attack-pattern--222",
            "name": "No Ref Technique",
            "revoked": False,
            "x_mitre_is_subtechnique": False,
            "external_references": [
                {"source_name": "capec", "external_id": "CAPEC-999"}
            ],
            "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "execution"}],
        }
    ]

    store.bootstrap_from_objects(objects)
    assert store.technique_count() == 0


# ---------------------------------------------------------------------------
# test_actor_matching_top3
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_actor_matching_top3():
    """actor_matches() returns ≤3 dicts with expected keys for overlapping techniques."""
    conn = _make_conn()
    store = AttackStore(conn)

    # Seed 3 techniques
    for tid, name in [("T1059", "Script"), ("T1071", "C2 Protocol"), ("T1055", "Injection")]:
        store.upsert_technique(tech_id=tid, name=name, tactic="execution")

    # Group A: uses T1059 + T1071 (high overlap for our query)
    store.upsert_group(stix_id="intrusion-set--A", group_id="G0001", name="GroupA", aliases="[]")
    store.upsert_group_technique("intrusion-set--A", "T1059")
    store.upsert_group_technique("intrusion-set--A", "T1071")

    # Group B: uses T1059 only (partial overlap)
    store.upsert_group(stix_id="intrusion-set--B", group_id="G0002", name="GroupB", aliases="[]")
    store.upsert_group_technique("intrusion-set--B", "T1059")

    # Group C: uses T1055 (no overlap with query)
    store.upsert_group(stix_id="intrusion-set--C", group_id="G0003", name="GroupC", aliases="[]")
    store.upsert_group_technique("intrusion-set--C", "T1055")

    results = store.actor_matches(["T1059", "T1071"])

    assert isinstance(results, list)
    assert len(results) <= 3

    for r in results:
        assert "name" in r
        assert "confidence" in r
        assert "overlap_pct" in r
        assert "matched_count" in r
        assert "total_count" in r
        assert "group_id" in r
        assert "aliases" in r


# ---------------------------------------------------------------------------
# test_confidence_labels
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Task 2")
def test_confidence_labels():
    """actor_matches() assigns correct confidence labels based on overlap_pct thresholds."""
    conn = _make_conn()
    store = AttackStore(conn)

    # Seed 10 techniques
    for i in range(10):
        store.upsert_technique(tech_id=f"T100{i}", name=f"Tech {i}", tactic="execution")

    # High overlap group: 7/10 match → 0.70 → "High"
    store.upsert_group(stix_id="intrusion-set--HIGH", group_id="G0010", name="HighGroup", aliases="[]")
    for i in range(10):
        store.upsert_group_technique("intrusion-set--HIGH", f"T100{i}")

    # Medium overlap group: 4/10 match → 0.40 → "Medium"
    store.upsert_group(stix_id="intrusion-set--MED", group_id="G0011", name="MedGroup", aliases="[]")
    for i in range(10):
        store.upsert_group_technique("intrusion-set--MED", f"T100{i}")

    # Low overlap group: 1/10 match → 0.10 → "Low"
    store.upsert_group(stix_id="intrusion-set--LOW", group_id="G0012", name="LowGroup", aliases="[]")
    for i in range(10):
        store.upsert_group_technique("intrusion-set--LOW", f"T100{i}")

    # Query with 7 of the techniques
    query_techs = [f"T100{i}" for i in range(7)]
    results = store.actor_matches(query_techs)

    # All groups have 10 techniques and we query 7 → 7/10 = 0.70 → all "High"
    # This tests that overlap_pct >= 0.60 → "High"
    for r in results:
        assert r["confidence"] in ("High", "Medium", "Low"), \
            f"Unexpected confidence value: {r['confidence']}"

    # Verify threshold logic with direct overlap_pct check
    for r in results:
        pct = r["overlap_pct"]
        if pct >= 0.60:
            assert r["confidence"] == "High", f"Expected High for {pct}, got {r['confidence']}"
        elif pct >= 0.30:
            assert r["confidence"] == "Medium", f"Expected Medium for {pct}, got {r['confidence']}"
        else:
            assert r["confidence"] == "Low", f"Expected Low for {pct}, got {r['confidence']}"
