"""
DuckDB store — single-writer pattern via asyncio.Queue.

Architecture notes:
- A single write connection is opened at startup; all DDL and DML goes
  through the write_worker() background task via the write queue.
- Read queries use separate read_only connections obtained on demand.
  DuckDB supports multiple concurrent readers on the same database file
  when at least one connection is open.
- All blocking DuckDB calls in async code must be wrapped in
  asyncio.to_thread() to avoid blocking the event loop.

Schema aligns with the NormalizedEvent model in backend/models/event.py.
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import duckdb

from backend.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS normalized_events (
    event_id            TEXT PRIMARY KEY,
    timestamp           TIMESTAMP NOT NULL,
    ingested_at         TIMESTAMP NOT NULL,
    source_type         TEXT,
    source_file         TEXT,
    hostname            TEXT,
    username            TEXT,
    process_name        TEXT,
    process_id          INTEGER,
    parent_process_name TEXT,
    parent_process_id   INTEGER,
    file_path           TEXT,
    file_hash_sha256    TEXT,
    command_line        TEXT,
    src_ip              TEXT,
    src_port            INTEGER,
    dst_ip              TEXT,
    dst_port            INTEGER,
    domain              TEXT,
    url                 TEXT,
    event_type          TEXT,
    severity            TEXT,
    confidence          FLOAT,
    detection_source    TEXT,
    attack_technique    TEXT,
    attack_tactic       TEXT,
    raw_event           TEXT,
    tags                TEXT,
    case_id             TEXT,
    ocsf_class_uid      INTEGER,
    event_outcome       TEXT,
    user_domain         TEXT,
    process_executable  TEXT,
    network_protocol    TEXT,
    network_direction   TEXT
)
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON normalized_events (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_events_hostname  ON normalized_events (hostname)",
    "CREATE INDEX IF NOT EXISTS idx_events_process   ON normalized_events (process_name)",
    "CREATE INDEX IF NOT EXISTS idx_events_case_id   ON normalized_events (case_id)",
]

_CREATE_LLM_CALLS_TABLE = """
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id          TEXT PRIMARY KEY,
    called_at        TIMESTAMP NOT NULL,
    model            TEXT NOT NULL,
    endpoint         TEXT NOT NULL,
    prompt_chars     INTEGER,
    completion_chars INTEGER,
    latency_ms       INTEGER,
    success          BOOLEAN NOT NULL DEFAULT TRUE,
    error_type       TEXT,
    prompt_text      TEXT,
    prompt_hash      TEXT
)
"""

_CREATE_LLM_CALLS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_llm_calls_model ON llm_calls (model)",
    "CREATE INDEX IF NOT EXISTS idx_llm_calls_at    ON llm_calls (called_at)",
]

_CREATE_KPI_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_kpi_snapshots (
    snapshot_date        DATE PRIMARY KEY,
    mttd_minutes         FLOAT,
    mttr_minutes         FLOAT,
    mttc_minutes         FLOAT,
    alert_volume         INTEGER,
    false_positive_count INTEGER,
    investigation_count  INTEGER,
    detection_count      INTEGER,
    computed_at          TIMESTAMP NOT NULL
)
"""

