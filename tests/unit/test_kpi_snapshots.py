"""
Unit tests for daily_kpi_snapshots DuckDB table and upsert method.

TDD: tests for the DDL constant and upsert_daily_kpi_snapshot() method.
"""
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


class TestKpiSnapshots:
    async def test_schema_created(self, store):
        """After initialise_schema(), SELECT on daily_kpi_snapshots returns empty list."""
        rows = await store.fetch_all("SELECT * FROM daily_kpi_snapshots")
        assert rows == [], f"Expected empty table, got {rows}"

    async def test_upsert_insert(self, store):
        """Upsert a row, fetch it back, verify mttd_minutes matches."""
        await store.upsert_daily_kpi_snapshot(
            snapshot_date="2026-01-15",
            mttd_minutes=12.5,
            mttr_minutes=30.0,
            mttc_minutes=45.0,
            alert_volume=100,
            false_positive_count=10,
            investigation_count=5,
            detection_count=20,
        )
        rows = await store.fetch_all(
            "SELECT snapshot_date, mttd_minutes FROM daily_kpi_snapshots"
        )
        assert len(rows) == 1, f"Expected 1 row, got {len(rows)}: {rows}"
        assert float(rows[0][1]) == pytest.approx(12.5), (
            f"Expected mttd_minutes=12.5, got {rows[0][1]}"
        )

    async def test_upsert_replace(self, store):
        """Upsert same date twice with different mttd — only one row, second value wins."""
        await store.upsert_daily_kpi_snapshot(
            snapshot_date="2026-02-01",
            mttd_minutes=5.0,
            mttr_minutes=10.0,
            mttc_minutes=15.0,
            alert_volume=50,
            false_positive_count=3,
            investigation_count=2,
            detection_count=8,
        )
        # Second upsert with updated mttd
        await store.upsert_daily_kpi_snapshot(
            snapshot_date="2026-02-01",
            mttd_minutes=99.9,
            mttr_minutes=10.0,
            mttc_minutes=15.0,
            alert_volume=50,
            false_positive_count=3,
            investigation_count=2,
            detection_count=8,
        )
        rows = await store.fetch_all(
            "SELECT snapshot_date, mttd_minutes FROM daily_kpi_snapshots "
            "WHERE snapshot_date = '2026-02-01'"
        )
        assert len(rows) == 1, f"Expected 1 row after upsert, got {len(rows)}: {rows}"
        assert float(rows[0][1]) == pytest.approx(99.9), (
            f"Expected mttd_minutes=99.9, got {rows[0][1]}"
        )
