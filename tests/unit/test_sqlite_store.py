"""Unit tests for Phase 9 SQLiteStore saved investigations.

Tests P9-T09 (save_investigation, list_saved_investigations, get_saved_investigation).
"""
import pytest

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
