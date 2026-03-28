"""
Unit tests for backend/services/metrics_service.py

Covers all 9 KPI computation functions and MetricsService.compute_all_kpis().
Uses AsyncMock for stores — no real I/O.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_stores(*, duckdb_rows=None, sqlite_rows=None):
    """Build a fake Stores container with mock DuckDB + SQLite stores."""
    if duckdb_rows is None:
        duckdb_rows = []
    if sqlite_rows is None:
        sqlite_rows = []

    duckdb_store = MagicMock()
    duckdb_store.fetch_all = AsyncMock(return_value=duckdb_rows)

    sqlite_store = MagicMock()
    # _conn.execute(...).fetchone() / .fetchall() mocks
    mock_cursor = MagicMock()
    mock_cursor.fetchone = MagicMock(return_value=sqlite_rows[0] if sqlite_rows else None)
    mock_cursor.fetchall = MagicMock(return_value=sqlite_rows)
    sqlite_store._conn = MagicMock()
    sqlite_store._conn.execute = MagicMock(return_value=mock_cursor)

    stores = MagicMock()
    stores.duckdb = duckdb_store
    stores.sqlite = sqlite_store
    return stores


# ---------------------------------------------------------------------------
# KpiValue / KpiSnapshot model tests
# ---------------------------------------------------------------------------

class TestKpiModels:
    def test_kpi_value_defaults(self):
        from backend.services.metrics_service import KpiValue
        kv = KpiValue(label="test", value=0.0)
        assert kv.unit == ""
        assert kv.trend == "flat"

    def test_kpi_snapshot_has_all_fields(self):
        from datetime import datetime, timezone

        from backend.services.metrics_service import KpiSnapshot, KpiValue
        snap = KpiSnapshot(
            computed_at=datetime.now(tz=timezone.utc),
            mttd=KpiValue(label="MTTD", value=0.0),
            mttr=KpiValue(label="MTTR", value=0.0),
            mttc=KpiValue(label="MTTC", value=0.0),
            false_positive_rate=KpiValue(label="False Positive Rate", value=0.0),
            alert_volume_24h=KpiValue(label="Alert Volume 24h", value=0.0),
            active_rules=KpiValue(label="Active Rules", value=0.0),
            open_cases=KpiValue(label="Open Cases", value=0.0),
            assets_monitored=KpiValue(label="Assets Monitored", value=0.0),
            log_sources=KpiValue(label="Log Sources", value=0.0),
        )
        assert snap.mttd.label == "MTTD"
        assert snap.mttr.label == "MTTR"
        assert snap.mttc.label == "MTTC"


# ---------------------------------------------------------------------------
# Individual compute_* function tests (empty stores)
# ---------------------------------------------------------------------------

class TestComputeMttd:
    async def test_returns_kpi_value_with_label_mttd(self):
        from backend.services.metrics_service import KpiValue, MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_mttd()
        assert isinstance(result, KpiValue)
        assert result.label == "MTTD"

    async def test_returns_zero_when_no_detections(self):
        from backend.services.metrics_service import MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_mttd()
        assert result.value == 0.0

    async def test_no_exception_on_empty_stores(self):
        from backend.services.metrics_service import MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        # Should not raise
        result = await svc.compute_mttd()
        assert result is not None


class TestComputeMttr:
    async def test_returns_kpi_value_with_label_mttr(self):
        from backend.services.metrics_service import KpiValue, MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_mttr()
        assert isinstance(result, KpiValue)
        assert result.label == "MTTR"

    async def test_returns_zero_when_no_closed_cases(self):
        from backend.services.metrics_service import MetricsService
        # sqlite returns empty list for cases query
        stores = _make_stores(sqlite_rows=[])
        svc = MetricsService(stores)
        result = await svc.compute_mttr()
        assert result.value == 0.0


class TestComputeMttc:
    async def test_returns_kpi_value_with_label_mttc(self):
        from backend.services.metrics_service import KpiValue, MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_mttc()
        assert isinstance(result, KpiValue)
        assert result.label == "MTTC"

    async def test_returns_zero_when_no_closed_cases(self):
        from backend.services.metrics_service import MetricsService
        stores = _make_stores(sqlite_rows=[])
        svc = MetricsService(stores)
        result = await svc.compute_mttc()
        assert result.value == 0.0


class TestComputeFalsePositiveRate:
    async def test_returns_kpi_value_with_correct_label(self):
        from backend.services.metrics_service import KpiValue, MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_false_positive_rate()
        assert isinstance(result, KpiValue)

    async def test_returns_value_in_range_0_to_1(self):
        from backend.services.metrics_service import MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_false_positive_rate()
        assert 0.0 <= result.value <= 1.0

    async def test_returns_zero_when_no_detections(self):
        from backend.services.metrics_service import MetricsService
        stores = _make_stores(sqlite_rows=[])
        svc = MetricsService(stores)
        result = await svc.compute_false_positive_rate()
        assert result.value == 0.0


class TestComputeAlertVolume:
    async def test_returns_kpi_value(self):
        from backend.services.metrics_service import KpiValue, MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_alert_volume()
        assert isinstance(result, KpiValue)

    async def test_returns_non_negative_integer(self):
        from backend.services.metrics_service import MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_alert_volume()
        assert result.value >= 0
        assert result.value == int(result.value)


class TestComputeActiveRules:
    async def test_returns_kpi_value(self):
        from backend.services.metrics_service import KpiValue, MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_active_rules()
        assert isinstance(result, KpiValue)

    async def test_returns_non_negative_integer(self):
        from backend.services.metrics_service import MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_active_rules()
        assert result.value >= 0
        assert result.value == int(result.value)


class TestComputeOpenCases:
    async def test_returns_kpi_value(self):
        from backend.services.metrics_service import KpiValue, MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_open_cases()
        assert isinstance(result, KpiValue)

    async def test_returns_non_negative_integer(self):
        from backend.services.metrics_service import MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        result = await svc.compute_open_cases()
        assert result.value >= 0
        assert result.value == int(result.value)


# ---------------------------------------------------------------------------
# compute_all_kpis() — full snapshot
# ---------------------------------------------------------------------------

class TestComputeAllKpis:
    async def test_returns_kpi_snapshot(self):
        from backend.services.metrics_service import KpiSnapshot, MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        snap = await svc.compute_all_kpis()
        assert isinstance(snap, KpiSnapshot)

    async def test_snapshot_has_all_9_fields(self):
        from backend.services.metrics_service import KpiValue, MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        snap = await svc.compute_all_kpis()
        assert isinstance(snap.mttd, KpiValue)
        assert isinstance(snap.mttr, KpiValue)
        assert isinstance(snap.mttc, KpiValue)
        assert isinstance(snap.false_positive_rate, KpiValue)
        assert isinstance(snap.alert_volume_24h, KpiValue)
        assert isinstance(snap.active_rules, KpiValue)
        assert isinstance(snap.open_cases, KpiValue)
        assert isinstance(snap.assets_monitored, KpiValue)
        assert isinstance(snap.log_sources, KpiValue)

    async def test_computed_at_is_set(self):
        from datetime import datetime

        from backend.services.metrics_service import MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        snap = await svc.compute_all_kpis()
        assert isinstance(snap.computed_at, datetime)

    async def test_no_exception_on_empty_stores(self):
        from backend.services.metrics_service import MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        # Should never raise, even with empty tables
        snap = await svc.compute_all_kpis()
        assert snap is not None


# ---------------------------------------------------------------------------
# Plan 14-03: LLMOps KPI fields on KpiSnapshot
# ---------------------------------------------------------------------------

class TestKpiSnapshotLlmopsFields:
    def test_kpi_snapshot_has_avg_latency_ms_per_model_field(self):
        """KpiSnapshot must include avg_latency_ms_per_model: dict[str, float]."""
        from datetime import datetime, timezone
        from backend.services.metrics_service import KpiSnapshot, KpiValue
        snap = KpiSnapshot(
            computed_at=datetime.now(tz=timezone.utc),
            mttd=KpiValue(label="MTTD", value=0.0),
            mttr=KpiValue(label="MTTR", value=0.0),
            mttc=KpiValue(label="MTTC", value=0.0),
            false_positive_rate=KpiValue(label="False Positive Rate", value=0.0),
            alert_volume_24h=KpiValue(label="Alert Volume 24h", value=0.0),
            active_rules=KpiValue(label="Active Rules", value=0.0),
            open_cases=KpiValue(label="Open Cases", value=0.0),
            assets_monitored=KpiValue(label="Assets Monitored", value=0.0),
            log_sources=KpiValue(label="Log Sources", value=0.0),
        )
        assert hasattr(snap, "avg_latency_ms_per_model")
        assert isinstance(snap.avg_latency_ms_per_model, dict)

    def test_kpi_snapshot_has_total_llm_calls_field(self):
        """KpiSnapshot must include total_llm_calls: int."""
        from datetime import datetime, timezone
        from backend.services.metrics_service import KpiSnapshot, KpiValue
        snap = KpiSnapshot(
            computed_at=datetime.now(tz=timezone.utc),
            mttd=KpiValue(label="MTTD", value=0.0),
            mttr=KpiValue(label="MTTR", value=0.0),
            mttc=KpiValue(label="MTTC", value=0.0),
            false_positive_rate=KpiValue(label="False Positive Rate", value=0.0),
            alert_volume_24h=KpiValue(label="Alert Volume 24h", value=0.0),
            active_rules=KpiValue(label="Active Rules", value=0.0),
            open_cases=KpiValue(label="Open Cases", value=0.0),
            assets_monitored=KpiValue(label="Assets Monitored", value=0.0),
            log_sources=KpiValue(label="Log Sources", value=0.0),
        )
        assert hasattr(snap, "total_llm_calls")
        assert isinstance(snap.total_llm_calls, int)

    def test_kpi_snapshot_has_error_rate_field(self):
        """KpiSnapshot must include error_rate: float."""
        from datetime import datetime, timezone
        from backend.services.metrics_service import KpiSnapshot, KpiValue
        snap = KpiSnapshot(
            computed_at=datetime.now(tz=timezone.utc),
            mttd=KpiValue(label="MTTD", value=0.0),
            mttr=KpiValue(label="MTTR", value=0.0),
            mttc=KpiValue(label="MTTC", value=0.0),
            false_positive_rate=KpiValue(label="False Positive Rate", value=0.0),
            alert_volume_24h=KpiValue(label="Alert Volume 24h", value=0.0),
            active_rules=KpiValue(label="Active Rules", value=0.0),
            open_cases=KpiValue(label="Open Cases", value=0.0),
            assets_monitored=KpiValue(label="Assets Monitored", value=0.0),
            log_sources=KpiValue(label="Log Sources", value=0.0),
        )
        assert hasattr(snap, "error_rate")
        assert isinstance(snap.error_rate, float)

    def test_kpi_snapshot_llm_fields_default_to_zero(self):
        """LLMOps fields default to empty/zero when not provided."""
        from datetime import datetime, timezone
        from backend.services.metrics_service import KpiSnapshot, KpiValue
        snap = KpiSnapshot(
            computed_at=datetime.now(tz=timezone.utc),
            mttd=KpiValue(label="MTTD", value=0.0),
            mttr=KpiValue(label="MTTR", value=0.0),
            mttc=KpiValue(label="MTTC", value=0.0),
            false_positive_rate=KpiValue(label="False Positive Rate", value=0.0),
            alert_volume_24h=KpiValue(label="Alert Volume 24h", value=0.0),
            active_rules=KpiValue(label="Active Rules", value=0.0),
            open_cases=KpiValue(label="Open Cases", value=0.0),
            assets_monitored=KpiValue(label="Assets Monitored", value=0.0),
            log_sources=KpiValue(label="Log Sources", value=0.0),
        )
        assert snap.avg_latency_ms_per_model == {}
        assert snap.total_llm_calls == 0
        assert snap.error_rate == 0.0

    async def test_compute_all_kpis_includes_llm_fields(self):
        """compute_all_kpis() returns snapshot with avg_latency_ms_per_model, total_llm_calls, error_rate."""
        from backend.services.metrics_service import MetricsService
        stores = _make_stores()
        svc = MetricsService(stores)
        snap = await svc.compute_all_kpis()
        assert hasattr(snap, "avg_latency_ms_per_model")
        assert hasattr(snap, "total_llm_calls")
        assert hasattr(snap, "error_rate")
        assert isinstance(snap.avg_latency_ms_per_model, dict)
        assert isinstance(snap.total_llm_calls, int)
        assert isinstance(snap.error_rate, float)

    async def test_compute_llm_kpis_returns_defaults_on_empty(self):
        """_compute_llm_kpis() returns empty dict, 0, 0.0 when no rows."""
        from backend.services.metrics_service import _compute_llm_kpis
        mock_store = MagicMock()
        mock_store.fetch_all = AsyncMock(return_value=[])
        avg, total, err = await _compute_llm_kpis(mock_store)
        assert avg == {}
        assert total == 0
        assert err == 0.0

    async def test_compute_llm_kpis_aggregates_rows(self):
        """_compute_llm_kpis() correctly aggregates model rows."""
        from backend.services.metrics_service import _compute_llm_kpis
        mock_store = MagicMock()
        # rows: (model, avg_latency, total, errors)
        mock_store.fetch_all = AsyncMock(return_value=[
            ("qwen3:14b", 250.0, 10, 1),
            ("foundation-sec:8b", 500.0, 5, 0),
        ])
        avg, total, err = await _compute_llm_kpis(mock_store)
        assert "qwen3:14b" in avg
        assert avg["qwen3:14b"] == 250.0
        assert total == 15
        assert round(err, 4) == round(1 / 15, 4)
