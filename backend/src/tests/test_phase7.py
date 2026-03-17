"""Phase 7 smoke tests — threat hunting, case management, timeline builder,
artifact store, and dashboard build verification.

Wave 0 stubs: All tests are marked xfail until Phase 7 implementation plans
(01 through 04) are complete. Module-level imports are minimal to ensure this
file imports cleanly before implementation stubs are replaced.
"""
import pytest
from fastapi.testclient import TestClient
from backend.src.api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# TestCaseManager
# Tests for CaseManager: SQLite-backed investigation case CRUD.
# P7: Plan 01 will implement CaseManager in investigation/case_manager.py.
# ---------------------------------------------------------------------------

class TestCaseManager:
    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 01 not yet implemented")
    def test_create_case_returns_id(self):
        """CaseManager.create_investigation_case must return a string UUID."""
        import sqlite3
        from backend.investigation.case_manager import CaseManager
        DDL = """
        CREATE TABLE IF NOT EXISTS investigation_cases (
            case_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            case_status TEXT NOT NULL DEFAULT 'open',
            related_alerts TEXT DEFAULT '[]',
            related_entities TEXT DEFAULT '[]',
            timeline_events TEXT DEFAULT '[]',
            analyst_notes TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            artifacts TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
        conn = sqlite3.connect(":memory:")
        conn.executescript(DDL)
        conn.commit()
        cm = CaseManager()
        result = cm.create_investigation_case(conn, "Test Investigation", "Test description")
        assert isinstance(result, str), f"Expected string UUID, got {type(result)}"
        assert len(result) > 0, "case_id must be non-empty"

    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 01 not yet implemented")
    def test_list_cases_empty(self):
        """CaseManager.list_investigation_cases on empty DB must return []."""
        import sqlite3
        from backend.investigation.case_manager import CaseManager
        DDL = """
        CREATE TABLE IF NOT EXISTS investigation_cases (
            case_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            case_status TEXT NOT NULL DEFAULT 'open',
            related_alerts TEXT DEFAULT '[]',
            related_entities TEXT DEFAULT '[]',
            timeline_events TEXT DEFAULT '[]',
            analyst_notes TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            artifacts TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
        conn = sqlite3.connect(":memory:")
        conn.executescript(DDL)
        conn.commit()
        cm = CaseManager()
        result = cm.list_investigation_cases(conn)
        assert result == [], f"Empty DB must return [], got {result!r}"

    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 01 not yet implemented")
    def test_update_case_status(self):
        """CaseManager.update_investigation_case must persist status change."""
        import sqlite3
        from backend.investigation.case_manager import CaseManager
        DDL = """
        CREATE TABLE IF NOT EXISTS investigation_cases (
            case_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            case_status TEXT NOT NULL DEFAULT 'open',
            related_alerts TEXT DEFAULT '[]',
            related_entities TEXT DEFAULT '[]',
            timeline_events TEXT DEFAULT '[]',
            analyst_notes TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            artifacts TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
        conn = sqlite3.connect(":memory:")
        conn.executescript(DDL)
        conn.commit()
        cm = CaseManager()
        case_id = cm.create_investigation_case(conn, "Status Test")
        cm.update_investigation_case(conn, case_id, {"case_status": "in-progress"})
        case = cm.get_investigation_case(conn, case_id)
        assert case is not None, "Case must exist after creation"
        assert case.get("case_status") == "in-progress", \
            f"Expected case_status='in-progress', got {case.get('case_status')!r}"


# ---------------------------------------------------------------------------
# TestCaseAPI
# Tests for the investigation case REST endpoints.
# P7: Plan 01 will implement endpoints in investigation_routes.py.
# ---------------------------------------------------------------------------

class TestCaseAPI:
    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 01 not yet implemented")
    def test_create_case_endpoint(self):
        """POST /api/cases must return 200 with case_id in response."""
        r = client.post("/api/cases", json={"title": "Test Case", "description": ""})
        assert r.status_code == 200, \
            f"POST /api/cases must return 200, got {r.status_code}"
        data = r.json()
        assert "case_id" in data, \
            f"Response must contain 'case_id'; got keys: {list(data.keys())}"

    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 01 not yet implemented")
    def test_list_cases_endpoint(self):
        """GET /api/cases must return 200."""
        r = client.get("/api/cases")
        assert r.status_code == 200, \
            f"GET /api/cases must return 200, got {r.status_code}"

    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 01 not yet implemented")
    def test_get_case_detail(self):
        """GET /api/cases/{case_id} must return 200 with case_status field."""
        # Create case first
        r = client.post("/api/cases", json={"title": "Detail Test"})
        assert r.status_code == 200, "Case creation must succeed"
        case_id = r.json()["case_id"]
        r2 = client.get(f"/api/cases/{case_id}")
        assert r2.status_code == 200, \
            f"GET /api/cases/{case_id} must return 200, got {r2.status_code}"
        data = r2.json()
        assert "case_status" in data, \
            f"Response must contain 'case_status'; got keys: {list(data.keys())}"

    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 01 not yet implemented")
    def test_patch_case_status(self):
        """PATCH /api/cases/{case_id} with case_status must return 200."""
        r = client.post("/api/cases", json={"title": "Patch Test"})
        assert r.status_code == 200, "Case creation must succeed"
        case_id = r.json()["case_id"]
        r2 = client.patch(f"/api/cases/{case_id}", json={"case_status": "in-progress"})
        assert r2.status_code == 200, \
            f"PATCH /api/cases/{case_id} must return 200, got {r2.status_code}"


# ---------------------------------------------------------------------------
# TestHuntEngine
# Tests for HUNT_TEMPLATES: threat hunting template registry.
# P7: Plan 02 will implement HUNT_TEMPLATES in investigation/hunt_engine.py.
# ---------------------------------------------------------------------------

class TestHuntEngine:
    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 02 not yet implemented")
    def test_suspicious_ip_template(self):
        """HUNT_TEMPLATES must contain 'suspicious_ip_comms' with 'dst_ip' param key."""
        from backend.investigation.hunt_engine import HUNT_TEMPLATES
        assert "suspicious_ip_comms" in HUNT_TEMPLATES, \
            f"'suspicious_ip_comms' not in HUNT_TEMPLATES; keys: {list(HUNT_TEMPLATES.keys())}"
        assert "dst_ip" in HUNT_TEMPLATES["suspicious_ip_comms"].param_keys, \
            f"'dst_ip' not in param_keys; got: {HUNT_TEMPLATES['suspicious_ip_comms'].param_keys}"

    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 02 not yet implemented")
    def test_powershell_children_template(self):
        """HUNT_TEMPLATES must contain 'powershell_children' with parent_process_name in SQL."""
        from backend.investigation.hunt_engine import HUNT_TEMPLATES
        assert "powershell_children" in HUNT_TEMPLATES, \
            f"'powershell_children' not in HUNT_TEMPLATES; keys: {list(HUNT_TEMPLATES.keys())}"
        assert "parent_process_name" in HUNT_TEMPLATES["powershell_children"].sql, \
            f"'parent_process_name' not in SQL template"


# ---------------------------------------------------------------------------
# TestHuntAPI
# Tests for the threat hunt REST endpoints.
# P7: Plan 02 will implement endpoints in investigation_routes.py.
# ---------------------------------------------------------------------------

class TestHuntAPI:
    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 02 not yet implemented")
    def test_list_hunt_templates(self):
        """GET /api/hunt/templates must return 200 with 4 templates."""
        r = client.get("/api/hunt/templates")
        assert r.status_code == 200, \
            f"GET /api/hunt/templates must return 200, got {r.status_code}"
        data = r.json()
        assert len(data.get("templates", [])) == 4, \
            f"Expected 4 templates, got {len(data.get('templates', []))}"

    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 02 not yet implemented")
    def test_execute_hunt(self):
        """POST /api/hunt must return 200 with 'results' key."""
        r = client.post("/api/hunt", json={"template": "powershell_children", "params": {}})
        assert r.status_code == 200, \
            f"POST /api/hunt must return 200, got {r.status_code}"
        data = r.json()
        assert "results" in data, \
            f"Response must contain 'results'; got keys: {list(data.keys())}"


# ---------------------------------------------------------------------------
# TestTimelineBuilder
# Tests for build_timeline: timeline construction for an investigation case.
# P7: Plan 03 will implement build_timeline in investigation/timeline_builder.py.
# ---------------------------------------------------------------------------

class TestTimelineBuilder:
    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 03 not yet implemented")
    def test_timeline_entry_shape(self):
        """build_timeline function must be callable (stub raises NotImplementedError — xfail)."""
        from backend.investigation.timeline_builder import build_timeline
        assert callable(build_timeline), "build_timeline must be a callable function"
        # Calling the stub raises NotImplementedError — this causes the xfail
        import asyncio
        asyncio.run(build_timeline("test-case", None, None))


# ---------------------------------------------------------------------------
# TestTimelineAPI
# Tests for GET /api/cases/{case_id}/timeline endpoint.
# P7: Plan 03 will implement this endpoint in investigation_routes.py.
# ---------------------------------------------------------------------------

class TestTimelineAPI:
    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 03 not yet implemented")
    def test_get_timeline(self):
        """GET /api/cases/{case_id}/timeline must return 200 with 'timeline' key."""
        r = client.post("/api/cases", json={"title": "Timeline Test"})
        assert r.status_code == 200, "Case creation must succeed"
        case_id = r.json()["case_id"]
        r2 = client.get(f"/api/cases/{case_id}/timeline")
        assert r2.status_code == 200, \
            f"GET /api/cases/{case_id}/timeline must return 200, got {r2.status_code}"
        data = r2.json()
        assert "timeline" in data, \
            f"Response must contain 'timeline'; got keys: {list(data.keys())}"


# ---------------------------------------------------------------------------
# TestArtifactStore
# Tests for save_artifact: file artifact persistence.
# P7: Plan 03 will implement save_artifact in investigation/artifact_store.py.
# ---------------------------------------------------------------------------

class TestArtifactStore:
    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 03 not yet implemented")
    def test_save_artifact(self):
        """save_artifact must return dict with 'artifact_id' key."""
        import asyncio
        import tempfile
        from backend.investigation.artifact_store import save_artifact
        tmp_dir = tempfile.mkdtemp()
        result = asyncio.run(
            save_artifact(tmp_dir, "case-001", "artifact-001", "evidence.txt", b"evidence data", None)
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "artifact_id" in result, \
            f"Result must have 'artifact_id'; got keys: {list(result.keys())}"


# ---------------------------------------------------------------------------
# TestArtifactAPI
# Tests for POST /api/cases/{case_id}/artifacts endpoint.
# P7: Plan 03 will implement this endpoint in investigation_routes.py.
# ---------------------------------------------------------------------------

class TestArtifactAPI:
    @pytest.mark.xfail(strict=False, reason="Phase 7 Plan 03 not yet implemented")
    def test_upload_artifact(self):
        """POST /api/cases/{case_id}/artifacts must return 200 with 'artifact_id' key."""
        r = client.post("/api/cases", json={"title": "Artifact Upload Test"})
        assert r.status_code == 200, "Case creation must succeed"
        case_id = r.json()["case_id"]
        r2 = client.post(
            f"/api/cases/{case_id}/artifacts",
            files={"file": ("test.txt", b"evidence data", "text/plain")},
            data={"description": "test artifact"},
        )
        assert r2.status_code == 200, \
            f"POST /api/cases/{case_id}/artifacts must return 200, got {r2.status_code}"
        data = r2.json()
        assert "artifact_id" in data, \
            f"Response must contain 'artifact_id'; got keys: {list(data.keys())}"


# ---------------------------------------------------------------------------
# TestDashboardBuild
# Tests that the frontend npm build succeeds with Phase 7 components.
# P7: Plan 04 will add Phase 7 dashboard components.
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False, reason="dashboard build test — passes when npm build is green")
def test_dashboard_build():
    """npm run build in dashboard/ must exit 0."""
    import subprocess
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd="dashboard",
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, \
        f"npm run build failed with exit code {result.returncode}.\n" \
        f"stdout: {result.stdout.decode()[-1000:]}\n" \
        f"stderr: {result.stderr.decode()[-1000:]}"
