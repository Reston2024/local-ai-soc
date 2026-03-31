"""
Playbook API — SOAR Playbook Engine (Phase 17).

Endpoints:
    GET  /api/playbooks                                         — list all playbooks
    POST /api/playbooks                                         — create a new playbook
    GET  /api/playbooks/{playbook_id}                           — get a single playbook
    GET  /api/playbooks/{playbook_id}/runs                      — list runs for a playbook
    POST /api/playbooks/{playbook_id}/run/{investigation_id}    — start a new run

    PATCH /api/playbook-runs/{run_id}/step/{step_n}             — advance a step (analyst-gated)
    PATCH /api/playbook-runs/{run_id}/cancel                    — cancel a run
    GET   /api/playbook-runs/{run_id}                           — get a single run
    GET   /api/playbook-runs/{run_id}/stream                    — SSE snapshot of run state

Seeding:
    seed_builtin_playbooks(sqlite_store) is called from main.py lifespan
    after the SQLite store is initialised. It inserts the 5 NIST IR starter
    playbooks on first startup (idempotent — checks for is_builtin=1 rows).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.core.logging import get_logger
from backend.data.builtin_playbooks import BUILTIN_PLAYBOOKS
from backend.models.playbook import PlaybookCreate, PlaybookRunAdvance
from backend.stores.sqlite_store import SQLiteStore

log = get_logger(__name__)

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])
runs_router = APIRouter(prefix="/api/playbook-runs", tags=["playbook-runs"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


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


@router.post("/{playbook_id}/run/{investigation_id}", status_code=201)
async def start_playbook_run(
    playbook_id: str, investigation_id: str, request: Request
) -> JSONResponse:
    """
    POST /api/playbooks/{playbook_id}/run/{investigation_id}

    Creates a new playbook run record with status="running" and returns 201.
    Returns 404 if the playbook does not exist.
    """
    stores = request.app.state.stores

    playbook: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_playbook, playbook_id
    )
    if playbook is None:
        raise HTTPException(status_code=404, detail="Playbook not found")

    run_dict: dict[str, Any] = {
        "run_id": str(uuid4()),
        "playbook_id": playbook_id,
        "investigation_id": investigation_id,
        "status": "running",
        "started_at": utcnow_iso(),
        "completed_at": None,
        "steps_completed": [],
        "analyst_notes": "",
    }

    created: dict[str, Any] = await asyncio.to_thread(
        stores.sqlite.create_playbook_run, run_dict
    )
    log.info(
        "Playbook run started",
        run_id=created["run_id"],
        playbook_id=playbook_id,
        investigation_id=investigation_id,
    )
    return JSONResponse(content=created, status_code=201)


# ---------------------------------------------------------------------------
# Playbook-runs sub-router  (/api/playbook-runs/*)
# ---------------------------------------------------------------------------


@runs_router.get("/{run_id}")
async def get_run(run_id: str, request: Request) -> JSONResponse:
    """
    GET /api/playbook-runs/{run_id} — return a single run or 404.
    """
    stores = request.app.state.stores
    run: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_playbook_run, run_id
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return JSONResponse(content=run)


@runs_router.patch("/{run_id}/step/{step_n}")
async def advance_step(
    run_id: str, step_n: int, body: PlaybookRunAdvance, request: Request
) -> JSONResponse:
    """
    PATCH /api/playbook-runs/{run_id}/step/{step_n}

    Analyst-gated step advancement — records analyst note and outcome.
    Returns 404 if run not found; 409 if run already completed/cancelled.
    Sets status="completed" when the final step is advanced.
    """
    stores = request.app.state.stores

    run: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_playbook_run, run_id
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if run["status"] in ("completed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"Run is already {run['status']}",
        )

    # Fetch the parent playbook to know total step count
    playbook: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_playbook, run["playbook_id"]
    )
    if playbook is None:
        raise HTTPException(status_code=404, detail="Parent playbook not found")

    now = utcnow_iso()
    step_entry: dict[str, Any] = {
        "step_number": step_n,
        "outcome": body.outcome,
        "analyst_note": body.analyst_note,
        "completed_at": now,
    }

    updated_steps: list[dict[str, Any]] = list(run.get("steps_completed") or [])
    updated_steps.append(step_entry)

    total_steps = len(playbook.get("steps") or [])
    new_status = "completed" if step_n >= total_steps else run["status"]
    completed_at = now if new_status == "completed" else run.get("completed_at")

    updated: dict[str, Any] = await asyncio.to_thread(
        stores.sqlite.update_playbook_run,
        run_id,
        {
            "steps_completed": updated_steps,
            "status": new_status,
            "completed_at": completed_at,
        },
    )
    log.info(
        "Playbook run step advanced",
        run_id=run_id,
        step_n=step_n,
        outcome=body.outcome,
        new_status=new_status,
    )
    return JSONResponse(content=updated)


@runs_router.patch("/{run_id}/cancel")
async def cancel_run(run_id: str, request: Request) -> JSONResponse:
    """
    PATCH /api/playbook-runs/{run_id}/cancel

    Cancels a running playbook run.
    Returns 404 if run not found; 409 if already completed or cancelled.
    """
    stores = request.app.state.stores

    run: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_playbook_run, run_id
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if run["status"] in ("completed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"Run is already {run['status']}",
        )

    updated: dict[str, Any] = await asyncio.to_thread(
        stores.sqlite.update_playbook_run,
        run_id,
        {"status": "cancelled", "completed_at": utcnow_iso()},
    )
    log.info("Playbook run cancelled", run_id=run_id)
    return JSONResponse(content=updated)


@runs_router.get("/{run_id}/stream")
async def stream_run(run_id: str, request: Request) -> StreamingResponse:
    """
    GET /api/playbook-runs/{run_id}/stream

    SSE snapshot endpoint — emits the current run state as a "run_state" event
    followed by a "done" event.  The frontend can poll this endpoint to get
    the latest state without maintaining a persistent connection.
    """
    stores = request.app.state.stores

    run: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_playbook_run, run_id
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_stream():
        yield f"data: {json.dumps({'event': 'run_state', 'run': run})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
