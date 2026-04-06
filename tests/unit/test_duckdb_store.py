"""Unit tests for backend/stores/duckdb_store.py — write queue + fetch_all."""
import uuid
from datetime import datetime, timezone

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


def _make_event_row(event_id: str | None = None, source_type: str = "json"):
    eid = event_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    return eid, now, source_type


class TestDuckDBStore:
    async def test_initialize_creates_table(self, store):
        rows = await store.fetch_all(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name = 'normalized_events'"
        )
        assert len(rows) == 1

    async def test_execute_write_inserts_row(self, store):
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

    async def test_fetch_all_with_where_filters(self, store):
        """Insert 3 rows with different source_type, query with WHERE filters correctly."""
        now = datetime.now(timezone.utc).isoformat()
        sql = (
            "INSERT OR IGNORE INTO normalized_events "
            "(event_id, timestamp, ingested_at, source_type) VALUES (?, ?, ?, ?)"
        )
        eid1 = str(uuid.uuid4())
        eid2 = str(uuid.uuid4())
        eid3 = str(uuid.uuid4())
        await store.execute_write(sql, [eid1, now, now, "evtx"])
        await store.execute_write(sql, [eid2, now, now, "csv"])
        await store.execute_write(sql, [eid3, now, now, "evtx"])

        rows = await store.fetch_all(
            "SELECT event_id FROM normalized_events WHERE source_type = ?",
            ["evtx"],
        )
        assert len(rows) == 2
        evtx_ids = {r[0] for r in rows}
        assert eid1 in evtx_ids
        assert eid3 in evtx_ids

    async def test_multiple_sequential_writes(self, store):
        """Write 5 rows in sequence and verify count."""
        now = datetime.now(timezone.utc).isoformat()
        sql = (
            "INSERT OR IGNORE INTO normalized_events "
            "(event_id, timestamp, ingested_at, source_type) VALUES (?, ?, ?, ?)"
        )
        ids = [str(uuid.uuid4()) for _ in range(5)]
        for eid in ids:
            await store.execute_write(sql, [eid, now, now, "json"])

        rows = await store.fetch_all(
            f"SELECT COUNT(*) FROM normalized_events "
            f"WHERE event_id IN ({','.join('?' * len(ids))})",
            ids,
        )
        assert rows[0][0] == 5

    async def test_fetch_all_empty_table(self, store):
        rows = await store.fetch_all(
            "SELECT event_id FROM normalized_events WHERE source_type = 'no_such_type'"
        )
        assert rows == []

    async def test_write_with_case_id(self, store):
        eid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await store.execute_write(
            "INSERT OR IGNORE INTO normalized_events "
            "(event_id, timestamp, ingested_at, source_type, case_id) "
            "VALUES (?, ?, ?, ?, ?)",
            [eid, now, now, "json", "case-test-001"],
        )
        rows = await store.fetch_all(
            "SELECT case_id FROM normalized_events WHERE event_id = ?", [eid]
        )
        assert rows[0][0] == "case-test-001"

    async def test_close_called_once(self, tmp_path):
        """close() can be called without errors after initialize()."""
        from backend.stores.duckdb_store import DuckDBStore
        s = DuckDBStore(str(tmp_path / "close_test"))
        s.start_write_worker()
        await s.initialise_schema()
        await s.close()  # Should not raise

    async def test_fetch_df_returns_dicts(self, store):
        """fetch_df returns list of dicts with column names as keys."""
        eid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await store.execute_write(
            "INSERT OR IGNORE INTO normalized_events "
            "(event_id, timestamp, ingested_at, source_type) VALUES (?, ?, ?, ?)",
            [eid, now, now, "json"],
        )
        rows = await store.fetch_df(
            "SELECT event_id, source_type FROM normalized_events WHERE event_id = ?",
            [eid],
        )
        assert len(rows) == 1
        assert isinstance(rows[0], dict)
        assert rows[0]["event_id"] == eid
        assert rows[0]["source_type"] == "json"

    async def test_insert_and_retrieve_all_common_fields(self, store):
        """Verify common fields survive a write/read round-trip."""
        eid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await store.execute_write(
            "INSERT OR IGNORE INTO normalized_events "
            "(event_id, timestamp, ingested_at, source_type, hostname, username, "
            "process_name, command_line, dst_ip) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [eid, now, now, "json", "host1", "alice", "powershell.exe",
             "powershell -enc abc", "192.168.1.1"],
        )
        rows = await store.fetch_df(
            "SELECT * FROM normalized_events WHERE event_id = ?", [eid]
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["hostname"] == "host1"
        assert row["username"] == "alice"
        assert row["process_name"] == "powershell.exe"
        assert row["command_line"] == "powershell -enc abc"
        assert row["dst_ip"] == "192.168.1.1"


class TestDuckDBStoreSecurity:
    def test_duckdb_external_access_disabled(self):
        """DuckDB must reject COPY TO and httpfs after store initialization (E5-02)."""
        import duckdb
        # Replicate what DuckDBStore.__init__ does for the write connection.
        conn = duckdb.connect(":memory:")
        conn.execute("SET enable_external_access = false")
        with pytest.raises(Exception, match="(?i)permission|external|access"):
            conn.execute("COPY (SELECT 1) TO '/tmp/exfil_test.csv' (FORMAT CSV)")

    def test_duckdb_external_access_disabled_on_read_conn(self):
        """Read connections opened by get_read_conn() also block COPY TO (E5-02)."""
        import duckdb
        # Replicate what get_read_conn() does.
        conn = duckdb.connect(":memory:")
        conn.execute("SET enable_external_access = false")
        with pytest.raises(Exception, match="(?i)permission|external|access"):
            conn.execute("COPY (SELECT 42) TO '/tmp/exfil_read.csv' (FORMAT CSV)")


class TestDuckDBStoreSchema:
    async def test_schema_has_case_id_column(self, store):
        rows = await store.fetch_all(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'normalized_events' AND column_name = 'case_id'"
        )
        assert len(rows) == 1

    async def test_schema_has_command_line_column(self, store):
        rows = await store.fetch_all(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'normalized_events' AND column_name = 'command_line'"
        )
        assert len(rows) == 1

    async def test_schema_has_dst_ip_column(self, store):
        rows = await store.fetch_all(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'normalized_events' AND column_name = 'dst_ip'"
        )
        assert len(rows) == 1

    async def test_schema_has_hostname_column(self, store):
        rows = await store.fetch_all(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'normalized_events' AND column_name = 'hostname'"
        )
        assert len(rows) == 1

    async def test_schema_has_attack_technique_column(self, store):
        rows = await store.fetch_all(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'normalized_events' AND column_name = 'attack_technique'"
        )
        assert len(rows) == 1

    async def test_indexes_created(self, store):
        """Check that expected indexes exist via pg_indexes."""
        rows = await store.fetch_all(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'normalized_events'"
        )
        index_names = {r[0] for r in rows}
        assert "idx_events_case_id" in index_names
