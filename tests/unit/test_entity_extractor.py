"""Unit tests for entity extractor."""
import uuid
from datetime import datetime, timezone

from backend.models.event import NormalizedEvent
from ingestion.entity_extractor import extract_entities_and_edges


def make_event(**kwargs) -> NormalizedEvent:
    """Helper: create a minimal NormalizedEvent for testing."""
    defaults = {
        "event_id": str(uuid.uuid4()),
        "source_type": "sysmon",
        "source_file": None,
        "timestamp": datetime(2026, 3, 14, 9, 0, 0, tzinfo=timezone.utc),
        "ingested_at": datetime(2026, 3, 14, 9, 0, 1, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    return NormalizedEvent(**defaults)


class TestEntityExtraction:
    """Test entity and edge extraction from normalized events."""

    def test_extracts_host_entity(self):
        event = make_event(hostname="WORKSTATION-01")
        entities, _ = extract_entities_and_edges(event)
        host_entities = [e for e in entities if e["type"] == "host"]
        assert len(host_entities) >= 1
        assert any(e["name"] == "WORKSTATION-01" for e in host_entities)

    def test_host_entity_id_format(self):
        event = make_event(hostname="WORKSTATION-01")
        entities, _ = extract_entities_and_edges(event)
        host_entities = [e for e in entities if e["type"] == "host"]
        assert any(e["id"].startswith("host:") for e in host_entities)

    def test_extracts_user_entity(self):
        event = make_event(username="jsmith")
        entities, _ = extract_entities_and_edges(event)
        user_entities = [e for e in entities if e["type"] == "user"]
        assert len(user_entities) >= 1
        assert any("jsmith" in e["name"] for e in user_entities)

    def test_user_entity_id_format(self):
        event = make_event(username="jsmith")
        entities, _ = extract_entities_and_edges(event)
        user_entities = [e for e in entities if e["type"] == "user"]
        assert any(e["id"].startswith("user:") for e in user_entities)

    def test_extracts_process_entity_when_pid_present(self):
        # Process entity requires both process_name AND process_id
        event = make_event(
            hostname="WORKSTATION-01",
            process_name="powershell.exe",
            process_id=4821,
        )
        entities, _ = extract_entities_and_edges(event)
        proc_entities = [e for e in entities if e["type"] == "process"]
        assert len(proc_entities) >= 1

    def test_no_process_entity_without_pid(self):
        # Without process_id, process entity should NOT be created
        event = make_event(
            hostname="WORKSTATION-01",
            process_name="powershell.exe",
            process_id=None,
        )
        entities, _ = extract_entities_and_edges(event)
        proc_entities = [e for e in entities if e["type"] == "process"]
        assert len(proc_entities) == 0

    def test_no_entities_when_fields_missing(self):
        event = make_event(
            hostname=None,
            username=None,
            process_name=None,
            process_id=None,
        )
        entities, edges = extract_entities_and_edges(event)
        assert isinstance(entities, list)
        assert isinstance(edges, list)
        # Should have no entities — nothing to extract
        assert len(entities) == 0

    def test_extracts_edges(self):
        event = make_event(
            hostname="WORKSTATION-01",
            username="jsmith",
            process_name="powershell.exe",
            process_id=4821,
        )
        entities, edges = extract_entities_and_edges(event)
        assert len(edges) >= 1
        for edge in edges:
            assert "source_id" in edge
            assert "target_id" in edge
            assert "edge_type" in edge

    def test_process_executed_by_user_edge(self):
        event = make_event(
            hostname="WORKSTATION-01",
            username="jsmith",
            process_name="powershell.exe",
            process_id=4821,
        )
        _, edges = extract_entities_and_edges(event)
        exec_edges = [e for e in edges if e["edge_type"] == "executed_by"]
        assert len(exec_edges) >= 1

    def test_process_ran_on_host_edge(self):
        event = make_event(
            hostname="WORKSTATION-01",
            username="jsmith",
            process_name="powershell.exe",
            process_id=4821,
        )
        _, edges = extract_entities_and_edges(event)
        ran_on_edges = [e for e in edges if e["edge_type"] == "ran_on"]
        assert len(ran_on_edges) >= 1

    def test_network_entity_from_dst_ip(self):
        event = make_event(
            hostname="WORKSTATION-01",
            process_name="powershell.exe",
            process_id=4821,
            dst_ip="185.234.1.100",
            dst_port=4444,
        )
        entities, edges = extract_entities_and_edges(event)
        ip_entities = [e for e in entities if e["type"] == "ip"]
        assert len(ip_entities) >= 1
        assert any(e["name"] == "185.234.1.100" for e in ip_entities)

    def test_network_entity_connected_to_edge(self):
        event = make_event(
            hostname="WORKSTATION-01",
            process_name="powershell.exe",
            process_id=4821,
            dst_ip="185.234.1.100",
            dst_port=4444,
        )
        _, edges = extract_entities_and_edges(event)
        conn_edges = [e for e in edges if e["edge_type"] == "connected_to"]
        assert len(conn_edges) >= 1

    def test_file_entity_extracted(self):
        event = make_event(
            hostname="WORKSTATION-01",
            file_path="C:\\Windows\\Temp\\payload.dll",
        )
        entities, _ = extract_entities_and_edges(event)
        file_entities = [e for e in entities if e["type"] == "file"]
        assert len(file_entities) >= 1

    def test_entity_ids_are_stable(self):
        """Same input should produce same entity IDs (deterministic)."""
        event = make_event(hostname="WORKSTATION-01", username="jsmith")
        entities1, _ = extract_entities_and_edges(event)
        entities2, _ = extract_entities_and_edges(event)
        ids1 = {e["id"] for e in entities1}
        ids2 = {e["id"] for e in entities2}
        assert ids1 == ids2

    def test_entity_has_required_keys(self):
        event = make_event(hostname="WORKSTATION-01", username="jsmith")
        entities, _ = extract_entities_and_edges(event)
        for entity in entities:
            assert "id" in entity
            assert "type" in entity
            assert "name" in entity

    def test_edge_has_required_keys(self):
        event = make_event(
            hostname="WORKSTATION-01",
            username="jsmith",
            process_name="cmd.exe",
            process_id=1234,
        )
        _, edges = extract_entities_and_edges(event)
        for edge in edges:
            assert "source_id" in edge
            assert "target_id" in edge
            assert "edge_type" in edge
            assert "source_type" in edge
            assert "target_type" in edge

    def test_return_types_are_lists(self):
        event = make_event()
        entities, edges = extract_entities_and_edges(event)
        assert isinstance(entities, list)
        assert isinstance(edges, list)
