"""
Phase 43 Correlation Engine tests.
P43-T01: CorrelationEngine module contract.
P43-T02: port scan detection (_detect_port_scans).
P43-T03: brute force detection (_detect_brute_force).
P43-T04: beaconing detection (_detect_beaconing).
P43-T05: chain detection (_detect_chains) + YAML loading — implemented in Plan 43-03.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit

_skip = pytest.mark.skip(reason="stub — implement in Plan 43-03")


# ---------------------------------------------------------------------------
# Test 0 — module exists (was RED until Plan 43-02 created it)
# ---------------------------------------------------------------------------
def test_correlation_engine_module_exists():
    """GREEN: detections/correlation_engine.py exists (Plan 43-02 created it)."""
    from detections.correlation_engine import CorrelationEngine  # noqa: F401


# ---------------------------------------------------------------------------
# Test 1 — port scan detection returns DetectionRecord
# ---------------------------------------------------------------------------
def test_port_scan_detection():
    """
    CorrelationEngine._detect_port_scans() returns a list of DetectionRecord
    when 15+ distinct dst_ports are seen from the same src_ip within a 60-second
    window.
    """
    from detections.correlation_engine import CorrelationEngine
    from backend.models.event import DetectionRecord

    mock_row = {
        "src_ip": "10.0.0.1",
        "distinct_ports": 20,
        "event_ids": ["evt-1", "evt-2", "evt-3"],
        "window_start": "2026-01-01T00:00:00",
        "window_end": "2026-01-01T00:01:00",
    }
    mock_duckdb = MagicMock()
    mock_duckdb.fetch_all = AsyncMock(return_value=[mock_row])
    stores = SimpleNamespace(duckdb=mock_duckdb, sqlite=MagicMock())

    engine = CorrelationEngine(stores)
    results = asyncio.run(engine._detect_port_scans())

    assert len(results) == 1
    det = results[0]
    assert isinstance(det, DetectionRecord)
    assert det.rule_id == "corr-portscan"
    assert det.severity == "medium"
    assert det.entity_key == "10.0.0.1"
    assert len(det.matched_event_ids) == 3
    assert "10.0.0.1" in det.explanation
    assert "20" in det.explanation


# ---------------------------------------------------------------------------
# Test 2 — brute force detection
# ---------------------------------------------------------------------------
def test_brute_force_detection():
    """
    CorrelationEngine._detect_brute_force() returns a DetectionRecord with
    severity='high' when 10+ failed authentication events occur from the same
    src_ip within a 60-second window.
    """
    from detections.correlation_engine import CorrelationEngine
    from backend.models.event import DetectionRecord

    mock_row = {
        "src_ip": "192.168.1.50",
        "dst_ip": "192.168.1.10",
        "failed_auth_count": 15,
        "event_ids": ["e1", "e2", "e3", "e4", "e5"],
        "window_start": "2026-01-01T00:00:00",
        "window_end": "2026-01-01T00:01:00",
    }
    mock_duckdb = MagicMock()
    mock_duckdb.fetch_all = AsyncMock(return_value=[mock_row])
    stores = SimpleNamespace(duckdb=mock_duckdb, sqlite=MagicMock())

    engine = CorrelationEngine(stores)
    results = asyncio.run(engine._detect_brute_force())

    assert len(results) == 1
    det = results[0]
    assert isinstance(det, DetectionRecord)
    assert det.rule_id == "corr-bruteforce"
    assert det.severity == "high"
    assert det.entity_key == "192.168.1.50"
    assert "15" in det.explanation


# ---------------------------------------------------------------------------
# Test 3 — beaconing CV detection
# ---------------------------------------------------------------------------
def test_beaconing_cv_detection():
    """
    CorrelationEngine._detect_beaconing() returns a DetectionRecord with
    rule_id='corr-beacon' when the CV of inter-arrival times is below 0.3
    across 20+ connections to the same dst_ip.
    """
    from detections.correlation_engine import CorrelationEngine
    from backend.models.event import DetectionRecord

    # CV = 0.1 / 60.0 = 0.00167 — well below 0.3 threshold
    mock_row = {
        "src_ip": "10.0.0.5",
        "dst_ip": "203.0.113.100",
        "dst_port": 443,
        "conn_count": 24,
        "mean_interval": 60.0,
        "stddev_interval": 0.1,
        "event_ids": [f"b{i}" for i in range(24)],
    }
    mock_duckdb = MagicMock()
    mock_duckdb.fetch_all = AsyncMock(return_value=[mock_row])
    stores = SimpleNamespace(duckdb=mock_duckdb, sqlite=MagicMock())

    engine = CorrelationEngine(stores)
    results = asyncio.run(engine._detect_beaconing())

    assert len(results) == 1
    det = results[0]
    assert isinstance(det, DetectionRecord)
    assert det.rule_id == "corr-beacon"
    assert det.severity == "high"
    assert det.entity_key == "10.0.0.5"
    assert det.attack_technique == "T1071"
    assert len(det.matched_event_ids) == 24


# ---------------------------------------------------------------------------
# Test 4 — DetectionRecord structure from run()
# ---------------------------------------------------------------------------
def test_detection_record_created():
    """
    CorrelationEngine.run() result items have:
      - rule_id starting with 'corr-'
      - matched_event_ids as a non-empty list
    """
    from detections.correlation_engine import CorrelationEngine
    from backend.models.event import DetectionRecord

    portscan_row = {
        "src_ip": "10.1.1.1",
        "distinct_ports": 20,
        "event_ids": ["x1", "x2"],
        "window_start": "2026-01-01T00:00:00",
        "window_end": "2026-01-01T00:01:00",
    }

    mock_duckdb = MagicMock()
    # port scans returns 1 row; brute force + beaconing return empty
    mock_duckdb.fetch_all = AsyncMock(side_effect=[
        [portscan_row],  # _detect_port_scans
        [],              # _detect_brute_force
        [],              # _detect_beaconing
    ])

    # Mock sqlite dedup check to return None (not suppressed)
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None
    mock_sqlite = MagicMock()
    mock_sqlite._conn = mock_conn

    stores = SimpleNamespace(duckdb=mock_duckdb, sqlite=mock_sqlite)

    engine = CorrelationEngine(stores)
    results = asyncio.run(engine.run())

    assert len(results) == 1
    det = results[0]
    assert isinstance(det, DetectionRecord)
    assert det.rule_id.startswith("corr-")
    assert isinstance(det.matched_event_ids, list)
    assert len(det.matched_event_ids) > 0


# ---------------------------------------------------------------------------
# Test 5 — dedup suppresses repeat fires
# ---------------------------------------------------------------------------
def test_dedup_suppresses_repeat():
    """
    run() skips a detection when the same (rule_id, entity_key) combination
    has already fired within the configured dedup window.
    """
    from detections.correlation_engine import CorrelationEngine

    portscan_row = {
        "src_ip": "10.2.2.2",
        "distinct_ports": 18,
        "event_ids": ["z1", "z2"],
        "window_start": "2026-01-01T00:00:00",
        "window_end": "2026-01-01T00:01:00",
    }

    mock_duckdb = MagicMock()
    mock_duckdb.fetch_all = AsyncMock(side_effect=[
        [portscan_row],  # _detect_port_scans
        [],              # _detect_brute_force
        [],              # _detect_beaconing
    ])

    # Mock sqlite dedup check to return a row (IS suppressed)
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = ("some-id",)
    mock_sqlite = MagicMock()
    mock_sqlite._conn = mock_conn

    stores = SimpleNamespace(duckdb=mock_duckdb, sqlite=mock_sqlite)

    engine = CorrelationEngine(stores)
    results = asyncio.run(engine.run())

    # The detection was suppressed by dedup — no results returned
    assert len(results) == 0


# ---------------------------------------------------------------------------
# Test 6 — chain detection (Plan 43-03)
# ---------------------------------------------------------------------------
def test_chain_detection():
    """
    CorrelationEngine._detect_chains() returns a DetectionRecord with
    rule_id='corr-chain-scan-bruteforce' when both corr-portscan and
    corr-bruteforce have fired for the same src_ip within the last 15 minutes.
    """
    import sqlite3
    import tempfile
    import os
    from datetime import datetime, timezone
    from detections.correlation_engine import CorrelationEngine
    from backend.models.event import DetectionRecord

    # Create a temp SQLite DB with a detections table and two rows
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE detections (
                id TEXT PRIMARY KEY,
                rule_id TEXT,
                rule_name TEXT,
                severity TEXT,
                matched_event_ids TEXT,
                attack_technique TEXT,
                attack_tactic TEXT,
                explanation TEXT,
                case_id TEXT,
                entity_key TEXT,
                created_at TEXT
            )
        """)
        now = datetime.now(tz=timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("d1", "corr-portscan", "Port Scan", "medium", "[]", "T1046", "discovery",
             "port scan", None, "10.0.0.1", now),
        )
        conn.execute(
            "INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("d2", "corr-bruteforce", "Brute Force", "high", "[]", "T1110", "credential-access",
             "brute force", None, "10.0.0.1", now),
        )
        conn.commit()

        mock_sqlite = MagicMock()
        mock_sqlite._conn = conn
        mock_duckdb = MagicMock()
        mock_duckdb.fetch_all = AsyncMock(return_value=[])
        stores = SimpleNamespace(duckdb=mock_duckdb, sqlite=mock_sqlite)

        engine = CorrelationEngine(stores)
        engine._chains = [
            {
                "name": "scan-bruteforce",
                "description": "Port scan followed by brute force",
                "rule_ids": ["corr-portscan", "corr-bruteforce"],
                "entity_key": "src_ip",
                "window_minutes": 15,
                "severity": "critical",
            }
        ]

        results = asyncio.run(engine._detect_chains())
        conn.close()

        assert len(results) == 1
        det = results[0]
        assert isinstance(det, DetectionRecord)
        assert det.rule_id == "corr-chain-scan-bruteforce"
        assert det.severity == "critical"
        assert det.entity_key == "10.0.0.1"
        assert "d1" in det.matched_event_ids or "d2" in det.matched_event_ids
    finally:
        try:
            os.unlink(db_path)
        except PermissionError:
            pass  # Windows: file may still be held — acceptable in CI