_CREATE_DB_META_TABLE = """
CREATE TABLE IF NOT EXISTS db_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

_INSERT_SCHEMA_VERSION = """
INSERT INTO db_meta (key, value)
VALUES ('schema_version', '20')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
"""

# One entry per ALTER TABLE statement — DuckDB allows only one column per statement.
# DuckDB does NOT support ADD COLUMN IF NOT EXISTS; idempotency is via try/except.
_ECS_MIGRATION_COLUMNS: list[tuple[str, str]] = [
    ("ocsf_class_uid",     "INTEGER"),
    ("event_outcome",      "TEXT"),
    ("user_domain",        "TEXT"),
    ("process_executable", "TEXT"),
    ("network_protocol",   "TEXT"),
    ("network_direction",  "TEXT"),
]


# ---------------------------------------------------------------------------
# Write-queue item
# ---------------------------------------------------------------------------


@dataclass
class _WriteOp:
    """A single SQL write operation plus a Future to signal completion."""

    sql: str
    params: Optional[list[Any]] = field(default=None)
    future: asyncio.Future = field(default_factory=asyncio.Future)


# ---------------------------------------------------------------------------
# DuckDB store
# ---------------------------------------------------------------------------


class DuckDBStore:
    """
    Manages a single DuckDB database file with:
    - One write connection serialised through an asyncio.Queue
    - On-demand read-only connections for query handlers
    """

    def __init__(self, data_dir: str) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = str(self._data_dir / "events.duckdb")

        # Write connection — opened once, never closed until shutdown.
        # DuckDB is not thread-safe; all write operations must run on the
        # write_worker thread via asyncio.to_thread.
        self._write_conn: duckdb.DuckDBPyConnection = duckdb.connect(self._db_path)
        self._write_queue: asyncio.Queue[_WriteOp] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

        log.info("DuckDB store initialised", db_path=self._db_path)

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------

    async def initialise_schema(self) -> None:
        """Create tables and indexes if they do not exist."""
        await self.execute_write(_CREATE_EVENTS_TABLE)
        for idx_sql in _CREATE_INDEXES:
            await self.execute_write(idx_sql)
        await self.execute_write(_CREATE_LLM_CALLS_TABLE)
        for idx_sql in _CREATE_LLM_CALLS_INDEXES:
            await self.execute_write(idx_sql)
        await self.execute_write(_CREATE_KPI_SNAPSHOTS_TABLE)
        # ECS schema migration (Phase 20) — additive, idempotent
        await self.execute_write(_CREATE_DB_META_TABLE)
        await self.execute_write(_INSERT_SCHEMA_VERSION)
        for col_name, col_type in _ECS_MIGRATION_COLUMNS:
            try:
                await self.execute_write(
                    f"ALTER TABLE normalized_events ADD COLUMN {col_name} {col_type}"
                )
            except Exception:
                # DuckDB raises if column already exists (no IF NOT EXISTS support)
                log.debug("ECS column already exists — skipping", column=col_name)
        # E7-02 migration: add prompt_text and prompt_hash columns to llm_calls
        for col_name, col_type in [("prompt_text", "TEXT"), ("prompt_hash", "TEXT")]:
            try:
                await self.execute_write(
                    f"ALTER TABLE llm_calls ADD COLUMN {col_name} {col_type}"
                )
            except Exception:
                log.debug("llm_calls column already exists — skipping", column=col_name)
        log.info("DuckDB schema initialised")

    # ------------------------------------------------------------------
    # Write worker
    # ------------------------------------------------------------------

    async def write_worker(self) -> None:
        """
        Background task that drains the write queue.

        Runs forever until cancelled (typically at application shutdown).
        Each operation is executed on a thread to avoid blocking the event
        loop.  The result (or exception) is forwarded to the caller's Future.
        """
        log.info("DuckDB write worker started")
        while True:
            op: _WriteOp = await self._write_queue.get()
            try:
                result = await asyncio.to_thread(self._execute_sync, op.sql, op.params)
                if not op.future.done():
                    op.future.set_result(result)
            except Exception as exc:
                log.error(
                    "DuckDB write error",
                    sql=op.sql[:120],
                    error=str(exc),
                )
                if not op.future.done():
                    op.future.set_exception(exc)
            finally:
                self._write_queue.task_done()

    def _execute_sync(
        self, sql: str, params: Optional[list[Any]] = None
    ) -> duckdb.DuckDBPyRelation:
        """Execute SQL synchronously on the write connection (called from thread)."""
        if params:
            return self._write_conn.execute(sql, params)
        return self._write_conn.execute(sql)

    def start_write_worker(self) -> asyncio.Task:  # type: ignore[type-arg]
        """Schedule the write worker as an asyncio background task."""
        self._worker_task = asyncio.create_task(self.write_worker(), name="duckdb-write-worker")
        return self._worker_task

    # ------------------------------------------------------------------
    # Public write interface
    # ------------------------------------------------------------------

    async def execute_write(
        self, sql: str, params: Optional[list[Any]] = None
    ) -> None:
        """
        Enqueue a write operation and await its completion.

        This is the *only* way callers should issue DDL or DML against
        the write connection.

        Args:
            sql:    SQL statement (DDL or DML).
            params: Optional list of positional parameters.
        """
        loop = asyncio.get_running_loop()
        op = _WriteOp(sql=sql, params=params, future=loop.create_future())
        await self._write_queue.put(op)
        await op.future  # Wait until the worker has processed this op.

    # ------------------------------------------------------------------
    # Read interface
    # ------------------------------------------------------------------

    def get_read_conn(self) -> duckdb.DuckDBPyConnection:
        """
        Open and return a secondary read connection to the database file.

        DuckDB 1.5+ requires all connections to the same file to use the same
        configuration (read_only flag must match).  Since the write connection
        uses the default read_write mode, secondary connections must also omit
        read_only=True.  DuckDB serialises concurrent access automatically.

        Callers must close the connection when done, e.g.::

            conn = store.get_read_conn()
            try:
                result = await asyncio.to_thread(conn.execute, sql)
            finally:
                conn.close()
        """
        return duckdb.connect(self._db_path)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    async def fetch_all(
        self,
        sql: str,
        params: Optional[list[Any]] = None,
    ) -> list[tuple]:
        """
        Execute a SELECT on a fresh read-only connection and return all rows.

        The DuckDB call is offloaded to a thread pool thread.
        """
        def _run() -> list[tuple]:
            conn = self.get_read_conn()
            try:
                if params:
                    rel = conn.execute(sql, params)
                else:
                    rel = conn.execute(sql)
                return rel.fetchall()
            finally:
                conn.close()

        return await asyncio.to_thread(_run)

    async def fetch_df(self, sql: str, params: Optional[list[Any]] = None):
        """
        Execute a SELECT and return a pandas/polars-compatible record list.

        Returns a list of dicts keyed by column name.
        """
        def _run() -> list[dict]:
            conn = self.get_read_conn()
            try:
                if params:
                    rel = conn.execute(sql, params)
                else:
                    rel = conn.execute(sql)
                cols = [desc[0] for desc in rel.description]
                rows = rel.fetchall()
                return [dict(zip(cols, row)) for row in rows]
            finally:
                conn.close()

        return await asyncio.to_thread(_run)

    # ------------------------------------------------------------------
    # KPI snapshot upsert
    # ------------------------------------------------------------------

    async def upsert_daily_kpi_snapshot(
        self,
        snapshot_date: str,
        mttd_minutes: float,
        mttr_minutes: float,
        mttc_minutes: float,
        alert_volume: int,
        false_positive_count: int,
        investigation_count: int,
        detection_count: int,
    ) -> None:
        """Upsert the daily KPI snapshot row for snapshot_date.

        Uses DuckDB's INSERT INTO ... ON CONFLICT (snapshot_date) DO UPDATE SET
        syntax (not INSERT OR REPLACE, which DuckDB does not support).

        Args:
            snapshot_date:        ISO date string "YYYY-MM-DD".
            mttd_minutes:         Mean Time to Detect (minutes).
            mttr_minutes:         Mean Time to Respond (minutes).
            mttc_minutes:         Mean Time to Contain (minutes).
            alert_volume:         Number of detections in the snapshot period.
            false_positive_count: Estimated false positive count.
            investigation_count:  Total investigation cases.
            detection_count:      Total detection records.
        """
        from datetime import datetime, timezone
        computed_at = datetime.now(timezone.utc).isoformat()
        await self.execute_write(
            """
            INSERT INTO daily_kpi_snapshots
              (snapshot_date, mttd_minutes, mttr_minutes, mttc_minutes,
               alert_volume, false_positive_count, investigation_count,
               detection_count, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (snapshot_date) DO UPDATE SET
                mttd_minutes         = EXCLUDED.mttd_minutes,
                mttr_minutes         = EXCLUDED.mttr_minutes,
                mttc_minutes         = EXCLUDED.mttc_minutes,
                alert_volume         = EXCLUDED.alert_volume,
                false_positive_count = EXCLUDED.false_positive_count,
                investigation_count  = EXCLUDED.investigation_count,
                detection_count      = EXCLUDED.detection_count,
                computed_at          = EXCLUDED.computed_at
            """,
            [snapshot_date, mttd_minutes, mttr_minutes, mttc_minutes,
             alert_volume, false_positive_count, investigation_count,
             detection_count, computed_at],
        )

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """
        Gracefully shut down the write worker and close the write connection.

        Called during application lifespan shutdown.
        """
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        def _close_sync() -> None:
            try:
                self._write_conn.close()
            except Exception as exc:
                log.warning("Error closing DuckDB write connection", error=str(exc))

        await asyncio.to_thread(_close_sync)
        log.info("DuckDB store closed")
