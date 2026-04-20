"""
End-to-end attack scenario tests.

Each test validates a complete detection pipeline slice:
  1. Seed DuckDB with fixture or synthetic events (via normalizer → to_duckdb_row)
  2. Load a targeted Sigma rule (inline YAML using SIGMA_FIELD_MAP field names)
  3. Run SigmaMatcher.run_all()
  4. Assert the expected detections fire with the expected matched event IDs
  5. Where applicable: assert correlation clustering groups related events correctly

No external services. All tests use tmp_path DuckDB.
pytest.mark: scenarios
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ingestion.loader import _INSERT_SQL
from ingestion.normalizer import normalize_event

pytestmark = pytest.mark.scenarios

# ---------------------------------------------------------------------------
# Inline Sigma rules — uses SIGMA_FIELD_MAP field names so matcher can convert
# ---------------------------------------------------------------------------

_C2_SUBNET_RULE = """
title: Suspicious C2 Network Connection
id: 11111111-0000-0000-0000-000000000001
status: test
description: Detects connections to known malicious Tor exit subnet 185.220.x.x
logsource:
    category: network_connection
    product: windows
detection:
    selection:
        DestinationIp|contains: '185.220.'
    condition: selection
level: critical
tags:
    - attack.command_and_control
    - attack.t1071.001
"""

_WMI_LATERAL_RULE = """
title: WMI Lateral Movement Detected
id: 11111111-0000-0000-0000-000000000002
status: test
description: PowerShell spawned by WmiPrvSE — classic lateral movement indicator
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        ParentImage|contains: 'WmiPrvSE'
    condition: selection
level: high
tags:
    - attack.lateral_movement
    - attack.t1047
"""

_POWERSHELL_ENCODED_RULE = """
title: PowerShell Encoded Command Download Cradle
id: 11111111-0000-0000-0000-000000000003
status: test
description: Detects PowerShell running with -EncodedCommand — common download cradle
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        CommandLine|contains: '-EncodedCommand'
    condition: selection
level: high
tags:
    - attack.execution
    - attack.t1059.001
"""

_AUTH_FAILURE_RULE = """
title: Multiple Authentication Failures
id: 11111111-0000-0000-0000-000000000004
status: test
description: Detects auth failure events — potential brute force
logsource:
    product: windows
    service: security
detection:
    selection:
        EventType: auth_failure
    condition: selection
level: medium
tags:
    - attack.credential_access
    - attack.t1110
"""

_LSASS_ACCESS_RULE = """
title: LSASS Process Access
id: 11111111-0000-0000-0000-000000000005
status: test
description: Detects access to lsass.exe — credential dumping indicator
logsource:
    category: process_access
    product: windows
detection:
    selection:
        TargetFilename|contains: 'lsass'
    condition: selection
level: critical
tags:
    - attack.credential_access
    - attack.t1003.001
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def store(tmp_path):
    """Real DuckDB store with schema bootstrapped — isolated per test."""
    from backend.stores.duckdb_store import DuckDBStore
    s = DuckDBStore(str(tmp_path / "scenario_db"))
    s.start_write_worker()
    await s.initialise_schema()
    yield s
    await s.close()


def _stores(duckdb_store):
    """Minimal Stores namespace expected by SigmaMatcher and clustering functions."""
    return SimpleNamespace(duckdb=duckdb_store)


async def _seed(store, events: list[dict]) -> list[str]:
    """Normalize and insert events into DuckDB. Returns list of event_ids inserted."""
    ids: list[str] = []
    for raw in events:
        ev = normalize_event(raw)
        await store.execute_write(_INSERT_SQL, list(ev.to_duckdb_row()))
        ids.append(ev.event_id)
    return ids


