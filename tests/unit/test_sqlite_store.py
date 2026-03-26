"""Unit tests for backend/stores/sqlite_store.py — edges, detections, investigations."""
import pytest
from uuid import uuid4

pytestmark = pytest.mark.unit


class TestSavedInvestigations:
    def test_save_investigation_returns_id(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "test.sqlite3"))
        inv_id = store.save_investigation(
            detection_id="det-001",
            graph_snapshot={"nodes": [], "edges": []},
            metadata={"label": "APT test"},
        )
        assert inv_id is not None
        assert isinstance(inv_id, str)

    def test_list_investigations_returns_saved(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "test.sqlite3"))
        store.save_investigation("det-001", {}, {})
        store.save_investigation("det-002", {}, {})
        results = store.list_saved_investigations()
        assert len(results) >= 2

    def test_get_investigation_by_id(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "test.sqlite3"))
        inv_id = store.save_investigation("det-001", {"nodes": [1, 2]}, {"label": "test"})
        result = store.get_saved_investigation(inv_id)
        assert result is not None
        assert result["detection_id"] == "det-001"
        snapshot = result["graph_snapshot"]
        assert snapshot["nodes"] == [1, 2]


class TestSQLiteEdges:
    def test_insert_and_get_edge_from(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "graph.sqlite3"))
        store.insert_edge("process", "pid-1", "ran_on", "host", "host-1", {})
        edges = store.get_edges_from("pid-1")
        assert len(edges) == 1
        assert edges[0]["target_id"] == "host-1"
        store.close()

    def test_edge_properties_preserved(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "graph.sqlite3"))
        store.insert_edge("process", "pid-2", "connected_to", "network", "10.0.0.1:443",
                          {"port": 443, "proto": "tcp"})
        edges = store.get_edges_from("pid-2")
        assert len(edges) == 1
        assert edges[0]["properties"]["port"] == 443
        assert edges[0]["properties"]["proto"] == "tcp"
        store.close()

    def test_get_edges_empty(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "graph.sqlite3"))
        edges = store.get_edges_from("no-such-pid")
        assert edges == []
        store.close()

    def test_insert_multiple_edges(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "graph.sqlite3"))
        store.insert_edge("process", "pid-3", "ran_on", "host", "host-a", {})
        store.insert_edge("process", "pid-3", "executed_by", "user", "alice", {})
        edges = store.get_edges_from("pid-3")
        assert len(edges) == 2
        store.close()

    def test_insert_edge_duplicate_ignored(self, tmp_path):
        """Duplicate edges (same source, type, target) are silently ignored."""
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "graph.sqlite3"))
        store.insert_edge("process", "pid-4", "ran_on", "host", "host-a", {})
        store.insert_edge("process", "pid-4", "ran_on", "host", "host-a", {})
        edges = store.get_edges_from("pid-4")
        assert len(edges) == 1
        store.close()

    def test_get_edges_to_returns_inbound(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "graph.sqlite3"))
        store.insert_edge("process", "pid-5", "connected_to", "host", "target-host", {})
        inbound = store.get_edges_to("target-host")
        assert len(inbound) == 1
        assert inbound[0]["source_id"] == "pid-5"
        store.close()

    def test_insert_edge_without_properties(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "graph.sqlite3"))
        result = store.insert_edge("process", "pid-6", "ran_on", "host", "host-b", None)
        assert result is not None  # Returns row ID
        store.close()


