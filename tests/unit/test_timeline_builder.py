"""Unit tests for backend/investigation/timeline_builder.py."""
import pytest

pytestmark = pytest.mark.unit

_BASE_EVENT = {
    "event_id": "evt-001",
    "timestamp": "2026-01-01T10:00:00+00:00",
    "hostname": "dc01",
    "username": "alice",
    "process_name": "cmd.exe",
    "severity": "medium",
    "source_type": "json",
}


class TestTimelineBuilder:
    def test_extract_entity_refs_hostname(self):
        from backend.investigation.timeline_builder import _extract_entity_refs
        refs = _extract_entity_refs(_BASE_EVENT)
        assert any("host:" in r for r in refs)

    def test_extract_entity_refs_username(self):
        from backend.investigation.timeline_builder import _extract_entity_refs
        refs = _extract_entity_refs(_BASE_EVENT)
        assert any("user:" in r for r in refs)

    def test_extract_entity_refs_process(self):
        from backend.investigation.timeline_builder import _extract_entity_refs
        refs = _extract_entity_refs({"process_name": "powershell.exe"})
        assert any("process:" in r for r in refs)

    def test_score_confidence_alert_linked_is_1(self):
        from backend.investigation.timeline_builder import _score_confidence
        score = _score_confidence(_BASE_EVENT, alert_ids=["evt-001"])
        assert score == 1.0

    def test_score_confidence_default_is_0_5(self):
        from backend.investigation.timeline_builder import _score_confidence
        score = _score_confidence(_BASE_EVENT, alert_ids=[])
        assert score == 0.5

    def test_score_confidence_attack_technique_is_0_8(self):
        from backend.investigation.timeline_builder import _score_confidence
        evt = {**_BASE_EVENT, "attack_technique": "T1059"}
        score = _score_confidence(evt, alert_ids=[])
        assert score == 0.8

    async def test_build_timeline_returns_list_for_missing_case(self, tmp_path):
        """build_timeline returns [] when the case is not found in sqlite_store."""
        from unittest.mock import MagicMock
        from backend.stores.duckdb_store import DuckDBStore
        from backend.investigation.timeline_builder import build_timeline

        store = DuckDBStore(str(tmp_path / "tl"))
        store.start_write_worker()
        await store.initialise_schema()

        # Mock sqlite_store: case not found returns None
        sqlite_store = MagicMock()
        sqlite_store.get_investigation_case = MagicMock(return_value=None)

        result = await build_timeline("case-tl", store, sqlite_store)
        assert isinstance(result, list)
        await store.close()

    def test_extract_entity_refs_dst_ip(self):
        from backend.investigation.timeline_builder import _extract_entity_refs
        refs = _extract_entity_refs({"dst_ip": "192.168.1.1"})
        assert any("ip:" in r for r in refs)
        assert any("192.168.1.1" in r for r in refs)

    def test_extract_entity_refs_domain(self):
        from backend.investigation.timeline_builder import _extract_entity_refs
        refs = _extract_entity_refs({"domain": "evil.example.com"})
        assert any("domain:" in r for r in refs)

    def test_extract_entity_refs_hostname_lowercased(self):
        from backend.investigation.timeline_builder import _extract_entity_refs
        refs = _extract_entity_refs({"hostname": "DC01"})
        assert any(r == "host:dc01" for r in refs)

    def test_extract_entity_refs_username_lowercased(self):
        from backend.investigation.timeline_builder import _extract_entity_refs
        refs = _extract_entity_refs({"username": "ALICE"})
        assert any(r == "user:alice" for r in refs)

    def test_extract_entity_refs_empty_event(self):
        from backend.investigation.timeline_builder import _extract_entity_refs
        refs = _extract_entity_refs({})
        assert refs == []

    def test_extract_entity_refs_all_fields(self):
        from backend.investigation.timeline_builder import _extract_entity_refs
        event = {
            "hostname": "host1",
            "username": "bob",
            "process_name": "cmd.exe",
            "dst_ip": "10.0.0.1",
            "domain": "example.com",
        }
        refs = _extract_entity_refs(event)
        assert len(refs) == 5

    def test_score_confidence_alert_takes_precedence_over_technique(self):
        """If event_id is in alert_ids, score is 1.0 even if attack_technique set."""
        from backend.investigation.timeline_builder import _score_confidence
        evt = {**_BASE_EVENT, "attack_technique": "T1059"}
        # event_id "evt-001" is in alert_ids
        score = _score_confidence(evt, alert_ids=["evt-001"])
        assert score == 1.0

    def test_score_confidence_different_event_id_no_match(self):
        from backend.investigation.timeline_builder import _score_confidence
        score = _score_confidence({"event_id": "evt-999"}, alert_ids=["evt-001"])
        assert score == 0.5

    async def test_build_timeline_returns_empty_for_none_store(self, tmp_path):
        """build_timeline returns [] when duckdb_store is None."""
        from unittest.mock import MagicMock
        from backend.investigation.timeline_builder import build_timeline

        sqlite_store = MagicMock()
        result = await build_timeline("case-abc", None, sqlite_store)
        assert result == []

    async def test_build_timeline_returns_empty_for_none_sqlite(self, tmp_path):
        """build_timeline returns [] when sqlite_store is None."""
        from backend.stores.duckdb_store import DuckDBStore
        from backend.investigation.timeline_builder import build_timeline

        store = DuckDBStore(str(tmp_path / "tl2"))
        store.start_write_worker()
        await store.initialise_schema()
        result = await build_timeline("case-abc", store, None)
        assert result == []
        await store.close()

    async def test_build_timeline_with_matching_case(self, tmp_path):
        """build_timeline returns entries for events in a matching case."""
        import uuid
        from datetime import datetime, timezone
        from unittest.mock import MagicMock
        from backend.stores.duckdb_store import DuckDBStore
        from backend.investigation.timeline_builder import build_timeline

        store = DuckDBStore(str(tmp_path / "tl3"))
        store.start_write_worker()
        await store.initialise_schema()

        eid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await store.execute_write(
            "INSERT INTO normalized_events "
            "(event_id, timestamp, ingested_at, source_type, case_id, hostname) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [eid, now, now, "json", "case-struct", "host1"],
        )

        # Mock sqlite_store returning a case with empty related_alerts
        sqlite_store = MagicMock()
        sqlite_store.get_investigation_case = MagicMock(
            return_value={"case_id": "case-struct", "related_alerts": []}
        )

        result = await build_timeline("case-struct", store, sqlite_store)
        assert isinstance(result, list)
        assert len(result) >= 1
        # Each entry should have required fields
        entry = result[0]
        assert "timestamp" in entry or "event_source" in entry
        await store.close()
