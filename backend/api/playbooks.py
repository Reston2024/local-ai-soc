"""
Playbook API — SOAR Playbook Engine (Phase 17).

Endpoints:
    GET  /api/playbooks                       — list all playbooks
    POST /api/playbooks                       — create a new playbook
    GET  /api/playbooks/{playbook_id}         — get a single playbook
    GET  /api/playbooks/{playbook_id}/runs    — list runs for a playbook

Seeding:
    seed_builtin_playbooks(sqlite_store) is called from main.py lifespan
    after the SQLite store is initialised. It inserts the 5 NIST IR starter
    playbooks on first startup (idempotent — checks for is_builtin=1 rows).
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger
from backend.data.builtin_playbooks import BUILTIN_PLAYBOOKS
from backend.models.playbook import PlaybookCreate
from backend.stores.sqlite_store import SQLiteStore

log = get_logger(__name__)

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])


# ---------------------------------------------------------------------------
# Startup seeding
# ---------------------------------------------------------------------------


async def seed_builtin_playbooks(sqlite_store: SQLiteStore) -> None:
    """
    Seed the 5 built-in NIST IR playbooks if not already present.

    Idempotent: checks for any is_builtin=1 row before inserting.
    Called from main.py lifespan after sqlite_store is initialised.
    """

    def _seed(store: SQLiteStore) -> int:
        existing = store._conn.execute(
            "SELECT COUNT(*) FROM playbooks WHERE is_builtin = 1"
        ).fetchone()[0]
        if existing > 0:
            log.info(
                "Built-in playbooks already seeded",
                count=existing,
            )
            return 0

        inserted = 0
        for pb_data in BUILTIN_PLAYBOOKS:
            store.create_playbook(pb_data)
            inserted += 1

        log.info("Built-in playbooks seeded", count=inserted)
        return inserted

    count = await asyncio.to_thread(_seed, sqlite_store)
    if count > 0:
        log.info("Playbook library ready", seeded=count)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_playbooks(request: Request) -> JSONResponse:
    """
    GET /api/playbooks — list all playbooks.

    Returns:
        {"playbooks": [...], "total": int}
    """
    stores = request.app.state.stores
    playbooks: list[dict[str, Any]] = await asyncio.to_thread(
        stores.sqlite.get_playbooks
    )
    return JSONResponse(
        content={"playbooks": playbooks, "total": len(playbooks)}
    )


@router.post("", status_code=201)
async def create_playbook(
    body: PlaybookCreate, request: Request
) -> JSONResponse:
    """
    POST /api/playbooks — create a new playbook.

    Returns 201 with the created playbook dict.
    """
    stores = request.app.state.stores
    data = body.model_dump()
    # Serialize steps (list of PlaybookStep) to plain dicts
    data["steps"] = [s if isinstance(s, dict) else s.model_dump() for s in data["steps"]]
    data["is_builtin"] = False

    created: dict[str, Any] = await asyncio.to_thread(
        stores.sqlite.create_playbook, data
    )
    return JSONResponse(content=created, status_code=201)


@router.get("/{playbook_id}")
async def get_playbook(playbook_id: str, request: Request) -> JSONResponse:
    """
    GET /api/playbooks/{playbook_id} — get a single playbook or 404.
    """
    stores = request.app.state.stores
    playbook: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_playbook, playbook_id
    )
    if playbook is None:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return JSONResponse(content=playbook)


@router.get("/{playbook_id}/runs")
async def get_playbook_runs(playbook_id: str, request: Request) -> JSONResponse:
    """
    GET /api/playbooks/{playbook_id}/runs — list all runs for a playbook.

    Returns:
        {"runs": [...], "total": int}
    """
    stores = request.app.state.stores

    # Verify playbook exists
    playbook: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_playbook, playbook_id
    )
    if playbook is None:
        raise HTTPException(status_code=404, detail="Playbook not found")

    runs: list[dict[str, Any]] = await asyncio.to_thread(
        stores.sqlite.get_playbook_runs, playbook_id
    )
    return JSONResponse(content={"runs": runs, "total": len(runs)})
