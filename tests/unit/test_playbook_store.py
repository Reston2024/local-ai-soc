"""
Unit tests for playbook SQLite store methods and Pydantic models.
TDD RED phase — tests written before implementation.
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from backend.models.playbook import (
    Playbook,
    PlaybookCreate,
    PlaybookRun,
    PlaybookRunAdvance,
    PlaybookStep,
)
from backend.stores.sqlite_store import SQLiteStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path):
    """Return a SQLiteStore backed by a temporary directory."""
    return SQLiteStore(data_dir=str(tmp_path))


@pytest.fixture()
def sample_playbook_data():
    return {
        "name": "Test Phishing Playbook",
        "description": "A test playbook for phishing incidents",
        "trigger_conditions": ["phishing", "suspicious email"],
        "steps": [
            {
                "step_number": 1,
                "title": "Identify affected users",
                "description": "Check which users received the email",
                "requires_approval": True,
                "evidence_prompt": "List affected user accounts",
            },
            {
                "step_number": 2,
                "title": "Collect email headers",
                "description": "Gather email header information",
                "requires_approval": False,
                "evidence_prompt": None,
            },
        ],
        "version": "1.0",
        "is_builtin": False,
    }


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestPlaybookModels:
    def test_playbook_step_defaults(self):
        step = PlaybookStep(
            step_number=1,
            title="Check logs",
            description="Review authentication logs",
        )
        assert step.requires_approval is True
        assert step.evidence_prompt is None

    def test_playbook_step_full(self):
        step = PlaybookStep(
            step_number=2,
            title="Block IP",
            description="Block the source IP",
            requires_approval=False,
            evidence_prompt="Document the blocked IP and timestamp",
        )
        assert step.requires_approval is False
        assert step.evidence_prompt == "Document the blocked IP and timestamp"

    def test_playbook_defaults(self):
        pb = Playbook(
            playbook_id="test-id",
            name="Test",
            description="",
            trigger_conditions=[],
            steps=[],
            version="1.0",
            created_at="2026-01-01T00:00:00Z",
        )
        assert pb.is_builtin is False
        assert pb.version == "1.0"

    def test_playbook_create_fields(self):
        pc = PlaybookCreate(
            name="My Playbook",
            description="desc",
            trigger_conditions=["malware"],
            steps=[
                PlaybookStep(
                    step_number=1,
                    title="Isolate",
                    description="Isolate host",
                )
            ],
            version="2.0",
        )
        assert pc.name == "My Playbook"
        assert len(pc.steps) == 1

    def test_playbook_run_defaults(self):
        run = PlaybookRun(
            run_id="run-1",
            playbook_id="pb-1",
            investigation_id="inv-1",
            status="running",
            started_at="2026-01-01T00:00:00Z",
        )
        assert run.analyst_notes == ""
        assert run.steps_completed == []
        assert run.completed_at is None

    def test_playbook_run_advance_model(self):
        advance = PlaybookRunAdvance(
            step_number=1,
            notes="Completed step 1",
            evidence_collected="Found suspicious login",
            approved=True,
        )
        assert advance.step_number == 1
        assert advance.approved is True


# ---------------------------------------------------------------------------
# Store tests
# ---------------------------------------------------------------------------


class TestCreatePlaybook:
    def test_create_playbook_round_trip(self, store, sample_playbook_data):
        created = store.create_playbook(sample_playbook_data)

        assert "playbook_id" in created
        assert created["name"] == "Test Phishing Playbook"
        assert created["version"] == "1.0"
        assert created["is_builtin"] == 0 or created["is_builtin"] is False

    def test_create_playbook_json_fields_stored_as_list(self, store, sample_playbook_data):
        created = store.create_playbook(sample_playbook_data)
        playbook_id = created["playbook_id"]

        retrieved = store.get_playbook(playbook_id)
        assert isinstance(retrieved["trigger_conditions"], list)
        assert "phishing" in retrieved["trigger_conditions"]
        assert isinstance(retrieved["steps"], list)
        assert len(retrieved["steps"]) == 2

    def test_create_playbook_generates_uuid(self, store, sample_playbook_data):
        created = store.create_playbook(sample_playbook_data)
        assert len(created["playbook_id"]) == 36  # UUID4 format

    def test_create_playbook_sets_created_at(self, store, sample_playbook_data):
        created = store.create_playbook(sample_playbook_data)
        assert "created_at" in created
        assert created["created_at"] is not None


class TestGetPlaybooks:
    def test_get_playbooks_returns_empty_list(self, store):
        result = store.get_playbooks()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_playbooks_returns_all(self, store, sample_playbook_data):
        store.create_playbook(sample_playbook_data)
        store.create_playbook({**sample_playbook_data, "name": "Second Playbook"})

        result = store.get_playbooks()
        assert len(result) == 2

    def test_get_playbooks_json_fields_deserialized(self, store, sample_playbook_data):
        store.create_playbook(sample_playbook_data)
        result = store.get_playbooks()
        pb = result[0]
        assert isinstance(pb["trigger_conditions"], list)
        assert isinstance(pb["steps"], list)

    def test_get_playbook_not_found(self, store):
        result = store.get_playbook("nonexistent-id")
        assert result is None


class TestPlaybookRuns:
    def test_create_playbook_run_links_to_playbook(self, store, sample_playbook_data):
        playbook = store.create_playbook(sample_playbook_data)
        playbook_id = playbook["playbook_id"]

        run_data = {
            "playbook_id": playbook_id,
            "investigation_id": "inv-123",
        }
        run = store.create_playbook_run(run_data)

        assert "run_id" in run
        assert run["playbook_id"] == playbook_id
        assert run["investigation_id"] == "inv-123"
        assert run["status"] == "running"

    def test_create_playbook_run_generates_uuid(self, store, sample_playbook_data):
        playbook = store.create_playbook(sample_playbook_data)
        run = store.create_playbook_run({
            "playbook_id": playbook["playbook_id"],
            "investigation_id": "inv-001",
        })
        assert len(run["run_id"]) == 36

    def test_get_playbook_runs_empty_for_new_playbook(self, store, sample_playbook_data):
        playbook = store.create_playbook(sample_playbook_data)
        runs = store.get_playbook_runs(playbook["playbook_id"])
        assert isinstance(runs, list)
        assert len(runs) == 0

    def test_get_playbook_runs_returns_all_for_playbook(self, store, sample_playbook_data):
        playbook = store.create_playbook(sample_playbook_data)
        pb_id = playbook["playbook_id"]

        store.create_playbook_run({"playbook_id": pb_id, "investigation_id": "inv-1"})
        store.create_playbook_run({"playbook_id": pb_id, "investigation_id": "inv-2"})

        runs = store.get_playbook_runs(pb_id)
        assert len(runs) == 2

    def test_get_playbook_run_by_id(self, store, sample_playbook_data):
        playbook = store.create_playbook(sample_playbook_data)
        run = store.create_playbook_run({
            "playbook_id": playbook["playbook_id"],
            "investigation_id": "inv-abc",
        })
        retrieved = store.get_playbook_run(run["run_id"])
        assert retrieved is not None
        assert retrieved["run_id"] == run["run_id"]

    def test_get_playbook_run_not_found(self, store):
        result = store.get_playbook_run("nonexistent-run-id")
        assert result is None


class TestUpdatePlaybookRun:
    def test_update_playbook_run_status(self, store, sample_playbook_data):
        playbook = store.create_playbook(sample_playbook_data)
        run = store.create_playbook_run({
            "playbook_id": playbook["playbook_id"],
            "investigation_id": "inv-update",
        })

        updated = store.update_playbook_run(run["run_id"], {
            "status": "completed",
            "completed_at": "2026-01-01T12:00:00Z",
        })

        assert updated["status"] == "completed"
        assert updated["completed_at"] == "2026-01-01T12:00:00Z"

    def test_update_playbook_run_steps_completed(self, store, sample_playbook_data):
        playbook = store.create_playbook(sample_playbook_data)
        run = store.create_playbook_run({
            "playbook_id": playbook["playbook_id"],
            "investigation_id": "inv-steps",
        })

        steps = [{"step_number": 1, "completed_at": "2026-01-01T10:00:00Z", "notes": "Done"}]
        updated = store.update_playbook_run(run["run_id"], {"steps_completed": steps})

        assert isinstance(updated["steps_completed"], list)
        assert len(updated["steps_completed"]) == 1
        assert updated["steps_completed"][0]["step_number"] == 1

    def test_update_playbook_run_analyst_notes(self, store, sample_playbook_data):
        playbook = store.create_playbook(sample_playbook_data)
        run = store.create_playbook_run({
            "playbook_id": playbook["playbook_id"],
            "investigation_id": "inv-notes",
        })

        updated = store.update_playbook_run(run["run_id"], {
            "analyst_notes": "Suspicious activity confirmed",
        })

        assert updated["analyst_notes"] == "Suspicious activity confirmed"
