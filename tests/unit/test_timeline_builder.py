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
