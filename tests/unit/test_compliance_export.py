"""
Unit tests for GET /api/reports/compliance endpoint (Phase 18-04).

Tests cover:
- nist-csf framework returns application/zip with 6 JSON evidence files + summary.html
- thehive framework returns application/zip with alerts.json + cases.json
- Unknown framework returns 400

Uses FastAPI TestClient with minimal app fixture (real SQLiteStore in tmp_path,
mocked DuckDB to avoid DuckDB startup cost).
Auth is handled by passing Authorization: Bearer <token> with the same token
value that is patched into settings.AUTH_TOKEN.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

_AUTH_TOKEN = "compliance-test-token"
_AUTH_HEADERS = {"Authorization": f"Bearer {_AUTH_TOKEN}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sqlite_store(tmp_path: Path):
    """Real SQLiteStore backed by a temp directory."""
    from backend.stores.sqlite_store import SQLiteStore

    return SQLiteStore(data_dir=str(tmp_path))


@pytest.fixture()
def stores(sqlite_store):
    """Minimal Stores container: real SQLite + mocked DuckDB."""
    from backend.core.deps import Stores

    duckdb = MagicMock()
    duckdb.fetch_all = AsyncMock(return_value=[])

    chroma = MagicMock()
    chroma.query_async = AsyncMock(return_value=[])

    return Stores(duckdb=duckdb, chroma=chroma, sqlite=sqlite_store)


@pytest.fixture()
def client(stores):
    """FastAPI TestClient with injected stores and dependency-overridden auth."""
    from fastapi.testclient import TestClient

    from backend.core.auth import verify_token
    from backend.core.rbac import OperatorContext
    from backend.main import create_app

    app = create_app()
    app.state.stores = stores
    app.state.ollama = MagicMock()
    app.state.settings = MagicMock()

    # Bypass auth with dependency override — compliance tests are testing export logic, not auth.
    # Legacy token path is now TOTP-gated, so we override the dependency directly.
    _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
    app.dependency_overrides[verify_token] = lambda: _ctx

    yield TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComplianceExport:
    def test_nist_csf_returns_zip(self, client):
        """GET /api/reports/compliance?framework=nist-csf returns 200 application/zip
        containing summary.html and all 6 NIST CSF function JSON files."""
        response = client.get(
            "/api/reports/compliance?framework=nist-csf", headers=_AUTH_HEADERS
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "attachment" in response.headers.get("content-disposition", "")

        buf = io.BytesIO(response.content)
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()

        assert "summary.html" in names
        # Six NIST CSF 2.0 functions must each have a JSON evidence file
        expected_functions = {"govern", "identify", "protect", "detect", "respond", "recover"}
        json_files = {
            n.replace("nist-csf/", "").replace(".json", "")
            for n in names
            if n.startswith("nist-csf/")
        }
        assert json_files == expected_functions

    def test_thehive_returns_zip(self, client):
        """GET /api/reports/compliance?framework=thehive returns 200 application/zip
        containing thehive/alerts.json and thehive/cases.json."""
        response = client.get(
            "/api/reports/compliance?framework=thehive", headers=_AUTH_HEADERS
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "attachment" in response.headers.get("content-disposition", "")

        buf = io.BytesIO(response.content)
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()

        assert "thehive/alerts.json" in names
        assert "thehive/cases.json" in names

    def test_unknown_framework_400(self, client):
        """GET /api/reports/compliance?framework=unknown returns 400."""
        response = client.get(
            "/api/reports/compliance?framework=unknown", headers=_AUTH_HEADERS
        )

        assert response.status_code == 400
        body = response.json()
        assert "Unknown" in body["detail"] or "unknown" in body["detail"]
        assert "nist-csf" in body["detail"]
        assert "thehive" in body["detail"]

    def test_nist_csf_empty_database_returns_valid_zip(self, client):
        """Empty database still produces a valid ZIP — evidence arrays are empty."""
        response = client.get(
            "/api/reports/compliance?framework=nist-csf", headers=_AUTH_HEADERS
        )

        assert response.status_code == 200
        buf = io.BytesIO(response.content)
        with zipfile.ZipFile(buf, "r") as zf:
            import json

            identify_data = json.loads(zf.read("nist-csf/identify.json"))

        assert identify_data["detections"] == []
        assert identify_data["technique_count"] == 0

    def test_thehive_empty_database_returns_valid_zip(self, client):
        """Empty database produces a ZIP with empty alerts and cases arrays."""
        response = client.get(
            "/api/reports/compliance?framework=thehive", headers=_AUTH_HEADERS
        )

        assert response.status_code == 200
        buf = io.BytesIO(response.content)
        with zipfile.ZipFile(buf, "r") as zf:
            import json

            alerts = json.loads(zf.read("thehive/alerts.json"))
            cases = json.loads(zf.read("thehive/cases.json"))

        assert alerts == []
        assert cases == []

    def test_thehive_uses_analyst_notes_not_description(self, client, stores):
        """TheHive description field uses analyst_notes, not a non-existent description column."""
        stores.sqlite.create_investigation_case(
            title="Test Case",
            description="",
            case_id="case-001",
        )
        stores.sqlite.update_investigation_case(
            "case-001",
            {"analyst_notes": "This is the analyst observation."},
        )

        response = client.get(
            "/api/reports/compliance?framework=thehive", headers=_AUTH_HEADERS
        )
        assert response.status_code == 200

        buf = io.BytesIO(response.content)
        with zipfile.ZipFile(buf, "r") as zf:
            import json

            alerts = json.loads(zf.read("thehive/alerts.json"))

        assert len(alerts) == 1
        assert alerts[0]["description"] == "This is the analyst observation."
        assert alerts[0]["sourceRef"] == "case-001"
