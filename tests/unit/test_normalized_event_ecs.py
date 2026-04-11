"""Tests for P20-T01: ECS-aligned NormalizedEvent model extension."""
from datetime import datetime, timezone

import pytest

from backend.models.event import OCSF_CLASS_UID_MAP, NormalizedEvent


_TS = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_ecs_new_fields_present():
    """NormalizedEvent must accept ocsf_class_uid, event_outcome, user_domain,
    process_executable, network_protocol, network_direction."""
    event = NormalizedEvent(
        event_id="x",
        timestamp=_TS,
        ingested_at=_TS,
        ocsf_class_uid=1007,
        event_outcome="success",
        user_domain="CORP",
        process_executable=r"C:\Windows\System32\cmd.exe",
        network_protocol="tcp",
        network_direction="outbound",
    )
    assert event.ocsf_class_uid == 1007
    assert event.event_outcome == "success"
    assert event.user_domain == "CORP"
    assert event.process_executable == r"C:\Windows\System32\cmd.exe"
    assert event.network_protocol == "tcp"
    assert event.network_direction == "outbound"


def test_ecs_new_fields_optional_default_none():
    """All six new ECS fields must default to None — existing callers not broken."""
    event = NormalizedEvent(event_id="x", timestamp=_TS, ingested_at=_TS)
    assert event.ocsf_class_uid is None
    assert event.event_outcome is None
    assert event.user_domain is None
    assert event.process_executable is None
    assert event.network_protocol is None
    assert event.network_direction is None


def test_ocsf_class_uid_process_create():
    """event_type='process_create' must map to ocsf_class_uid=1007 via OCSF_CLASS_UID_MAP."""
    assert OCSF_CLASS_UID_MAP["process_create"] == 1007


def test_ocsf_class_uid_network_connect():
    """event_type='network_connect' must map to ocsf_class_uid=4001."""
    assert OCSF_CLASS_UID_MAP["network_connect"] == 4001


def test_ocsf_class_uid_logon():
    """event_type='logon_success' must map to ocsf_class_uid=3002."""
    assert OCSF_CLASS_UID_MAP["logon_success"] == 3002


def test_ocsf_class_uid_dns_query():
    """event_type='dns_query' must map to ocsf_class_uid=4003."""
    assert OCSF_CLASS_UID_MAP["dns_query"] == 4003


def test_backward_compat_existing_fields():
    """Legacy fields (hostname, username, process_name, etc.) must still work unchanged."""
    event = NormalizedEvent(
        event_id="legacy-01",
        timestamp=_TS,
        ingested_at=_TS,
        hostname="ws01",
        username="alice",
        process_name="svchost.exe",
        process_id=1234,
        parent_process_name="services.exe",
        parent_process_id=568,
        file_path=r"C:\Windows\System32\svchost.exe",
        file_hash_sha256="abc123",
        command_line="svchost -k netsvcs",
        src_ip="10.0.0.1",
        src_port=49152,
        dst_ip="8.8.8.8",
        dst_port=53,
        domain="corp.local",
        url="http://corp.local/",
        event_type="network_connect",
        severity="medium",
        confidence=0.95,
        detection_source="sigma",
        attack_technique="T1071",
        attack_tactic="command-and-control",
        raw_event='{"raw": true}',
        tags="dns,c2",
        case_id="case-42",
    )
    assert event.hostname == "ws01"
    assert event.username == "alice"
    assert event.process_name == "svchost.exe"
    assert event.process_id == 1234
    assert event.parent_process_name == "services.exe"
    assert event.parent_process_id == 568
    assert event.file_path == r"C:\Windows\System32\svchost.exe"
    assert event.file_hash_sha256 == "abc123"
    assert event.command_line == "svchost -k netsvcs"
    assert event.src_ip == "10.0.0.1"
    assert event.src_port == 49152
    assert event.dst_ip == "8.8.8.8"
    assert event.dst_port == 53
    assert event.domain == "corp.local"
    assert event.url == "http://corp.local/"
    assert event.event_type == "network_connect"
    assert event.severity == "medium"
    assert event.confidence == 0.95
    assert event.detection_source == "sigma"
    assert event.attack_technique == "T1071"
    assert event.attack_tactic == "command-and-control"
    assert event.raw_event == '{"raw": true}'
    assert event.tags == "dns,c2"
    assert event.case_id == "case-42"


def test_to_duckdb_row_includes_new_fields():
    """to_duckdb_row() must return a 58-element tuple; ECS fields at positions 29-34.

    Updated from 35 to 55 in Phase 31 (plan 31-01) — 20 EVE protocol fields appended.
    Updated from 55 to 58 in Phase 33 (plan 33-02) — 3 IOC matching fields appended.
    ECS field positions 29-34 are unchanged.
    """
    event = NormalizedEvent(
        event_id="row-test",
        timestamp=_TS,
        ingested_at=_TS,
        case_id="case-99",
        ocsf_class_uid=4001,
        event_outcome="failure",
        user_domain="WORKGROUP",
        process_executable=r"C:\temp\evil.exe",
        network_protocol="udp",
        network_direction="inbound",
    )
    row = event.to_duckdb_row()
    assert len(row) == 75             # Phase 36: expanded from 58 to 75 columns (Zeek fields)
    assert row[29] == 4001            # ocsf_class_uid
    assert row[30] == "failure"       # event_outcome
    assert row[31] == "WORKGROUP"     # user_domain
    assert row[32] == r"C:\temp\evil.exe"  # process_executable
    assert row[33] == "udp"           # network_protocol
    assert row[34] == "inbound"       # network_direction
    assert row[55] is False           # ioc_matched (default False)
    assert row[56] is None            # ioc_confidence
    assert row[57] is None            # ioc_actor_tag
