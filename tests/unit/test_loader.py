"""Unit tests for ingestion/loader.py — batch logic with mocked stores."""
from datetime import datetime, timezone
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
    chroma_store.add_documents_async = AsyncMock(return_value=None)

    sqlite_store = MagicMock()
    sqlite_store.upsert_entity = MagicMock(return_value=None)
    sqlite_store.insert_edge = MagicMock(return_value=None)

    return Stores(duckdb=duckdb_store, chroma=chroma_store, sqlite=sqlite_store)


def _make_ollama():
    client = MagicMock()
    client.embed = AsyncMock(return_value=[0.1] * 1024)
    client.embed_batch = AsyncMock(return_value=[[0.1] * 1024])
    return client


def _make_event(event_id: str | None = None, hostname: str = "host1") -> "NormalizedEvent":  # noqa: F821
    from backend.models.event import NormalizedEvent
    now = datetime.now(timezone.utc)
    return NormalizedEvent(
        event_id=event_id or f"evt-{hostname}",
        timestamp=now,
        ingested_at=now,
        source_type="csv",
        hostname=hostname,
        case_id="case-001",
    )


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

    async def test_ingest_deduplicates_same_event_id(self, tmp_path):
        """ingest_events deduplicates events with the same event_id."""
        from backend.models.event import NormalizedEvent
        from ingestion.loader import IngestionLoader
        stores = await _make_stores(tmp_path)
        ollama = _make_ollama()
        loader = IngestionLoader(stores, ollama)
        now = datetime.now(timezone.utc)
        event = NormalizedEvent(
            event_id="dedup-evt-001",
            timestamp=now,
            ingested_at=now,
            source_type="csv",
            hostname="host1",
            case_id="case-001",
        )
        # Ingest the same event twice
        await loader.ingest_events([event])
        await loader.ingest_events([event])
        rows = await stores.duckdb.fetch_all(
            "SELECT COUNT(*) FROM normalized_events WHERE event_id = 'dedup-evt-001'"
        )
        # Should only be stored once despite two ingest calls
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

    async def test_result_has_loaded_count(self, tmp_path):
        csv_file = tmp_path / "events.csv"
        csv_file.write_text(
            "timestamp,hostname\n"
            "2026-01-01T00:00:00,host1\n"
            "2026-01-01T00:01:00,host2\n"
            "2026-01-01T00:02:00,host3\n"
        )
        from ingestion.loader import IngestionLoader
        stores = await _make_stores(tmp_path)
        loader = IngestionLoader(stores, _make_ollama())
        result = await loader.ingest_file(str(csv_file), case_id="case-001")
        assert result.loaded == 3

    async def test_ingest_events_empty_list(self, tmp_path):
        """ingest_events with an empty list returns a result with 0 loaded."""
        from ingestion.loader import IngestionLoader
        stores = await _make_stores(tmp_path)
        loader = IngestionLoader(stores, _make_ollama())
        result = await loader.ingest_events([])
        assert result.loaded == 0

    async def test_ingest_events_single_event(self, tmp_path):
        """ingest_events with one new event loads it."""
        from ingestion.loader import IngestionLoader
        stores = await _make_stores(tmp_path)
        loader = IngestionLoader(stores, _make_ollama())
        event = _make_event("single-evt-001")
        result = await loader.ingest_events([event])
        assert result.loaded == 1

    async def test_ingest_file_returns_ingestion_result(self, tmp_path):
        """ingest_file returns an IngestionResult dataclass."""
        from ingestion.loader import IngestionLoader, IngestionResult
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("timestamp,hostname\n2026-01-01T00:00:00,host1\n")
        stores = await _make_stores(tmp_path)
        loader = IngestionLoader(stores, _make_ollama())
        result = await loader.ingest_file(str(csv_file), case_id="case-001")
        assert isinstance(result, IngestionResult)

    async def test_ingest_file_with_job_id(self, tmp_path):
        """ingest_file with job_id stores job status."""
        from ingestion.loader import IngestionLoader, get_job_status
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("timestamp,hostname\n2026-01-01T00:00:00,host1\n")
        stores = await _make_stores(tmp_path)
        loader = IngestionLoader(stores, _make_ollama())
        await loader.ingest_file(str(csv_file), case_id="case-001", job_id="job-test-001")
        status = get_job_status("job-test-001")
        assert status is not None
        assert status["job_id"] == "job-test-001"

    async def test_ingest_result_has_parsed_count(self, tmp_path):
        """IngestionResult.parsed counts how many events the parser produced."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "timestamp,hostname\n"
            "2026-01-01T00:00:00,host1\n"
            "2026-01-01T00:01:00,host2\n"
        )
        from ingestion.loader import IngestionLoader
        stores = await _make_stores(tmp_path)
        loader = IngestionLoader(stores, _make_ollama())
        result = await loader.ingest_file(str(csv_file), case_id="case-001")
        assert result.parsed == 2

    async def test_ingest_result_str_representation(self, tmp_path):
        """IngestionResult has a useful __str__."""
        from ingestion.loader import IngestionResult
        r = IngestionResult(file_path="/test/file.csv", loaded=5, parsed=5)
        s = str(r)
        assert "file.csv" in s
        assert "loaded=5" in s

    async def test_ingest_multiple_events_stored(self, tmp_path):
        """Ingesting multiple events stores them all in DuckDB."""
        from ingestion.loader import IngestionLoader
        stores = await _make_stores(tmp_path)
        loader = IngestionLoader(stores, _make_ollama())
        events = [_make_event(f"multi-evt-{i}", f"host{i}") for i in range(5)]
        result = await loader.ingest_events(events)
        assert result.loaded == 5

        total = await stores.duckdb.fetch_all(
            "SELECT COUNT(*) FROM normalized_events "
            "WHERE event_id LIKE 'multi-evt-%'"
        )
        assert total[0][0] == 5
