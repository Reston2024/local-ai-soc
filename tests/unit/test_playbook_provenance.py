"""Tests for P21-T04: playbook run provenance.

Validates:
- playbook_run_provenance table is created by SQLiteStore.__init__
- record_playbook_provenance / get_playbook_provenance roundtrip
- GET /api/provenance/playbook/{run_id} returns 200 with correct fields
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import os

import pytest

from backend.models.provenance import PlaybookProvenanceRecord
from backend.stores.sqlite_store import SQLiteStore


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_store() -> SQLiteStore:
    """Create a SQLiteStore in a temp directory so we can inspect tables."""
    td = tempfile.mkdtemp()
    store = SQLiteStore(td)
    return store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_playbook_provenance_table_exists():
    """SQLiteStore creates playbook_run_provenance table on init."""
    store = _make_store()
    try:
        tables = [
            r[0]
            for r in store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "playbook_run_provenance" in tables, (
            f"playbook_run_provenance table missing; tables found: {tables}"
        )
    finally:
        store.close()
        shutil.rmtree(os.path.dirname(store._db_path), ignore_errors=True)


def test_playbook_provenance_fields():
    """Playbook provenance row contains playbook_file_sha256 and operator_id_who_approved."""
    store = _make_store()
    try:
        steps_json = json.dumps([{"action": "isolate_host"}])
        sha256 = hashlib.sha256(steps_json.encode()).hexdigest()

        store.record_playbook_provenance(
            prov_id="prov-001",
            run_id="run-abc",
            playbook_id="pb-xyz",
            playbook_file_sha256=sha256,
            playbook_version="1.0",
            trigger_event_ids=["evt-1", "evt-2"],
            operator_id_who_approved="op-alice",
        )

        row = store.get_playbook_provenance("run-abc")
        assert row is not None, "Expected a provenance row for run-abc"
        assert row["playbook_file_sha256"] == sha256, "SHA-256 mismatch"
        assert len(row["playbook_file_sha256"]) == 64, "SHA-256 should be 64 hex chars"
        assert row["operator_id_who_approved"] == "op-alice"
        assert isinstance(row["trigger_event_ids"], list), "trigger_event_ids should be a list"
        assert row["trigger_event_ids"] == ["evt-1", "evt-2"]
        assert row["playbook_version"] == "1.0"
        assert row["run_id"] == "run-abc"
        assert row["playbook_id"] == "pb-xyz"
    finally:
        store.close()
        shutil.rmtree(os.path.dirname(store._db_path), ignore_errors=True)


def test_playbook_provenance_api():
    """GET /api/provenance/playbook/{run_id} returns 200 with trigger_event_ids."""
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock
    from fastapi import FastAPI
    from backend.api.provenance import router as prov_router
    from backend.core.deps import get_stores

    # Build an isolated FastAPI app with the provenance router
    app = FastAPI()
    app.include_router(prov_router)

    # Create a real store with provenance data
    store = _make_store()
    steps_json = json.dumps([{"action": "contain_host"}, {"action": "notify_soc"}])
    sha256 = hashlib.sha256(steps_json.encode()).hexdigest()

    store.record_playbook_provenance(
        prov_id="prov-api-001",
        run_id="run-api-test",
        playbook_id="pb-nist",
        playbook_file_sha256=sha256,
        playbook_version="2.1",
        trigger_event_ids=["evt-99"],
        operator_id_who_approved="op-bob",
    )

    # Inject stores dependency
    stores_mock = MagicMock()
    stores_mock.sqlite = store
    app.dependency_overrides[get_stores] = lambda: stores_mock

    try:
        client = TestClient(app)
        response = client.get("/api/provenance/playbook/run-api-test")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["run_id"] == "run-api-test"
        assert data["playbook_file_sha256"] == sha256
        assert data["trigger_event_ids"] == ["evt-99"]
        assert data["operator_id_who_approved"] == "op-bob"

        # 404 for unknown run
        r404 = client.get("/api/provenance/playbook/no-such-run")
        assert r404.status_code == 404
    finally:
        store.close()
        shutil.rmtree(os.path.dirname(store._db_path), ignore_errors=True)
