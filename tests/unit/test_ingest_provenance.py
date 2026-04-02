"""Tests for P21-T01: ingest provenance (ingest_provenance + ingest_provenance_events tables).

Tests follow TDD protocol:
- RED: written before implementation
- GREEN: made to pass after implementation
"""
from __future__ import annotations

import asyncio
import hashlib
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from backend.models.provenance import IngestProvenanceRecord


# ---------------------------------------------------------------------------
# Task 1 tests: SQLiteStore DDL and methods
# ---------------------------------------------------------------------------


def test_ingest_provenance_table_exists():
    """SQLiteStore creates ingest_provenance and ingest_provenance_events tables on init."""
    from backend.stores.sqlite_store import SQLiteStore

    store = SQLiteStore(":memory:")
    tables = {
        row[0]
        for row in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "ingest_provenance" in tables, f"ingest_provenance missing from {tables}"
    assert "ingest_provenance_events" in tables, (
        f"ingest_provenance_events missing from {tables}"
    )


def test_ingest_provenance_record_and_lookup():
    """record_ingest_provenance writes rows; get_ingest_provenance retrieves them."""
    from backend.stores.sqlite_store import SQLiteStore

    store = SQLiteStore(":memory:")
    store.record_ingest_provenance(
        prov_id="prov-001",
        raw_sha256="a" * 64,
        source_file="/tmp/test.ndjson",
        parser_name="NdjsonParser",
        event_ids=["evt-1", "evt-2"],
        parser_version="1.0",
        operator_id="op-abc",
    )

    row = store.get_ingest_provenance("evt-1")
    assert row is not None
    assert row["prov_id"] == "prov-001"
    assert row["raw_sha256"] == "a" * 64
    assert row["parser_name"] == "NdjsonParser"
    assert row["operator_id"] == "op-abc"

    row2 = store.get_ingest_provenance("evt-2")
    assert row2 is not None
    assert row2["prov_id"] == "prov-001"

    missing = store.get_ingest_provenance("evt-nonexistent")
    assert missing is None


# ---------------------------------------------------------------------------
# Task 2 tests: _sha256_file helper and provenance recording in loader.py
# ---------------------------------------------------------------------------


def test_sha256_file_hash():
    """_sha256_file() returns a 64-character hex string for any file path."""
    from ingestion.loader import _sha256_file

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"hello world\n")
        tmp_path = f.name

    try:
        digest = _sha256_file(tmp_path)
        assert len(digest) == 64, f"Expected 64 chars, got {len(digest)}"
        assert all(c in "0123456789abcdef" for c in digest), (
            f"Non-hex chars in digest: {digest}"
        )
        # Verify it matches hashlib directly
        expected = hashlib.sha256(b"hello world\n").hexdigest()
        assert digest == expected
    finally:
        os.unlink(tmp_path)


def test_ingest_provenance_written():
    """A row is written to ingest_provenance after ingest_file() completes successfully."""
    from backend.stores.sqlite_store import SQLiteStore
    from ingestion.loader import IngestionLoader

    # Build a minimal stores mock
    sqlite_store = SQLiteStore(":memory:")

    stores = MagicMock()
    stores.sqlite = sqlite_store

    # DuckDB fetch_all returns empty (no duplicates)
    async def fake_fetch_all(sql, params=None):
        return []

    # DuckDB execute_write is a no-op
    async def fake_execute_write(sql, params=None):
        return None

    stores.duckdb.fetch_all = fake_fetch_all
    stores.duckdb.execute_write = fake_execute_write

    # Chroma add_documents_async is a no-op
    stores.chroma.add_documents_async = AsyncMock(return_value=None)

    # Ollama embed_batch returns empty (skip embedding)
    ollama = MagicMock()
    ollama.embed_batch = AsyncMock(return_value=[])

    loader = IngestionLoader(stores, ollama)

    # Write a real NDJSON fixture file
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".ndjson", mode="w"
    ) as f:
        import json as _json
        f.write(
            _json.dumps(
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "source_type": "json",
                    "event_type": "process",
                    "severity": "low",
                    "hostname": "host1",
                }
            )
            + "\n"
        )
        tmp_path = f.name

    try:
        result = asyncio.run(
            loader.ingest_file(tmp_path, case_id=None, operator_id=None)
        )
        assert result.loaded > 0, f"Expected events loaded, got {result.loaded}"

        # Provenance row must exist — look up the actual event_id assigned by the parser
        prov_rows = sqlite_store._conn.execute(
            "SELECT * FROM ingest_provenance"
        ).fetchall()
        assert len(prov_rows) == 1, (
            f"Expected 1 ingest_provenance row, got {len(prov_rows)}"
        )
        prov = dict(prov_rows[0])
        assert len(prov["raw_sha256"]) == 64, "raw_sha256 must be 64-char hex"
        assert prov["source_file"] == tmp_path
        assert prov["parser_name"] != "", "parser_name must be set"

        # Junction table must have at least 1 row linking prov → event
        evt_rows = sqlite_store._conn.execute(
            "SELECT * FROM ingest_provenance_events WHERE prov_id = ?",
            (prov["prov_id"],),
        ).fetchall()
        assert len(evt_rows) >= 1, "No event rows in ingest_provenance_events"

        # get_ingest_provenance lookup via actual event_id must work
        actual_event_id = dict(evt_rows[0])["event_id"]
        row = sqlite_store.get_ingest_provenance(actual_event_id)
        assert row is not None, (
            f"get_ingest_provenance returned None for event_id={actual_event_id}"
        )
        assert row["prov_id"] == prov["prov_id"]
    finally:
        os.unlink(tmp_path)


def test_ingest_provenance_failure_nonfatal():
    """A SQLite INSERT failure in provenance recording does not abort the ingestion pipeline."""
    from backend.stores.sqlite_store import SQLiteStore
    from ingestion.loader import IngestionLoader

    sqlite_store = SQLiteStore(":memory:")

    # Make record_ingest_provenance raise
    def _boom(*args, **kwargs):
        raise RuntimeError("provenance write boom")

    sqlite_store.record_ingest_provenance = _boom

    stores = MagicMock()
    stores.sqlite = sqlite_store

    async def fake_fetch_all(sql, params=None):
        return []

    async def fake_execute_write(sql, params=None):
        return None

    stores.duckdb.fetch_all = fake_fetch_all
    stores.duckdb.execute_write = fake_execute_write
    stores.chroma.add_documents_async = AsyncMock(return_value=None)

    ollama = MagicMock()
    ollama.embed_batch = AsyncMock(return_value=[])

    loader = IngestionLoader(stores, ollama)

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".ndjson", mode="w"
    ) as f:
        import json as _json
        f.write(
            _json.dumps(
                {
                    "event_id": "test-evt-nonfatal-001",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "source_type": "json",
                    "event_type": "process",
                    "severity": "low",
                    "hostname": "host2",
                }
            )
            + "\n"
        )
        tmp_path = f.name

    try:
        # Must not raise despite provenance failure
        result = asyncio.run(
            loader.ingest_file(tmp_path, case_id=None, operator_id=None)
        )
        assert result.loaded > 0, f"Ingest should succeed; got {result.loaded}"
    finally:
        os.unlink(tmp_path)
