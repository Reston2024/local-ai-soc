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
import os
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
    case_id             TEXT
)
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON normalized_events (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_events_hostname  ON normalized_events (hostname)",
    "CREATE INDEX IF NOT EXISTS idx_events_process   ON normalized_events (process_name)",
    "CREATE INDEX IF NOT EXISTS idx_events_case_id   ON normalized_events (case_id)",
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
        Open and return a new read-only connection to the database file.

        Callers must close the connection when done, e.g.::

            conn = store.get_read_conn()
            try:
                result = await asyncio.to_thread(conn.execute, sql)
            finally:
                conn.close()

        A new connection per query is acceptable for a desktop workload
        and avoids any cross-request state leakage.
        """
        return duckdb.connect(self._db_path, read_only=True)

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
