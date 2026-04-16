"""
Phase 52 Wave 0 stubs: TheHiveClient tests (Plan 52-01).
All 5 stubs SKIP cleanly until Plan 52-02 implements backend/services/thehive_client.py.
"""
from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Per-test guard pattern (matches Phase 44/45/48 convention)
_TH_AVAILABLE = False
try:
    from backend.services.thehive_client import (  # noqa: F401
        TheHiveClient,
        build_case_payload,
        build_observables,
        _maybe_create_thehive_case,
    )
    _TH_AVAILABLE = True
except ImportError:
    pass


def test_case_payload_severity():
    """build_case_payload() maps severity 'high'→3, 'critical'→4 (TheHive numeric scale)."""
    if not _TH_AVAILABLE:
        pytest.skip("backend.services.thehive_client not yet implemented (Plan 52-02)")

    detection = {
        "rule_name": "Mimikatz Detected",
        "src_ip": "192.168.1.55",
        "severity": "high",
        "rule_id": "sigma-mimikatz",
    }
    payload = build_case_payload(detection)
    assert payload["severity"] == 3, f"Expected severity 3 for 'high', got {payload['severity']}"

    detection_crit = {**detection, "severity": "critical"}
    payload_crit = build_case_payload(detection_crit)
    assert payload_crit["severity"] == 4, f"Expected severity 4 for 'critical', got {payload_crit['severity']}"


def test_suppress_rules_skip():
    """_maybe_create_thehive_case() returns early when rule_id is in suppress list."""
    if not _TH_AVAILABLE:
        pytest.skip("backend.services.thehive_client not yet implemented (Plan 52-02)")

    mock_client = MagicMock(spec=TheHiveClient)
    detection = {
        "rule_id": "noisy-rule-001",
        "severity": "high",
        "rule_name": "Noisy Rule",
        "src_ip": "1.2.3.4",
    }
    suppress_list = ["noisy-rule-001", "other-noisy-rule"]

    _maybe_create_thehive_case(mock_client, detection, suppress_rules=suppress_list)

    mock_client.create_case.assert_not_called()


def test_observable_builder():
    """build_observables() returns list with ip and other observable types."""
    if not _TH_AVAILABLE:
        pytest.skip("backend.services.thehive_client not yet implemented (Plan 52-02)")

    detection = {
        "src_ip": "1.2.3.4",
        "rule_name": "Port Scan Detected",
        "rule_id": "sigma-portscan",
    }
    observables = build_observables(detection)

    assert isinstance(observables, list), "build_observables() must return a list"
    assert len(observables) >= 1, "Must return at least one observable"

    ip_obs = next((o for o in observables if o.get("dataType") == "ip"), None)
    assert ip_obs is not None, "Expected observable with dataType='ip'"
    assert ip_obs["data"] == "1.2.3.4", f"Expected data='1.2.3.4', got {ip_obs['data']}"

    other_obs = [o for o in observables if o.get("dataType") == "other"]
    assert len(other_obs) >= 1, "Expected at least one observable with dataType='other'"


def test_enqueue_on_failure():
    """_maybe_create_thehive_case() writes to thehive_pending_cases on TheHiveClient failure."""
    if not _TH_AVAILABLE:
        pytest.skip("backend.services.thehive_client not yet implemented (Plan 52-02)")

    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE thehive_pending_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detection_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.commit()

    mock_client = MagicMock(spec=TheHiveClient)
    mock_client.create_case.side_effect = Exception("TheHive connection refused")

    detection = {
        "rule_id": "sigma-mimikatz",
        "severity": "high",
        "rule_name": "Mimikatz Detected",
        "src_ip": "192.168.1.55",
    }

    _maybe_create_thehive_case(mock_client, detection, db_conn=conn)

    rows = conn.execute("SELECT COUNT(*) FROM thehive_pending_cases").fetchone()
    assert rows[0] == 1, f"Expected 1 pending row, got {rows[0]}"


def test_ping_returns_false_when_unreachable():
    """TheHiveClient.ping() returns False when TheHive is unreachable."""
    if not _TH_AVAILABLE:
        pytest.skip("backend.services.thehive_client not yet implemented (Plan 52-02)")

    client = TheHiveClient(url="http://localhost:19999", api_key="fake-key")

    with patch.object(client._api, "case", new_callable=MagicMock) as mock_case:
        mock_case.find.side_effect = Exception("Connection refused")
        result = client.ping()

    assert result is False, f"Expected False when unreachable, got {result}"
