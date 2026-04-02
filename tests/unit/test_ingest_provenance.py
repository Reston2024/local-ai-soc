"""Failing test stubs for P21-T01: ingest provenance (RED state).

All tests intentionally call pytest.fail() — they will be made GREEN
in the Wave 1 executor plans that implement the actual functionality.
"""
import pytest

from backend.models.provenance import IngestProvenanceRecord


def test_ingest_provenance_table_exists():
    """SQLiteStore creates ingest_provenance and ingest_provenance_events tables on init."""
    pytest.fail("NOT IMPLEMENTED")


def test_sha256_file_hash():
    """_sha256_file() returns a 64-character hex string for any file path."""
    pytest.fail("NOT IMPLEMENTED")


def test_ingest_provenance_written():
    """A row is written to ingest_provenance after ingest_file() completes successfully."""
    pytest.fail("NOT IMPLEMENTED")


def test_ingest_provenance_api():
    """GET /api/provenance/ingest/{event_id} returns 200 with raw_sha256 and parser_name."""
    pytest.fail("NOT IMPLEMENTED")


def test_ingest_provenance_failure_nonfatal():
    """A SQLite INSERT failure in provenance recording does not abort the ingestion pipeline."""
    pytest.fail("NOT IMPLEMENTED")
