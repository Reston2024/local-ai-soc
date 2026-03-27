"""Unit tests for investigation utility modules.

Covers:
- backend/investigation/case_manager.py
- backend/investigation/hunt_engine.py
- backend/api/investigate.py (pure functions)
"""
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# CaseManager tests (uses in-memory SQLite with real schema)
# ---------------------------------------------------------------------------

def _make_case_db():
    """Create an in-memory SQLite DB with the investigation_cases schema."""
    import tempfile

    from backend.stores.sqlite_store import SQLiteStore
    store = SQLiteStore(data_dir=tempfile.mkdtemp())
    return store._conn


class TestCaseManager:
    def test_create_investigation_case(self):
        from backend.investigation.case_manager import CaseManager
        conn = _make_case_db()
        cm = CaseManager()
        case_id = cm.create_investigation_case(conn, "APT29 Investigation")
        assert case_id is not None
        assert isinstance(case_id, str)

    def test_create_with_explicit_id(self):
        from backend.investigation.case_manager import CaseManager
        conn = _make_case_db()
        cm = CaseManager()
        cid = str(uuid4())
        result = cm.create_investigation_case(conn, "Test", case_id=cid)
        assert result == cid

    def test_get_investigation_case(self):
        from backend.investigation.case_manager import CaseManager
        conn = _make_case_db()
        cm = CaseManager()
        case_id = cm.create_investigation_case(conn, "Phishing Campaign")
        case = cm.get_investigation_case(conn, case_id)
        assert case is not None
        assert case["title"] == "Phishing Campaign"
        assert case["case_status"] == "open"

    def test_get_nonexistent_case_returns_none(self):
        from backend.investigation.case_manager import CaseManager
        conn = _make_case_db()
        cm = CaseManager()
        result = cm.get_investigation_case(conn, "no-such-case")
        assert result is None

    def test_list_investigation_cases(self):
        from backend.investigation.case_manager import CaseManager
        conn = _make_case_db()
        cm = CaseManager()
        cm.create_investigation_case(conn, "Case A")
        cm.create_investigation_case(conn, "Case B")
        cases = cm.list_investigation_cases(conn)
        assert len(cases) >= 2

    def test_list_cases_filter_by_status(self):
        from backend.investigation.case_manager import CaseManager
        conn = _make_case_db()
        cm = CaseManager()
        cm.create_investigation_case(conn, "Open Case")
        cid2 = cm.create_investigation_case(conn, "Another Open Case")
        cm.update_investigation_case(conn, cid2, {"case_status": "closed"})
        open_cases = cm.list_investigation_cases(conn, status="open")
        assert all(c["case_status"] == "open" for c in open_cases)

    def test_update_investigation_case(self):
        from backend.investigation.case_manager import CaseManager
        conn = _make_case_db()
        cm = CaseManager()
        case_id = cm.create_investigation_case(conn, "Test Case")
        cm.update_investigation_case(conn, case_id, {
            "analyst_notes": "Confirmed lateral movement",
            "case_status": "in_progress",
        })
        case = cm.get_investigation_case(conn, case_id)
        assert case["analyst_notes"] == "Confirmed lateral movement"

    def test_update_array_fields(self):
        from backend.investigation.case_manager import CaseManager
        conn = _make_case_db()
        cm = CaseManager()
        case_id = cm.create_investigation_case(conn, "Test")
        cm.update_investigation_case(conn, case_id, {
            "related_alerts": ["alert-1", "alert-2"],
            "tags": ["apt29", "lateral-movement"],
        })
        case = cm.get_investigation_case(conn, case_id)
        assert isinstance(case["related_alerts"], list)
        assert "alert-1" in case["related_alerts"]

    def test_case_array_fields_parsed_on_get(self):
        from backend.investigation.case_manager import CaseManager
        conn = _make_case_db()
        cm = CaseManager()
        case_id = cm.create_investigation_case(conn, "Test")
        case = cm.get_investigation_case(conn, case_id)
        # Array fields should be deserialized to lists
        assert isinstance(case.get("related_alerts"), list)
        assert isinstance(case.get("tags"), list)

    def test_create_case_idempotent_for_same_id(self):
        from backend.investigation.case_manager import CaseManager
        conn = _make_case_db()
        cm = CaseManager()
        cid = str(uuid4())
        cm.create_investigation_case(conn, "First", case_id=cid)
        cm.create_investigation_case(conn, "Second (ignored)", case_id=cid)
        case = cm.get_investigation_case(conn, cid)
        assert case["title"] == "First"  # INSERT OR IGNORE — first wins


# ---------------------------------------------------------------------------
# HuntEngine tests
# ---------------------------------------------------------------------------