# ---------------------------------------------------------------------------
# Test 7 — chain YAML loading (Plan 43-03)
# ---------------------------------------------------------------------------
def test_chain_yaml_loading():
    """
    load_chains(path) reads a YAML file and returns the count of chain
    definitions loaded.
    """
    import tempfile
    import os
    from detections.correlation_engine import CorrelationEngine

    yaml_content = """
chains:
  - name: scan-bruteforce
    description: "Port scan then brute force"
    rule_ids:
      - corr-portscan
      - corr-bruteforce
    entity_key: src_ip
    window_minutes: 15
    severity: critical

  - name: recon-to-exploit
    description: "Recon then exploitation"
    rule_ids:
      - corr-portscan
    rule_tactics:
      - discovery
      - execution
    entity_key: src_ip
    window_minutes: 15
    severity: critical
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False
    ) as f:
        f.write(yaml_content)
        tmp_path = f.name
    try:
        mock_stores = SimpleNamespace(duckdb=MagicMock(), sqlite=MagicMock())
        engine = CorrelationEngine(mock_stores)
        count = engine.load_chains(tmp_path)

        assert count == 2
        assert len(engine._chains) == 2
        names = [c["name"] for c in engine._chains]
        assert "scan-bruteforce" in names
        assert "recon-to-exploit" in names
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Test 8 — ingest hook calls correlation (verified via loader.py integration)
# ---------------------------------------------------------------------------
async def test_ingest_hook_calls_correlation():
    """
    When CorrelationEngine is wired into IngestionLoader, loader calls
    correlation_engine.run() after each batch of events is ingested.
    """
    from ingestion.loader import IngestionLoader

    mock_engine = MagicMock()
    mock_engine.run = AsyncMock(return_value=[])
    mock_engine.save_detections = AsyncMock(return_value=0)

    mock_stores = MagicMock()
    mock_stores.duckdb.fetch_all = AsyncMock(return_value=[])

    loader = IngestionLoader(stores=mock_stores, ollama_client=MagicMock(), correlation_engine=mock_engine)
    # Call ingest_events with empty list — should still call engine.run()
    await loader.ingest_events([])

    mock_engine.run.assert_called_once()
