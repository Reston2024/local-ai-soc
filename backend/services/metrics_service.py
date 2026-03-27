"""
SOC KPI computation service.

Provides MetricsService with 9 KPI computation methods and a
compute_all_kpis() aggregator that runs them concurrently.

All functions catch exceptions broadly and return zero values rather than
raising — metrics must never crash the endpoint.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.core.deps import Stores

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class KpiValue(BaseModel):
    label: str
    value: float
    unit: str = ""        # e.g. "min", "%", "count"
    trend: str = "flat"   # "up" | "down" | "flat"


class KpiSnapshot(BaseModel):
    computed_at: datetime
    mttd: KpiValue                # Mean Time to Detect (minutes)
    mttr: KpiValue                # Mean Time to Respond (minutes)
    mttc: KpiValue                # Mean Time to Contain (minutes)
    false_positive_rate: KpiValue # ratio 0–1
    alert_volume_24h: KpiValue    # count of detections in last 24h
    active_rules: KpiValue        # count of sigma rules that have fired
    open_cases: KpiValue          # count of cases with status='active'
    assets_monitored: KpiValue    # count of distinct non-null hostnames
    log_sources: KpiValue         # count of distinct non-null source_type values


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _zero(label: str, unit: str = "") -> KpiValue:
    """Return a zero KpiValue for graceful fallback."""
    return KpiValue(label=label, value=0.0, unit=unit, trend="flat")


def _sqlite_fetchone(conn, sql: str, params: tuple = ()) -> object:
    """Execute a SQLite query synchronously and return the first row."""
    return conn.execute(sql, params).fetchone()


def _sqlite_fetchall(conn, sql: str, params: tuple = ()) -> list:
    """Execute a SQLite query synchronously and return all rows."""
    return conn.execute(sql, params).fetchall()


# ---------------------------------------------------------------------------
# MetricsService
# ---------------------------------------------------------------------------


class MetricsService:
    """
    Compute SOC KPIs from DuckDB (events) and SQLite (detections/cases).

    Instantiate with a Stores container::

        svc = MetricsService(stores)
        snapshot = await svc.compute_all_kpis()
    """

    def __init__(self, stores: "Stores") -> None:
        self._stores = stores

    # ------------------------------------------------------------------
    # MTTD — Mean Time to Detect
    # ------------------------------------------------------------------

    async def compute_mttd(self) -> KpiValue:
        """
        MTTD = avg(detection.created_at - min(event.timestamp)) per detection.

        Proxy: query the earliest event timestamp from normalized_events and
        the earliest detection created_at, then compute the gap in minutes.
        Returns 0.0 if there are no detections.
        """
        try:
            conn = self._stores.sqlite._conn

            # Fetch oldest detection created_at
            row = await asyncio.to_thread(
                _sqlite_fetchone,
                conn,
                "SELECT MIN(created_at) FROM detections",
            )
            if not row or row[0] is None:
                return _zero("MTTD", "min")

            # Fetch oldest event timestamp from DuckDB
            event_rows = await self._stores.duckdb.fetch_all(
                "SELECT MIN(timestamp) AS min_ts FROM normalized_events"
            )
            if not event_rows or event_rows[0][0] is None:
                return _zero("MTTD", "min")

            oldest_event = event_rows[0][0]
            oldest_detection_str = row[0]

            # Parse detection timestamp (ISO string from SQLite)
            if isinstance(oldest_detection_str, str):
                # Remove trailing Z if present for fromisoformat compat
                oldest_detection_str = oldest_detection_str.replace("Z", "+00:00")
                oldest_detection = datetime.fromisoformat(oldest_detection_str)
            else:
                oldest_detection = oldest_detection_str

            # Ensure timezone-aware
            if oldest_detection.tzinfo is None:
                oldest_detection = oldest_detection.replace(tzinfo=timezone.utc)

            if isinstance(oldest_event, str):
                oldest_event = oldest_event.replace("Z", "+00:00")
                oldest_event_dt = datetime.fromisoformat(oldest_event)
            else:
                oldest_event_dt = oldest_event

            if oldest_event_dt.tzinfo is None:
                oldest_event_dt = oldest_event_dt.replace(tzinfo=timezone.utc)

            diff_minutes = max(0.0, (oldest_detection - oldest_event_dt).total_seconds() / 60.0)
            return KpiValue(label="MTTD", value=round(diff_minutes, 2), unit="min")

        except Exception as exc:
            log.warning("compute_mttd failed: %s", exc)
            return _zero("MTTD", "min")

    # ------------------------------------------------------------------
    # MTTR — Mean Time to Respond
    # ------------------------------------------------------------------

    async def compute_mttr(self) -> KpiValue:
        """
        MTTR = avg(case updated_at - case created_at) for closed cases (minutes).

        SQLite cases table: id, name, status, created_at.
        Returns 0.0 if no closed cases exist.
        """
        try:
            conn = self._stores.sqlite._conn
            rows = await asyncio.to_thread(
                _sqlite_fetchall,
                conn,
                "SELECT created_at FROM cases WHERE status != 'active'",
            )
            if not rows:
                return _zero("MTTR", "min")

            # Use a rough proxy: avg time from created_at to now for closed cases
            now = datetime.now(tz=timezone.utc)
            total_minutes = 0.0
            count = 0
            for row in rows:
                created_str = row[0] if row[0] else None
                if not created_str:
                    continue
                created_str = str(created_str).replace("Z", "+00:00")
                created_dt = datetime.fromisoformat(created_str)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                diff = (now - created_dt).total_seconds() / 60.0
                total_minutes += max(0.0, diff)
                count += 1

            if count == 0:
                return _zero("MTTR", "min")

            avg = round(total_minutes / count, 2)
            return KpiValue(label="MTTR", value=avg, unit="min")

        except Exception as exc:
            log.warning("compute_mttr failed: %s", exc)
            return _zero("MTTR", "min")

    # ------------------------------------------------------------------
    # MTTC — Mean Time to Contain
    # ------------------------------------------------------------------

    async def compute_mttc(self) -> KpiValue:
        """
        MTTC = avg(case closed_at - case created_at) for all closed cases.

        Proxy: same calculation as MTTR (cases table has no explicit closed_at
        column yet — reuse the created_at → now delta for closed cases).
        Returns 0.0 if no closed cases.
        """
        try:
            conn = self._stores.sqlite._conn
            rows = await asyncio.to_thread(
                _sqlite_fetchall,
                conn,
                "SELECT created_at FROM cases WHERE status = 'closed'",
            )
            if not rows:
                return _zero("MTTC", "min")

            now = datetime.now(tz=timezone.utc)
            total_minutes = 0.0
            count = 0
            for row in rows:
                created_str = row[0] if row[0] else None
                if not created_str:
                    continue
                created_str = str(created_str).replace("Z", "+00:00")
                created_dt = datetime.fromisoformat(created_str)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                diff = (now - created_dt).total_seconds() / 60.0
                total_minutes += max(0.0, diff)
                count += 1

            if count == 0:
                return _zero("MTTC", "min")

            avg = round(total_minutes / count, 2)
            return KpiValue(label="MTTC", value=avg, unit="min")

        except Exception as exc:
            log.warning("compute_mttc failed: %s", exc)
            return _zero("MTTC", "min")

    # ------------------------------------------------------------------
    # False Positive Rate
    # ------------------------------------------------------------------

    async def compute_false_positive_rate(self) -> KpiValue:
        """
        FP rate = count(detections with severity='low' and case_id IS NULL)
                  / count(all detections).

        Proxy metric — true FP tracking requires analyst feedback.
        Returns 0.0 if no detections exist.
        """
        try:
            conn = self._stores.sqlite._conn

            total_row = await asyncio.to_thread(
                _sqlite_fetchone,
                conn,
                "SELECT COUNT(*) FROM detections",
            )
            total = total_row[0] if total_row else 0
            if not total:
                return _zero("False Positive Rate", "%")

            fp_row = await asyncio.to_thread(
                _sqlite_fetchone,
                conn,
                "SELECT COUNT(*) FROM detections WHERE severity = 'low' AND case_id IS NULL",
            )
            fp_count = fp_row[0] if fp_row else 0

            rate = round(fp_count / total, 4)
            return KpiValue(label="False Positive Rate", value=rate, unit="%")

        except Exception as exc:
            log.warning("compute_false_positive_rate failed: %s", exc)
            return _zero("False Positive Rate", "%")

    # ------------------------------------------------------------------
    # Alert Volume 24h
    # ------------------------------------------------------------------

    async def compute_alert_volume(self) -> KpiValue:
        """Count of detections with created_at >= NOW() - 24h from SQLite."""
        try:
            conn = self._stores.sqlite._conn
            row = await asyncio.to_thread(
                _sqlite_fetchone,
                conn,
                "SELECT COUNT(*) FROM detections "
                "WHERE datetime(created_at) >= datetime('now', '-24 hours')",
            )
            count = int(row[0]) if row and row[0] is not None else 0
            return KpiValue(label="Alert Volume 24h", value=float(count), unit="count")

        except Exception as exc:
            log.warning("compute_alert_volume failed: %s", exc)
            return _zero("Alert Volume 24h", "count")

    # ------------------------------------------------------------------
    # Active Rules
    # ------------------------------------------------------------------

    async def compute_active_rules(self) -> KpiValue:
        """Count of distinct rule_ids in the detections table (rules that have fired)."""
        try:
            conn = self._stores.sqlite._conn
            row = await asyncio.to_thread(
                _sqlite_fetchone,
                conn,
                "SELECT COUNT(DISTINCT rule_id) FROM detections WHERE rule_id IS NOT NULL",
            )
            count = int(row[0]) if row and row[0] is not None else 0
            return KpiValue(label="Active Rules", value=float(count), unit="count")

        except Exception as exc:
            log.warning("compute_active_rules failed: %s", exc)
            return _zero("Active Rules", "count")

    # ------------------------------------------------------------------
    # Open Cases
    # ------------------------------------------------------------------

    async def compute_open_cases(self) -> KpiValue:
        """Count of cases with status='active' from SQLite."""
        try:
            conn = self._stores.sqlite._conn
            row = await asyncio.to_thread(
                _sqlite_fetchone,
                conn,
                "SELECT COUNT(*) FROM cases WHERE status = 'active'",
            )
            count = int(row[0]) if row and row[0] is not None else 0
            return KpiValue(label="Open Cases", value=float(count), unit="count")

        except Exception as exc:
            log.warning("compute_open_cases failed: %s", exc)
            return _zero("Open Cases", "count")

    # ------------------------------------------------------------------
    # Assets Monitored
    # ------------------------------------------------------------------

    async def compute_assets_monitored(self) -> KpiValue:
        """Count of distinct non-null hostnames from DuckDB normalized_events."""
        try:
            rows = await self._stores.duckdb.fetch_all(
                "SELECT COUNT(DISTINCT hostname) AS cnt "
                "FROM normalized_events WHERE hostname IS NOT NULL"
            )
            count = int(rows[0][0]) if rows and rows[0][0] is not None else 0
            return KpiValue(label="Assets Monitored", value=float(count), unit="count")

        except Exception as exc:
            log.warning("compute_assets_monitored failed: %s", exc)
            return _zero("Assets Monitored", "count")

    # ------------------------------------------------------------------
    # Log Sources
    # ------------------------------------------------------------------

    async def compute_log_sources(self) -> KpiValue:
        """Count of distinct non-null source_type values from DuckDB normalized_events."""
        try:
            rows = await self._stores.duckdb.fetch_all(
                "SELECT COUNT(DISTINCT source_type) AS cnt "
                "FROM normalized_events WHERE source_type IS NOT NULL"
            )
            count = int(rows[0][0]) if rows and rows[0][0] is not None else 0
            return KpiValue(label="Log Sources", value=float(count), unit="count")

        except Exception as exc:
            log.warning("compute_log_sources failed: %s", exc)
            return _zero("Log Sources", "count")

    # ------------------------------------------------------------------
    # Aggregate: compute_all_kpis
    # ------------------------------------------------------------------

    async def compute_all_kpis(self) -> KpiSnapshot:
        """
        Run all compute_* coroutines concurrently via asyncio.gather.

        Returns a KpiSnapshot with all 9 KPI fields populated.
        Never raises — all individual functions have their own exception guards.
        """
        (
            mttd,
            mttr,
            mttc,
            fpr,
            alert_vol,
            active_rules,
            open_cases,
            assets,
            log_srcs,
        ) = await asyncio.gather(
            self.compute_mttd(),
            self.compute_mttr(),
            self.compute_mttc(),
            self.compute_false_positive_rate(),
            self.compute_alert_volume(),
            self.compute_active_rules(),
            self.compute_open_cases(),
            self.compute_assets_monitored(),
            self.compute_log_sources(),
        )

        return KpiSnapshot(
            computed_at=datetime.now(tz=timezone.utc),
            mttd=mttd,
            mttr=mttr,
            mttc=mttc,
            false_positive_rate=fpr,
            alert_volume_24h=alert_vol,
            active_rules=active_rules,
            open_cases=open_cases,
            assets_monitored=assets,
            log_sources=log_srcs,
        )