class TestHuntEngine:
    def test_hunt_templates_exist(self):
        from backend.investigation.hunt_engine import HUNT_TEMPLATES
        assert len(HUNT_TEMPLATES) >= 4

    def test_hunt_templates_have_required_fields(self):
        from backend.investigation.hunt_engine import HUNT_TEMPLATES, HuntTemplate
        for name, tmpl in HUNT_TEMPLATES.items():
            assert isinstance(tmpl, HuntTemplate)
            assert tmpl.name == name
            assert isinstance(tmpl.sql, str)
            assert len(tmpl.sql) > 0

    async def test_execute_hunt_unknown_template_raises(self, tmp_path):
        from unittest.mock import AsyncMock, MagicMock

        from backend.investigation.hunt_engine import execute_hunt
        store = MagicMock()
        store.fetch_df = AsyncMock(return_value=[])
        with pytest.raises(ValueError, match="Unknown hunt template"):
            await execute_hunt(store, "nonexistent_template", {})

    async def test_execute_hunt_powershell_children(self, tmp_path):
        from unittest.mock import AsyncMock, MagicMock

        from backend.investigation.hunt_engine import execute_hunt
        store = MagicMock()
        store.fetch_df = AsyncMock(return_value=[])
        result = await execute_hunt(store, "powershell_children", {})
        assert result == []
        store.fetch_df.assert_called_once()

    async def test_execute_hunt_suspicious_ip_comms(self):
        from unittest.mock import AsyncMock, MagicMock

        from backend.investigation.hunt_engine import execute_hunt
        store = MagicMock()
        store.fetch_df = AsyncMock(return_value=[{"hostname": "host1"}])
        result = await execute_hunt(store, "suspicious_ip_comms", {"dst_ip": "10.0.0.1"})
        assert len(result) == 1
        # Verify the param was passed
        _, call_kwargs = store.fetch_df.call_args
        # positional params should include the IP
        call_args = store.fetch_df.call_args[0]
        assert any("10.0.0.1" in str(a) for a in call_args)

    async def test_execute_hunt_ioc_search_multiplies_params(self):
        from unittest.mock import AsyncMock, MagicMock

        from backend.investigation.hunt_engine import execute_hunt
        store = MagicMock()
        store.fetch_df = AsyncMock(return_value=[])
        await execute_hunt(store, "ioc_search", {"ioc_value": "malicious.exe"})
        # ioc_search should have been called with 6 params
        call_args = store.fetch_df.call_args[0]
        params = call_args[1]  # second positional arg to fetch_df
        assert len(params) == 6

    async def test_execute_hunt_unusual_auth_uses_threshold(self):
        from unittest.mock import AsyncMock, MagicMock

        from backend.investigation.hunt_engine import execute_hunt
        store = MagicMock()
        store.fetch_df = AsyncMock(return_value=[])
        await execute_hunt(store, "unusual_auth", {"threshold": 20})
        call_args = store.fetch_df.call_args[0]
        params = call_args[1]
        assert params[0] == 20

    def test_execute_hunt_available_templates(self):
        from backend.investigation.hunt_engine import HUNT_TEMPLATES
        expected = {"suspicious_ip_comms", "powershell_children", "unusual_auth", "ioc_search"}
        assert expected.issubset(set(HUNT_TEMPLATES.keys()))


# ---------------------------------------------------------------------------
# investigate.py pure function tests
# ---------------------------------------------------------------------------

class TestInvestigateHelpers:
    def test_describe_event_process_create(self):
        from backend.api.investigate import _describe_event
        evt = {
            "event_type": "process_create",
            "process_name": "cmd.exe",
            "parent_process_name": "explorer.exe",
            "hostname": "host1",
        }
        desc = _describe_event(evt)
        assert "explorer.exe" in desc
        assert "cmd.exe" in desc

    def test_describe_event_process_create_no_parent(self):
        from backend.api.investigate import _describe_event
        evt = {
            "event_type": "process_create",
            "process_name": "cmd.exe",
            "hostname": "host1",
        }
        desc = _describe_event(evt)
        assert "Process created" in desc
        assert "cmd.exe" in desc

    def test_describe_event_network_connection(self):
        from backend.api.investigate import _describe_event
        evt = {
            "event_type": "network_connection",
            "process_name": "chrome.exe",
            "dst_ip": "192.168.1.1",
            "dst_port": 443,
            "hostname": "host1",
        }
        desc = _describe_event(evt)
        assert "192.168.1.1" in desc
        assert "chrome.exe" in desc

    def test_describe_event_file_create(self):
        from backend.api.investigate import _describe_event
        evt = {
            "event_type": "file_create",
            "process_name": "explorer.exe",
            "file_path": "C:\\Temp\\evil.exe",
            "hostname": "host1",
        }
        desc = _describe_event(evt)
        assert "file" in desc.lower()

    def test_describe_event_auth_failure(self):
        from backend.api.investigate import _describe_event
        evt = {
            "event_type": "auth_failure",
            "username": "jsmith",
            "hostname": "host1",
        }
        desc = _describe_event(evt)
        assert "jsmith" in desc or "Authentication" in desc

    def test_describe_event_registry_write(self):
        from backend.api.investigate import _describe_event
        evt = {
            "event_type": "registry_write",
            "process_name": "regedit.exe",
            "file_path": "HKLM\\Software\\test",
            "hostname": "host1",
        }
        desc = _describe_event(evt)
        assert "registry" in desc.lower() or "regedit" in desc

    def test_describe_event_unknown_type(self):
        from backend.api.investigate import _describe_event
        evt = {
            "event_type": "custom_type",
            "process_name": "proc.exe",
            "hostname": "host1",
        }
        desc = _describe_event(evt)
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_safe_val_datetime(self):
        from datetime import datetime, timezone

        from backend.api.investigate import _safe_val
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = _safe_val(dt)
        assert isinstance(result, str)
        assert "2026" in result

    def test_safe_val_non_datetime(self):
        from backend.api.investigate import _safe_val
        assert _safe_val("string") == "string"
        assert _safe_val(42) == 42
        assert _safe_val(None) is None

    def test_normalize_event(self):
        from datetime import datetime, timezone

        from backend.api.investigate import _normalize_event
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        row = {"event_id": "e1", "timestamp": dt, "hostname": "host1"}
        result = _normalize_event(row)
        assert result["event_id"] == "e1"
        assert isinstance(result["timestamp"], str)
        assert result["hostname"] == "host1"
