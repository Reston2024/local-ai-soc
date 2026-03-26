"""Unit tests for backend/stores/duckdb_store.py — write queue + fetch_all."""
import pytest
pytestmark = pytest.mark.unit


@pytest.fixture
async def store(tmp_path):
    from backend.stores.duckdb_store import DuckDBStore
    s = DuckDBStore(str(tmp_path / "duckdb"))
    s.start_write_worker()
    await s.initialise_schema()
    yield s
    await s.close()


class TestDuckDBStore:
    async def test_initialize_creates_table(self, store):
        rows = await store.fetch_all(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name = 'normalized_events'"
        )
        assert len(rows) == 1

    async def test_execute_write_inserts_row(self, store):
        import uuid
        from datetime import datetime, timezone
        eid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await store.execute_write(
            "INSERT OR IGNORE INTO normalized_events (event_id, timestamp, ingested_at, source_type) "
            "VALUES (?, ?, ?, ?)",
            [eid, now, now, "json"],
        )
        rows = await store.fetch_all(
            "SELECT event_id FROM normalized_events WHERE event_id = ?",
            [eid],
        )
        assert len(rows) == 1
        # fetch_all returns list of tuples; event_id is first column
        assert rows[0][0] == eid

    async def test_fetch_all_returns_list(self, store):
        result = await store.fetch_all("SELECT 1 AS n")
        assert isinstance(result, list)
        assert result[0][0] == 1

    async def test_duplicate_insert_ignored(self, store):
        import uuid
        from datetime import datetime, timezone
        eid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        sql = (
            "INSERT OR IGNORE INTO normalized_events "
            "(event_id, timestamp, ingested_at, source_type) VALUES (?, ?, ?, ?)"
        )
        await store.execute_write(sql, [eid, now, now, "json"])
        await store.execute_write(sql, [eid, now, now, "json"])
        rows = await store.fetch_all(
            "SELECT event_id FROM normalized_events WHERE event_id = ?",
            [eid],
        )
        assert len(rows) == 1
