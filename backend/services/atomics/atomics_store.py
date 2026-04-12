"""
AtomicsStore — SQLite CRUD for Atomic Red Team catalog (Phase 40).

Provides:
- AtomicsStore: SQLite CRUD wrapping atomics + atomics_validation_results tables.
- seed_atomics(): Async startup seed from bundled JSON.

All AtomicsStore methods are synchronous — call via asyncio.to_thread() from async handlers.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from backend.core.logging import get_logger

log = get_logger(__name__)

DDL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS atomics (
    technique_id TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    test_number INTEGER NOT NULL,
    test_name TEXT NOT NULL,
    auto_generated_guid TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    supported_platforms TEXT NOT NULL DEFAULT '[]',
    executor_name TEXT NOT NULL DEFAULT '',
    elevation_required INTEGER NOT NULL DEFAULT 0,
    command TEXT NOT NULL DEFAULT '',
    cleanup_command TEXT NOT NULL DEFAULT '',
    prereq_command TEXT NOT NULL DEFAULT '',
    input_arguments TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (technique_id, test_number)
);
CREATE TABLE IF NOT EXISTS atomics_validation_results (
    technique_id TEXT NOT NULL,
    test_number INTEGER NOT NULL,
    verdict TEXT NOT NULL,
    validated_at TEXT NOT NULL,
    detection_id TEXT,
    PRIMARY KEY (technique_id, test_number)
);
CREATE INDEX IF NOT EXISTS idx_atomics_technique ON atomics (technique_id);
"""


class AtomicsStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        if self._conn.row_factory is None:
            self._conn.row_factory = sqlite3.Row
        self._conn.executescript(DDL)
        self._conn.commit()

    def atomic_count(self) -> int:
        """Return total number of atomic tests in the catalog."""
        return self._conn.execute("SELECT COUNT(*) FROM atomics").fetchone()[0]

    def bulk_insert(self, tests: list[dict]) -> None:
        """Insert atomic tests from list. Idempotent (INSERT OR IGNORE)."""
        self._conn.executemany(
            """INSERT OR IGNORE INTO atomics
               (technique_id, display_name, test_number, test_name,
                auto_generated_guid, description, supported_platforms,
                executor_name, elevation_required, command,
                cleanup_command, prereq_command, input_arguments)
               VALUES
               (:technique_id, :display_name, :test_number, :test_name,
                :auto_generated_guid, :description, :supported_platforms,
                :executor_name, :elevation_required, :command,
                :cleanup_command, :prereq_command, :input_arguments)""",
            tests,
        )
        self._conn.commit()

    def list_techniques(self) -> list[dict]:
        """Return distinct technique_id + display_name pairs ordered by technique_id."""
        rows = self._conn.execute(
            "SELECT DISTINCT technique_id, display_name FROM atomics ORDER BY technique_id"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_tests_for_technique(self, technique_id: str) -> list[dict]:
        """Return all tests for a given technique_id ordered by test_number."""
        rows = self._conn.execute(
            "SELECT * FROM atomics WHERE technique_id = ? ORDER BY test_number",
            (technique_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def save_validation_result(
        self,
        technique_id: str,
        test_number: int,
        verdict: str,
        detection_id: str | None,
    ) -> None:
        """Persist a validation result (INSERT OR REPLACE — idempotent)."""
        self._conn.execute(
            """INSERT OR REPLACE INTO atomics_validation_results
               (technique_id, test_number, verdict, validated_at, detection_id)
               VALUES (?, ?, ?, datetime('now'), ?)""",
            (technique_id, test_number, verdict, detection_id),
        )
        self._conn.commit()

    def get_validation_results(self) -> dict[tuple, dict]:
        """Return {(technique_id, test_number): {verdict, validated_at, detection_id}}."""
        rows = self._conn.execute(
            "SELECT technique_id, test_number, verdict, validated_at, detection_id "
            "FROM atomics_validation_results"
        ).fetchall()
        return {
            (row["technique_id"], row["test_number"]): {
                "verdict": row["verdict"],
                "validated_at": row["validated_at"],
                "detection_id": row["detection_id"],
            }
            for row in rows
        }


async def seed_atomics(atomics_store: AtomicsStore) -> None:
    """Seed atomic tests from bundled JSON on startup. Idempotent."""
    if atomics_store.atomic_count() > 0:
        log.info("Atomics catalog already seeded — skipping")
        return
    data_path = Path(__file__).parent.parent.parent / "data" / "atomics.json"
    if not data_path.exists():
        log.warning("Atomics bundle not found at %s — skipping seed", data_path)
        return
    tests = json.loads(data_path.read_text(encoding="utf-8"))
    await asyncio.to_thread(atomics_store.bulk_insert, tests)
    log.info("Atomics seeded: %d tests", atomics_store.atomic_count())