class TestSQLiteDetections:
    def test_insert_and_get_detection(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "det.sqlite3"))
        # Create case first (FK constraint on case_id)
        case_id = store.create_case("Test Case")
        det_id = str(uuid4())
        store.insert_detection(
            detection_id=det_id,
            rule_id="rule-001",
            rule_name="Mimikatz Detection",
            severity="critical",
            matched_event_ids=["evt-001", "evt-002"],
            case_id=case_id,
        )
        det = store.get_detection(det_id)
        assert det is not None
        assert det["rule_name"] == "Mimikatz Detection"
        assert det["severity"] == "critical"
        store.close()

    def test_get_detections_by_case(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "det2.sqlite3"))
        case_a_id = store.create_case("Case A")
        case_b_id = store.create_case("Case B")
        store.insert_detection(
            detection_id=str(uuid4()),
            rule_id="rule-001",
            rule_name="Rule A",
            severity="high",
            matched_event_ids=["e1"],
            case_id=case_a_id,
        )
        store.insert_detection(
            detection_id=str(uuid4()),
            rule_id="rule-002",
            rule_name="Rule B",
            severity="medium",
            matched_event_ids=["e2"],
            case_id=case_b_id,
        )
        case_a_dets = store.get_detections_by_case(case_id=case_a_id)
        assert len(case_a_dets) == 1
        assert case_a_dets[0]["rule_name"] == "Rule A"
        store.close()

    def test_detection_matched_event_ids_deserialized(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "det3.sqlite3"))
        # Use None case_id to avoid FK constraint
        det_id = str(uuid4())
        store.insert_detection(
            detection_id=det_id,
            rule_id="rule-001",
            rule_name="Test",
            severity="low",
            matched_event_ids=["e1", "e2", "e3"],
            case_id=None,
        )
        det = store.get_detection(det_id)
        assert isinstance(det["matched_event_ids"], list)
        assert len(det["matched_event_ids"]) == 3
        store.close()

    def test_detection_with_attack_fields(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "det4.sqlite3"))
        det_id = str(uuid4())
        store.insert_detection(
            detection_id=det_id,
            rule_id="rule-001",
            rule_name="ATT&CK Test",
            severity="high",
            matched_event_ids=["e1"],
            attack_technique="T1059.001",
            attack_tactic="Execution",
            case_id=None,
        )
        det = store.get_detection(det_id)
        assert det["attack_technique"] == "T1059.001"
        assert det["attack_tactic"] == "Execution"
        store.close()

    def test_get_detection_nonexistent_returns_none(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "det5.sqlite3"))
        result = store.get_detection("no-such-detection-id")
        assert result is None
        store.close()

    def test_insert_detection_no_case_id(self, tmp_path):
        """insert_detection works with case_id=None (no FK constraint)."""
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "det6.sqlite3"))
        det_id = str(uuid4())
        store.insert_detection(
            detection_id=det_id,
            rule_id="rule-001",
            rule_name="No Case Detection",
            severity="medium",
            matched_event_ids=[],
            case_id=None,
        )
        det = store.get_detection(det_id)
        assert det is not None
        assert det["case_id"] is None
        store.close()


class TestSQLiteEntities:
    def test_upsert_and_get_entity(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "ent.sqlite3"))
        # Create case first (FK constraint on case_id)
        case_id = store.create_case("Test Case")
        store.upsert_entity(
            entity_id="host-dc01",
            entity_type="host",
            name="dc01",
            attributes={"os": "Windows Server 2022"},
            case_id=case_id,
        )
        entity = store.get_entity("host-dc01")
        assert entity is not None
        assert entity["name"] == "dc01"
        assert entity["type"] == "host"
        store.close()

    def test_upsert_entity_no_case(self, tmp_path):
        """upsert_entity works without case_id."""
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "ent_nc.sqlite3"))
        store.upsert_entity(
            entity_id="proc-abc",
            entity_type="process",
            name="cmd.exe",
            attributes=None,
            case_id=None,
        )
        entity = store.get_entity("proc-abc")
        assert entity is not None
        assert entity["type"] == "process"
        store.close()

    def test_get_entities_by_case(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "ent2.sqlite3"))
        case_x = store.create_case("Case X")
        case_y = store.create_case("Case Y")
        store.upsert_entity("e1", "host", "host1", case_id=case_x)
        store.upsert_entity("e2", "user", "alice", case_id=case_x)
        store.upsert_entity("e3", "host", "host2", case_id=case_y)
        entities = store.get_entities_by_case(case_x)
        assert len(entities) == 2
        store.close()

    def test_get_entity_nonexistent_returns_none(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "ent3.sqlite3"))
        result = store.get_entity("no-such-entity")
        assert result is None
        store.close()


class TestSQLiteCases:
    def test_create_and_get_case(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "case.sqlite3"))
        case_id = store.create_case(name="IR-001", description="Incident response test")
        case = store.get_case(case_id)
        assert case is not None
        assert case["name"] == "IR-001"
        store.close()

    def test_list_cases_returns_all(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "case2.sqlite3"))
        store.create_case("Case A")
        store.create_case("Case B")
        cases = store.list_cases()
        assert len(cases) >= 2
        store.close()

    def test_health_check_returns_ok(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "hc.sqlite3"))
        health = store.health_check()
        assert health["status"] == "ok"
        store.close()

    def test_close_does_not_raise(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "close.sqlite3"))
        store.close()  # Should not raise


class TestSQLiteInvestigationCases:
    def test_create_and_get_investigation_case(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "inv.sqlite3"))
        case_id = store.create_investigation_case(
            title="APT29 Investigation",
            description="Suspicious lateral movement",
        )
        case = store.get_investigation_case(case_id)
        assert case is not None
        assert case["title"] == "APT29 Investigation"
        store.close()

    def test_list_investigation_cases(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "inv2.sqlite3"))
        store.create_investigation_case("Case 1")
        store.create_investigation_case("Case 2")
        cases = store.list_investigation_cases()
        assert len(cases) >= 2
        store.close()

    def test_update_investigation_case(self, tmp_path):
        from backend.stores.sqlite_store import SQLiteStore
        store = SQLiteStore(str(tmp_path / "inv3.sqlite3"))
        case_id = store.create_investigation_case("Test Case")
        store.update_investigation_case(case_id, {"analyst_notes": "Updated notes"})
        case = store.get_investigation_case(case_id)
        assert case["analyst_notes"] == "Updated notes"
        store.close()
