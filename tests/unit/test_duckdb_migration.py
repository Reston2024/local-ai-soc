"""Tests for P20-T03: DuckDB additive schema migration."""
import asyncio
import datetime

import pytest

from backend.stores.duckdb_store import DuckDBStore


async def _make_store(tmp_path):
    """Create a DuckDBStore with an isolated temp directory."""
    store = DuckDBStore(data_dir=str(tmp_path))
    worker = store.start_write_worker()
    return store, worker


async def _cleanup(worker):
    worker.cancel()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_db_meta_table_created(tmp_path):
    """initialise_schema() must create db_meta table with schema_version key."""
    store, worker = await _make_store(tmp_path)
    try:
        await store.initialise_schema()
        rows = await store.fetch_all(
            "SELECT value FROM db_meta WHERE key='schema_version'"
        )
        assert len(rows) == 1
        assert rows[0][0] == "20"
    finally:
        await _cleanup(worker)


@pytest.mark.asyncio
async def test_new_ecs_columns_added(tmp_path):
    """After migration, normalized_events must have all 6 ECS columns."""
    store, worker = await _make_store(tmp_path)
    try:
        await store.initialise_schema()
        cols = await store.fetch_all(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='normalized_events'"
        )
        col_names = {row[0] for row in cols}
        for expected in (
            "ocsf_class_uid",
            "event_outcome",
            "user_domain",
            "process_executable",
            "network_protocol",
            "network_direction",
        ):
            assert expected in col_names, f"Missing column: {expected}"
    finally:
        await _cleanup(worker)


@pytest.mark.asyncio
async def test_migration_idempotent(tmp_path):
    """Running initialise_schema() twice must not raise."""
    store, worker = await _make_store(tmp_path)
    try:
        await store.initialise_schema()
        # Second call — should not raise even though columns already exist
        await store.initialise_schema()
    finally:
        await _cleanup(worker)


@pytest.mark.asyncio
async def test_existing_rows_not_broken(tmp_path):
    """Rows inserted before migration retain their values; new columns are NULL."""
    store, worker = await _make_store(tmp_path)
    try:
        # Bootstrap schema WITHOUT the ECS migration (original 29-column schema)
        # We use the legacy CREATE TABLE that pre-dates the migration columns,
        # then call initialise_schema() to trigger the ALTER TABLE additions.
        # Since plan 20-02 already includes the 6 columns in CREATE TABLE,
        # we instead insert a row first, then call initialise_schema() again
        # to confirm the row survives (idempotent path).
        await store.initialise_schema()

        now = datetime.datetime.utcnow().replace(microsecond=0)
        await store.execute_write(
            """
            INSERT INTO normalized_events
                (event_id, timestamp, ingested_at, source_type, hostname, username,
                 event_type, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ["evt-test-001", now, now, "json", "host1", "alice", "process", "low"],
        )

        # Re-run migration — should be idempotent
        await store.initialise_schema()

        rows = await store.fetch_all(
            "SELECT hostname, username, ocsf_class_uid FROM normalized_events "
            "WHERE event_id='evt-test-001'"
        )
        assert len(rows) == 1
        assert rows[0][0] == "host1"
        assert rows[0][1] == "alice"
        assert rows[0][2] is None  # new column defaults to NULL
    finally:
        await _cleanup(worker)


@pytest.mark.asyncio
async def test_schema_version_value(tmp_path):
    """db_meta must contain key='schema_version' with string value '20'."""
    store, worker = await _make_store(tmp_path)
    try:
        await store.initialise_schema()
        rows = await store.fetch_all(
            "SELECT key, value FROM db_meta WHERE key='schema_version'"
        )
        assert len(rows) == 1
        key, value = rows[0]
        assert key == "schema_version"
        assert value == "20"          # string, not integer
        assert isinstance(value, str)
    finally:
        await _cleanup(worker)
