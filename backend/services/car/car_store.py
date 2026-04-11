"""
CARStore — SQLite CRUD for MITRE CAR analytics catalog (Phase 39).

Provides:
- CARStore: SQLite CRUD wrapping car_analytics table.
- seed_car_analytics(): Async startup seed from bundled JSON.

All CARStore methods are synchronous — call via asyncio.to_thread() from async handlers.
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

CREATE TABLE IF NOT EXISTS car_analytics (
    analytic_id      TEXT NOT NULL,
    technique_id     TEXT NOT NULL,
    title            TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    log_sources      TEXT NOT NULL DEFAULT '',
    analyst_notes    TEXT NOT NULL DEFAULT '',
    pseudocode       TEXT NOT NULL DEFAULT '',
    coverage_level   TEXT NOT NULL DEFAULT '',
    platforms        TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (analytic_id, technique_id)
);

CREATE INDEX IF NOT EXISTS idx_car_technique ON car_analytics (technique_id);
CREATE INDEX IF NOT EXISTS idx_car_analytic  ON car_analytics (analytic_id);
"""


class CARStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.executescript(DDL)
        self._conn.commit()

    def analytic_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM car_analytics").fetchone()[0]

    def bulk_insert(self, analytics: list[dict]) -> None:
        """Insert analytics from bundled JSON list. Idempotent (INSERT OR IGNORE)."""
        self._conn.executemany(
            """INSERT OR IGNORE INTO car_analytics
               (analytic_id, technique_id, title, description, log_sources,
                analyst_notes, pseudocode, coverage_level, platforms)
               VALUES (:analytic_id, :technique_id, :title, :description,
                       :log_sources, :analyst_notes, :pseudocode,
                       :coverage_level, :platforms)""",
            analytics,
        )
        self._conn.commit()

    def get_analytics_for_technique(self, technique_id: str | None) -> list[dict]:
        """Return all CAR analytics covering the given ATT&CK technique ID.

        Sub-technique IDs (e.g. T1059.001) are resolved to their parent (T1059).
        Returns [] for None/empty input or no match.
        """
        if not technique_id:
            return []
        parent_id = technique_id.split(".")[0].upper()
        rows = self._conn.execute(
            """SELECT analytic_id, technique_id, title, description, log_sources,
                      analyst_notes, pseudocode, coverage_level, platforms
               FROM car_analytics
               WHERE technique_id = ?
               ORDER BY analytic_id ASC""",
            (parent_id,),
        ).fetchall()
        return [dict(row) for row in rows]


async def seed_car_analytics(car_store: CARStore) -> None:
    """Seed CAR analytics from bundled JSON on startup. Idempotent."""
    if car_store.analytic_count() > 0:
        log.info("CAR analytics already seeded — skipping")
        return
    data_path = Path(__file__).parent.parent.parent / "data" / "car_analytics.json"
    if not data_path.exists():
        log.warning("CAR analytics bundle not found at %s — skipping seed", data_path)
        return
    analytics = json.loads(data_path.read_text(encoding="utf-8"))
    await asyncio.to_thread(car_store.bulk_insert, analytics)
    log.info("CAR analytics seeded: %d entries", car_store.analytic_count())
