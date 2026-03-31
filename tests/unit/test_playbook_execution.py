"""
Unit tests for playbook execution engine endpoints (Phase 17 Plan 02).
TDD RED phase — tests written before implementation.

Tests cover:
- POST /api/playbooks/{playbook_id}/run/{investigation_id}
- PATCH /api/playbook-runs/{run_id}/step/{step_n}
- PATCH /api/playbook-runs/{run_id}/cancel
- GET /api/playbook-runs/{run_id}
- GET /api/playbook-runs/{run_id}/stream (SSE snapshot)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.playbooks import router, runs_router
from backend.stores.sqlite_store import SQLiteStore


# ---------------------------------------------------------------------------
# App + client fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(data_dir=str(tmp_path))


@pytest.fixture()
def app(store: SQLiteStore) -> FastAPI:
    """Minimal FastAPI app wired with both playbook routers."""
    from unittest.mock import MagicMock

    application = FastAPI()
    application.state.stores = MagicMock()
    application.state.stores.sqlite = store
    application.include_router(router)
    application.include_router(runs_router)
    return application


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_playbook(client: TestClient, step_count: int = 2) -> dict:
    """Create a playbook with the given number of steps and return the dict."""
    steps = [
        {
            "step_number": i + 1,
            "title": f"Step {i + 1}",
            "description": f"Description for step {i + 1}",
            "requires_approval": True,
        }
        for i in range(step_count)
    ]
    resp = client.post(
        "/api/playbooks",
        json={
            "name": f"Test Playbook ({step_count} steps)",
            "description": "A test playbook",
            "trigger_conditions": ["test"],
            "steps": steps,
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/playbooks/{playbook_id}/run/{investigation_id}
# ---------------------------------------------------------------------------


class TestStartRun:
    def test_start_run_creates_run_record(self, client: TestClient) -> None:
        """Starting a run returns 201 with a run dict including run_id."""
        pb = _create_playbook(client, step_count=2)
        resp = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/investigation-001"
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["playbook_id"] == pb["playbook_id"]
        assert data["investigation_id"] == "investigation-001"
        assert data["status"] == "running"
        assert data["steps_completed"] == []
        assert data["completed_at"] is None
        assert "run_id" in data
        assert "started_at" in data

    def test_start_run_returns_404_for_missing_playbook(self, client: TestClient) -> None:
        """Starting a run against a non-existent playbook returns 404."""
        resp = client.post(
            "/api/playbooks/no-such-playbook/run/investigation-001"
        )
        assert resp.status_code == 404

    def test_start_run_persists_to_store(self, client: TestClient, store: SQLiteStore) -> None:
        """The created run is stored and retrievable from SQLite."""
        pb = _create_playbook(client, step_count=1)
        resp = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/investigation-xyz"
        )
        run_id = resp.json()["run_id"]
        stored = store.get_playbook_run(run_id)
        assert stored is not None
        assert stored["investigation_id"] == "investigation-xyz"


# ---------------------------------------------------------------------------
# PATCH /api/playbook-runs/{run_id}/step/{step_n}
# ---------------------------------------------------------------------------


class TestAdvanceStep:
    def test_advance_step_appends_to_steps_completed(self, client: TestClient) -> None:
        """Advancing a step appends a step result to steps_completed."""
        pb = _create_playbook(client, step_count=3)
        run_id = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/inv-001"
        ).json()["run_id"]

        resp = client.patch(
            f"/api/playbook-runs/{run_id}/step/1",
            json={"analyst_note": "Checked logs", "outcome": "confirmed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["steps_completed"]) == 1
        step_entry = data["steps_completed"][0]
        assert step_entry["step_number"] == 1
        assert step_entry["outcome"] == "confirmed"
        assert step_entry["analyst_note"] == "Checked logs"
        assert "completed_at" in step_entry

    def test_advance_step_does_not_complete_on_non_final(self, client: TestClient) -> None:
        """Advancing a non-final step keeps status='running'."""
        pb = _create_playbook(client, step_count=3)
        run_id = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/inv-002"
        ).json()["run_id"]

        resp = client.patch(
            f"/api/playbook-runs/{run_id}/step/1",
            json={"analyst_note": "", "outcome": "confirmed"},
        )
        assert resp.json()["status"] == "running"
        assert resp.json()["completed_at"] is None

    def test_advance_last_step_sets_completed(self, client: TestClient) -> None:
        """Advancing the final step sets status='completed' and completed_at."""
        pb = _create_playbook(client, step_count=2)
        run_id = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/inv-003"
        ).json()["run_id"]

        # Advance step 1
        client.patch(
            f"/api/playbook-runs/{run_id}/step/1",
            json={"analyst_note": "Step 1 done", "outcome": "confirmed"},
        )
        # Advance final step 2
        resp = client.patch(
            f"/api/playbook-runs/{run_id}/step/2",
            json={"analyst_note": "Step 2 done", "outcome": "confirmed"},
        )
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None
        assert len(data["steps_completed"]) == 2

    def test_advance_step_skipped_outcome(self, client: TestClient) -> None:
        """Advancing with outcome='skipped' stores 'skipped' in the entry."""
        pb = _create_playbook(client, step_count=2)
        run_id = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/inv-004"
        ).json()["run_id"]

        resp = client.patch(
            f"/api/playbook-runs/{run_id}/step/1",
            json={"analyst_note": "Not applicable", "outcome": "skipped"},
        )
        assert resp.json()["steps_completed"][0]["outcome"] == "skipped"

    def test_advance_step_returns_404_for_missing_run(self, client: TestClient) -> None:
        """Advancing a step on a non-existent run returns 404."""
        resp = client.patch(
            "/api/playbook-runs/no-such-run/step/1",
            json={"analyst_note": "", "outcome": "confirmed"},
        )
        assert resp.status_code == 404

    def test_advance_step_returns_409_if_completed(self, client: TestClient) -> None:
        """Advancing a step on an already-completed run returns 409."""
        pb = _create_playbook(client, step_count=1)
        run_id = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/inv-005"
        ).json()["run_id"]

        # Complete the run
        client.patch(
            f"/api/playbook-runs/{run_id}/step/1",
            json={"analyst_note": "done", "outcome": "confirmed"},
        )
        # Try to advance again
        resp = client.patch(
            f"/api/playbook-runs/{run_id}/step/1",
            json={"analyst_note": "again", "outcome": "confirmed"},
        )
        assert resp.status_code == 409

    def test_advance_step_returns_409_if_cancelled(self, client: TestClient) -> None:
        """Advancing a step on a cancelled run returns 409."""
        pb = _create_playbook(client, step_count=2)
        run_id = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/inv-006"
        ).json()["run_id"]

        client.patch(f"/api/playbook-runs/{run_id}/cancel")
        resp = client.patch(
            f"/api/playbook-runs/{run_id}/step/1",
            json={"analyst_note": "too late", "outcome": "confirmed"},
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# PATCH /api/playbook-runs/{run_id}/cancel
# ---------------------------------------------------------------------------


class TestCancelRun:
    def test_cancel_sets_status_cancelled(self, client: TestClient) -> None:
        """Cancelling a running run sets status='cancelled' and completed_at."""
        pb = _create_playbook(client, step_count=2)
        run_id = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/inv-007"
        ).json()["run_id"]

        resp = client.patch(f"/api/playbook-runs/{run_id}/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["completed_at"] is not None

    def test_cancel_returns_404_for_missing_run(self, client: TestClient) -> None:
        """Cancelling a non-existent run returns 404."""
        resp = client.patch("/api/playbook-runs/no-such-run/cancel")
        assert resp.status_code == 404

    def test_cancel_returns_409_if_already_completed(self, client: TestClient) -> None:
        """Cancelling an already-completed run returns 409."""
        pb = _create_playbook(client, step_count=1)
        run_id = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/inv-008"
        ).json()["run_id"]

        # Complete it
        client.patch(
            f"/api/playbook-runs/{run_id}/step/1",
            json={"analyst_note": "done", "outcome": "confirmed"},
        )
        # Try to cancel
        resp = client.patch(f"/api/playbook-runs/{run_id}/cancel")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# GET /api/playbook-runs/{run_id}
# ---------------------------------------------------------------------------


class TestGetRun:
    def test_get_run_returns_run(self, client: TestClient) -> None:
        """GET /api/playbook-runs/{run_id} returns the run dict."""
        pb = _create_playbook(client, step_count=1)
        run_id = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/inv-009"
        ).json()["run_id"]

        resp = client.get(f"/api/playbook-runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == run_id

    def test_get_run_returns_404_for_missing(self, client: TestClient) -> None:
        """GET /api/playbook-runs/{run_id} returns 404 for unknown run."""
        resp = client.get("/api/playbook-runs/no-such-run")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/playbook-runs/{run_id}/stream (SSE snapshot)
# ---------------------------------------------------------------------------


class TestStreamRun:
    def test_stream_returns_event_stream_content_type(self, client: TestClient) -> None:
        """GET /stream returns text/event-stream content type."""
        pb = _create_playbook(client, step_count=1)
        run_id = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/inv-010"
        ).json()["run_id"]

        resp = client.get(f"/api/playbook-runs/{run_id}/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_stream_emits_run_state_and_done_events(self, client: TestClient) -> None:
        """GET /stream emits a run_state event then a done event."""
        pb = _create_playbook(client, step_count=1)
        run_id = client.post(
            f"/api/playbooks/{pb['playbook_id']}/run/inv-011"
        ).json()["run_id"]

        resp = client.get(f"/api/playbook-runs/{run_id}/stream")
        body = resp.text

        # Parse SSE lines
        events = [
            json.loads(line[6:])
            for line in body.splitlines()
            if line.startswith("data: ")
        ]
        assert len(events) == 2
        assert events[0]["event"] == "run_state"
        assert events[0]["run"]["run_id"] == run_id
        assert events[1].get("done") is True

    def test_stream_returns_404_for_missing_run(self, client: TestClient) -> None:
        """GET /stream returns 404 for an unknown run_id."""
        resp = client.get("/api/playbook-runs/no-such-run/stream")
        assert resp.status_code == 404
