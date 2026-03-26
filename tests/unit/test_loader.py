"""Unit tests for ingestion/loader.py — batch logic with mocked stores."""
import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

pytestmark = pytest.mark.unit


async def _make_stores(tmp_path):
    """Build a Stores object with a real DuckDB + mock Chroma/SQLite."""
    from backend.core.deps import Stores
    from backend.stores.duckdb_store import DuckDBStore

    duckdb_store = DuckDBStore(str(tmp_path / "duckdb"))
    duckdb_store.start_write_worker()
    await duckdb_store.initialise_schema()

    chroma_store = MagicMock()
    chroma_store.upsert_events = AsyncMock(return_value=None)

    sqlite_store = MagicMock()
    sqlite_store.insert_entity = MagicMock(return_value=None)
    sqlite_store.insert_edge = MagicMock(return_value=None)

    return Stores(duckdb=duckdb_store, chroma=chroma_store, sqlite=sqlite_store)


def _make_ollama():
    client = MagicMock()
    client.embed = AsyncMock(return_value=[0.1] * 1024)
    return client


class TestIngestionLoader:
    async def test_ingest_csv_file(self, tmp_path):
        csv_file = tmp_path / "events.csv"
        csv_file.write_text(
            "timestamp,hostname,process_name\n"
            "2026-01-01T00:00:00,host1,cmd.exe\n"
            "2026-01-01T00:01:00,host2,powershell.exe\n"
        )
        from ingestion.loader import IngestionLoader
        stores = await _make_stores(tmp_path)
        ollama = _make_ollama()
        loader = IngestionLoader(stores, ollama)
        result = await loader.ingest_file(str(csv_file), case_id="case-001")
        assert result is not None
        # IngestionResult has a loaded attribute
        assert hasattr(result, "loaded")
        assert result.loaded >= 0

    async def test_ingest_deduplicates_on_reingest(self, tmp_path):
        csv_file = tmp_path / "events.csv"
        csv_file.write_text(
            "timestamp,hostname\n"
            "2026-01-01T00:00:00,host1\n"
        )
        from ingestion.loader import IngestionLoader
        stores = await _make_stores(tmp_path)
        ollama = _make_ollama()
        loader = IngestionLoader(stores, ollama)
        await loader.ingest_file(str(csv_file), case_id="case-001")
        await loader.ingest_file(str(csv_file), case_id="case-001")
        rows = await stores.duckdb.fetch_all(
            "SELECT COUNT(*) AS cnt FROM normalized_events"
        )
        # fetch_all returns tuples; first column is count
        assert rows[0][0] == 1

    async def test_ingest_nonexistent_file_returns_error(self, tmp_path):
        """IngestionLoader returns IngestionResult with errors for missing files."""
        from ingestion.loader import IngestionLoader
        stores = await _make_stores(tmp_path)
        ollama = _make_ollama()
        loader = IngestionLoader(stores, ollama)
        result = await loader.ingest_file(
            str(tmp_path / "does_not_exist.csv"), case_id="case-001"
        )
        # Should return an IngestionResult with errors populated
        assert result is not None
        assert len(result.errors) > 0
