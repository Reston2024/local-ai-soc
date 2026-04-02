"""Failing test stubs for P21-T04: playbook run provenance (RED state).

All tests intentionally call pytest.fail() — they will be made GREEN
in the Wave 1 executor plans that implement the actual functionality.
"""
import pytest

from backend.models.provenance import PlaybookProvenanceRecord


def test_playbook_provenance_table_exists():
    """SQLiteStore creates playbook_run_provenance table on init."""
    pytest.fail("NOT IMPLEMENTED")


def test_playbook_provenance_fields():
    """Playbook provenance row contains playbook_file_sha256 and operator_id_who_approved."""
    pytest.fail("NOT IMPLEMENTED")


def test_playbook_provenance_api():
    """GET /api/provenance/playbook/{run_id} returns 200 with trigger_event_ids."""
    pytest.fail("NOT IMPLEMENTED")
