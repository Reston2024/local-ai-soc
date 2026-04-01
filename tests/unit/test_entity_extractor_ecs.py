"""Automated tests: ECS field propagation from NormalizedEvent into entity graph nodes.

These tests satisfy P20-T05 integration verification. They use only in-process
objects — no DuckDB instance, no running server required.
"""
import pytest
from datetime import datetime, timezone
from backend.models.event import NormalizedEvent
from ingestion.entity_extractor import extract_entities_and_edges


def _base_event(**kwargs) -> NormalizedEvent:
    """Minimal valid NormalizedEvent for testing."""
    now = datetime.now(timezone.utc)
    return NormalizedEvent(
        event_id="test-001",
        timestamp=now,
        ingested_at=now,
        source_type="test",
        **kwargs,
    )


def test_user_entity_includes_user_domain():
    """User graph node attributes must contain user_domain when NormalizedEvent has it."""
    event = _base_event(
        username="alice",
        hostname="WS01",
        user_domain="CORP",
        event_type="logon_success",
    )
    nodes, _ = extract_entities_and_edges(event)
    user_nodes = [n for n in nodes if n.get("type") == "user"]
    assert user_nodes, "Expected at least one user node"
    user_node = user_nodes[0]
    attrs = user_node.get("attributes", {})
    assert "user_domain" in attrs, f"user_domain missing from user node attributes: {attrs}"
    assert attrs["user_domain"] == "CORP"


def test_process_entity_includes_process_executable():
    """Process graph node attributes must contain process_executable when NormalizedEvent has it."""
    event = _base_event(
        process_name="cmd.exe",
        process_id=1234,
        hostname="WS01",
        process_executable="C:\\Windows\\System32\\cmd.exe",
        event_type="process_create",
    )
    nodes, _ = extract_entities_and_edges(event)
    proc_nodes = [n for n in nodes if n.get("type") == "process"]
    assert proc_nodes, "Expected at least one process node"
    proc_node = proc_nodes[0]
    attrs = proc_node.get("attributes", {})
    assert "process_executable" in attrs, f"process_executable missing from process node: {attrs}"
    assert attrs["process_executable"] == "C:\\Windows\\System32\\cmd.exe"


def test_ip_entity_includes_network_protocol():
    """IP graph node attributes must contain network_protocol when NormalizedEvent has it."""
    event = _base_event(
        dst_ip="8.8.8.8",
        network_protocol="dns",
        event_type="dns_query",
    )
    nodes, _ = extract_entities_and_edges(event)
    ip_nodes = [n for n in nodes if n.get("type") == "ip"]
    assert ip_nodes, "Expected at least one IP node"
    ip_node = ip_nodes[0]
    attrs = ip_node.get("attributes", {})
    assert "network_protocol" in attrs, f"network_protocol missing from IP node: {attrs}"
    assert attrs["network_protocol"] == "dns"


def test_ecs_fields_absent_when_none():
    """Nodes must NOT contain ECS attribute keys when NormalizedEvent fields are None."""
    event = _base_event(
        username="bob",
        hostname="WS02",
        process_name="powershell.exe",
        process_id=5678,
        dst_ip="10.0.0.1",
        event_type="process_create",
        # user_domain, process_executable, network_protocol are all None (default)
    )
    nodes, _ = extract_entities_and_edges(event)
    for node in nodes:
        attrs = node.get("attributes", {})
        assert "user_domain" not in attrs or attrs.get("user_domain") is not None, \
            "user_domain key present with None value — should be omitted"
        assert "process_executable" not in attrs or attrs.get("process_executable") is not None, \
            "process_executable key present with None value — should be omitted"
        assert "network_protocol" not in attrs or attrs.get("network_protocol") is not None, \
            "network_protocol key present with None value — should be omitted"