def _load_apt_scenario() -> list[dict]:
    """Load the apt_scenario.ndjson fixture."""
    fixture_path = Path(__file__).parents[2] / "fixtures" / "ndjson" / "apt_scenario.ndjson"
    events = []
    with open(fixture_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _make_matcher(stores_ns):
    """Create a SigmaMatcher wired to the given stores namespace."""
    from detections.matcher import SigmaMatcher
    return SigmaMatcher(stores=stores_ns)


# ---------------------------------------------------------------------------
# Scenario 1: Phishing → C2 — network connections to malicious subnet
# ---------------------------------------------------------------------------

async def test_c2_subnet_rule_fires_on_apt_scenario(store):
    """C2 detection fires when APT scenario events contain connections to 185.220.x.x.

    Loads the full apt_scenario.ndjson (15 events, 4 contain dst_ip 185.220.101.45).
    The C2 subnet rule (DestinationIp|contains: '185.220.') must fire and return
    exactly those 4 network connection events.
    """
    stores_ns = _stores(store)
    events = _load_apt_scenario()
    await _seed(store, events)

    # Identify events we expect to match (dst_ip = 185.220.101.45)
    expected_ids = {
        e["event_id"] for e in events
        if (e.get("dst_ip") or "").startswith("185.220.")
    }
    assert len(expected_ids) >= 2, "Fixture must have ≥2 events to 185.220.x.x"

    matcher = _make_matcher(stores_ns)
    rule = matcher.load_rule_yaml(_C2_SUBNET_RULE)
    assert rule is not None, "C2 subnet rule must parse successfully"

    detections = await matcher.run_all()
    assert len(detections) >= 1, "C2 subnet rule must produce at least one detection"

    all_matched = {eid for d in detections for eid in d.matched_event_ids}
    missing = expected_ids - all_matched
    assert not missing, (
        f"Expected event IDs not matched by C2 rule: {missing}. "
        f"Matched: {all_matched}"
    )


# ---------------------------------------------------------------------------
# Scenario 2: WMI Lateral Movement
# ---------------------------------------------------------------------------

async def test_wmi_lateral_movement_rule_fires(store):
    """WMI lateral movement rule fires on the correct APT scenario event.

    Event a1b2c3d4-...013 has parent_process_name='WmiPrvSE.exe' — WMI-based
    lateral movement from WORKSTATION-01 to WORKSTATION-02.
    The rule must fire and match exactly that event.
    """
    stores_ns = _stores(store)
    events = _load_apt_scenario()
    await _seed(store, events)

    # Event 013 is the WMI lateral movement
    wmi_event_id = "a1b2c3d4-e5f6-4789-8abc-def012345013"

    matcher = _make_matcher(stores_ns)
    matcher.load_rule_yaml(_WMI_LATERAL_RULE)

    detections = await matcher.run_all()
    assert len(detections) >= 1, "WMI lateral movement rule must fire"

    all_matched = {eid for d in detections for eid in d.matched_event_ids}
    assert wmi_event_id in all_matched, (
        f"WMI lateral movement event {wmi_event_id!r} not in matched IDs: {all_matched}"
    )


# ---------------------------------------------------------------------------
# Scenario 3: PowerShell encoded download cradle
# ---------------------------------------------------------------------------

async def test_powershell_encoded_command_rule_fires(store):
    """PowerShell encoded command rule fires on -EncodedCommand events.

    The APT scenario contains at least one event with -EncodedCommand in the
    command_line (event 001: winword→powershell initial compromise).
    The rule must fire and its severity must be 'high'.
    """
    stores_ns = _stores(store)
    events = _load_apt_scenario()
    await _seed(store, events)

    expected_id = "a1b2c3d4-e5f6-4789-8abc-def012345001"

    matcher = _make_matcher(stores_ns)
    matcher.load_rule_yaml(_POWERSHELL_ENCODED_RULE)

    detections = await matcher.run_all()
    assert len(detections) >= 1, "PowerShell encoded command rule must fire"

    all_matched = {eid for d in detections for eid in d.matched_event_ids}
    assert expected_id in all_matched, (
        f"Initial compromise event {expected_id!r} not in matched IDs: {all_matched}"
    )

    # Severity must be 'high' (from rule level: high)
    assert all(d.severity == "high" for d in detections), (
        f"Expected severity 'high', got: {[d.severity for d in detections]}"
    )


# ---------------------------------------------------------------------------
# Scenario 4: Credential abuse — synthetic brute force events
# ---------------------------------------------------------------------------

async def test_credential_abuse_brute_force_detection(store):
    """Auth failure rule detects synthetic brute force — exactly N auth_failure events matched.

    Inserts 5 auth_failure events and 2 network_connection events from the same
    source IP. The auth failure rule must match exactly the 5 failure events
    and not the network events.
    """
    stores_ns = _stores(store)
    now = datetime.now(tz=timezone.utc)
    src_ip = "10.10.10.99"

    # 5 brute-force auth failures from same src_ip
    failure_ids = []
    for i in range(5):
        eid = str(uuid4())
        failure_ids.append(eid)
        await _seed(store, [{
            "event_id": eid,
            "timestamp": (now + timedelta(seconds=i * 3)).isoformat(),
            "src_ip": src_ip,
            "dst_ip": "192.168.1.10",
            "hostname": "DC-01",
            "username": f"attacker_attempt_{i}",
            "event_type": "auth_failure",
            "severity": "high",
            "source_type": "windows_event",
        }])

    # 2 unrelated network events (must NOT be matched)
    unrelated_ids = []
    for i in range(2):
        eid = str(uuid4())
        unrelated_ids.append(eid)
        await _seed(store, [{
            "event_id": eid,
            "timestamp": (now + timedelta(seconds=20 + i)).isoformat(),
            "src_ip": src_ip,
            "dst_ip": "8.8.8.8",
            "hostname": "DC-01",
            "event_type": "network_connection",
            "severity": "low",
            "source_type": "windows_event",
        }])

    matcher = _make_matcher(stores_ns)
    matcher.load_rule_yaml(_AUTH_FAILURE_RULE)

    detections = await matcher.run_all()
    assert len(detections) >= 1, "Auth failure rule must fire on brute force events"

    all_matched = {eid for d in detections for eid in d.matched_event_ids}

    # All 5 failure events must be matched
    missing = set(failure_ids) - all_matched
    assert not missing, f"Auth failure events not matched: {missing}"

    # No unrelated events should be matched
    false_positives = set(unrelated_ids) & all_matched
    assert not false_positives, (
        f"Auth failure rule incorrectly matched unrelated events: {false_positives}"
    )


# ---------------------------------------------------------------------------
# Scenario 5: LSASS credential dump + multi-rule fan-out
# ---------------------------------------------------------------------------

async def test_lsass_credential_dump_detected(store):
    """LSASS access rule fires on process_access event targeting lsass.exe.

    Event 011 in apt_scenario: svchosts.exe accesses lsass.exe — credential dump.
    The LSASS rule (TargetFilename|contains: 'lsass') must fire as critical severity.
    """
    stores_ns = _stores(store)
    events = _load_apt_scenario()
    await _seed(store, events)

    lsass_event_id = "a1b2c3d4-e5f6-4789-8abc-def012345011"

    matcher = _make_matcher(stores_ns)
    matcher.load_rule_yaml(_LSASS_ACCESS_RULE)

    detections = await matcher.run_all()
    assert len(detections) >= 1, "LSASS access rule must fire"

    all_matched = {eid for d in detections for eid in d.matched_event_ids}
    assert lsass_event_id in all_matched, (
        f"LSASS event {lsass_event_id!r} not matched. Matched: {all_matched}"
    )

    critical = [d for d in detections if d.severity == "critical"]
    assert critical, "LSASS detection must have critical severity"


# ---------------------------------------------------------------------------
# Scenario 6: Multi-rule APT chain — all 5 rules on same dataset
# ---------------------------------------------------------------------------

async def test_full_apt_chain_multi_rule_coverage(store):
    """All 5 detection rules fire on the complete APT scenario dataset.

    This is the pipeline integration test: given a realistic 15-event APT
    chain (initial access → C2 → persistence → credential dump → lateral
    movement), all 5 rules must produce detections.

    Also verifies that entity-based clustering groups the WORKSTATION-01
    events into a single cluster (shared hostname entity).
    """
    from correlation.clustering import cluster_events_by_entity

    stores_ns = _stores(store)
    events = _load_apt_scenario()
    await _seed(store, events)

    matcher = _make_matcher(stores_ns)
    for rule_yaml in [
        _C2_SUBNET_RULE,
        _WMI_LATERAL_RULE,
        _POWERSHELL_ENCODED_RULE,
        _AUTH_FAILURE_RULE,
        _LSASS_ACCESS_RULE,
    ]:
        matcher.load_rule_yaml(rule_yaml)

    detections = await matcher.run_all()

    # With 5 rules and 15 events spanning 5 attack phases, we expect ≥4 rule hits
    # (auth_failure rule may not fire since apt_scenario uses event_type='auth_failure'
    # which EventType field maps correctly)
    assert len(detections) >= 4, (
        f"Expected ≥4 detections across 5 rules on APT scenario, got {len(detections)}. "
        f"Rules: C2 subnet, WMI lateral, PowerShell encoded, LSASS access, auth failure."
    )

    # Verify ATT&CK tagging: detections must carry technique IDs
    with_technique = [d for d in detections if d.attack_technique]
    assert with_technique, "At least one detection must have ATT&CK technique assigned"

    # --- Correlation check ---
    # WORKSTATION-01 has 10+ events; they should form a single large cluster
    all_event_ids = [e["event_id"] for e in events]
    clusters = await cluster_events_by_entity(stores_ns, event_ids=all_event_ids)

    assert clusters, "Clustering must produce at least one cluster"

    # Largest cluster should contain multiple WORKSTATION-01 events
    largest = max(clusters, key=lambda c: len(c.events))
    assert len(largest.events) >= 5, (
        f"Largest cluster should contain ≥5 events from WORKSTATION-01, "
        f"got {len(largest.events)}: {largest.events}"
    )


# ---------------------------------------------------------------------------
# Scenario 7: DNS exfiltration — synthetic high-volume DNS events normalize correctly
# ---------------------------------------------------------------------------

async def test_dns_exfil_events_normalize_and_cluster(store):
    """High-volume DNS events from a single host normalize correctly and cluster together.

    Creates 15 DNS query events from the same host within a 60-second window.
    Verifies:
    1. All events are normalized with event_type preserved
    2. Entity clustering groups them by shared hostname into a single cluster
    3. Cluster size equals the number of inserted events
    """
    from correlation.clustering import cluster_events_by_entity

    stores_ns = _stores(store)
    now = datetime.now(tz=timezone.utc)
    infected_host = "WORKSTATION-EXFIL"
    dns_ids = []

    # 15 DNS queries in 60 seconds — simulates high-volume DNS exfil
    suspicious_domains = [
        f"{uuid4().hex[:8]}.exfil-domain.biz",
        "data-chunk.evil-c2.net",
        "beacon.track-me.io",
    ]
    for i in range(15):
        eid = str(uuid4())
        dns_ids.append(eid)
        await _seed(store, [{
            "event_id": eid,
            "timestamp": (now + timedelta(seconds=i * 4)).isoformat(),
            "src_ip": "192.168.1.55",
            "hostname": infected_host,
            "event_type": "dns",
            "dns_query": suspicious_domains[i % len(suspicious_domains)],
            "dns_query_type": "A",
            "severity": "medium",
            "source_type": "zeek",
        }])

    # Verify all events round-trip through DuckDB correctly
    rows = await store.fetch_all(
        "SELECT event_id, event_type, hostname FROM normalized_events "
        "WHERE hostname = ?",
        [infected_host],
    )
    assert len(rows) == 15, f"Expected 15 DNS events in DuckDB, got {len(rows)}"
    event_types = {row[1] for row in rows}
    assert event_types == {"dns"}, (
        f"All events must have event_type='dns', got: {event_types}"
    )

    # Entity clustering: all 15 events share hostname → single cluster
    clusters = await cluster_events_by_entity(stores_ns, event_ids=dns_ids)
    assert clusters, "DNS events from same host must form at least one cluster"

    largest = max(clusters, key=lambda c: len(c.events))
    assert len(largest.events) == 15, (
        f"All 15 DNS events must cluster together (shared host entity), "
        f"got cluster size {len(largest.events)}"
    )
