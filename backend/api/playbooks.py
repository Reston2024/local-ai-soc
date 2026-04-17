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
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.core.logging import get_logger
from backend.data.builtin_playbooks import BUILTIN_PLAYBOOKS
from backend.enforcement.ipfire import build_enforcer_from_settings, execute_containment_action
from backend.enforcement.policy import EnforcementPolicy
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
    Seed the built-in playbook library on startup.

    Strategy (Phase 46 — expanded multi-source library):
      1. Tag existing is_builtin=1 rows with source='custom' as source='nist' (legacy cleanup).
      2. Delete all rows where source='nist'.
      3. Collect all existing builtin names (any source) — idempotent guard.
      4. Insert any BUILTIN_PLAYBOOKS entry whose name is not already present.
      5. Backfill category for existing builtin rows that have category='' — allows
         retroactive categorisation of playbooks seeded before Phase 46.

    Returns 404 for playbook runs that reference deleted NIST playbook IDs —
    old runs remain as historical records but cannot be advanced.

    Called from main.py lifespan after sqlite_store is initialised.
    """

    # Category backfill map — name → category for the 19 CISA playbooks seeded in Phase 38
    _CISA_CATEGORY_MAP: dict[str, str] = {
        "Phishing / BEC Response": "phishing",
        "Ransomware Response": "ransomware",
        "Credential / Account Compromise Response": "identity",
        "Malware / Intrusion Response": "malware",
        "Vulnerability Response": "vulnerability",
        "Denial of Service / DDoS Response": "network",
        "Supply Chain Compromise Response": "supply_chain",
        "Data Exfiltration / Breach Response": "data_breach",
        "Web Application Attack Response": "web",
        "Insider Threat Response": "insider",
        "Cloud Account Compromise Response": "cloud",
        "ICS / OT Intrusion Response": "ics_ot",
        "Active Directory Full Compromise Response": "identity",
        "Cryptojacking / Resource Hijacking Response": "endpoint",
        "Destructive Wiper Response": "malware",
        "M365 Tenant Compromise Response": "cloud",
        "APT / Long-Dwell Intrusion Response": "malware",
        "Wire Fraud / Business Payment Fraud Response": "phishing",
        "Living-off-the-Land (LotL) Attack Response": "endpoint",
    }

    def _seed(store: SQLiteStore) -> int:
        # Step 1: Tag legacy NIST builtins (source DEFAULT was 'custom' before Phase 38)
        store._conn.execute(
            "UPDATE playbooks SET source = 'nist' WHERE is_builtin = 1 AND source = 'custom'"
        )
        store._conn.commit()
        # Step 2: Delete old NIST builtins
        store._conn.execute(
            "DELETE FROM playbooks WHERE is_builtin = 1 AND source = 'nist'"
        )
        store._conn.commit()
        # Step 3: Collect ALL existing builtin names (any source) — idempotent per-name
        existing_names: set[str] = {
            row[0]
            for row in store._conn.execute(
                "SELECT name FROM playbooks WHERE is_builtin = 1"
            ).fetchall()
        }
        # Step 4: Insert any playbook not already present
        added = 0
        for pb_data in BUILTIN_PLAYBOOKS:
            if pb_data["name"] not in existing_names:
                store.create_playbook(pb_data)
                added += 1
        # Step 5: Backfill category for existing rows that have category=''
        backfilled = 0
        for name, cat in _CISA_CATEGORY_MAP.items():
            result = store._conn.execute(
                "UPDATE playbooks SET category = ? WHERE name = ? AND (category IS NULL OR category = '')",
                (cat, name),
            )
            backfilled += result.rowcount
        if backfilled:
            store._conn.commit()
            log.info("Backfilled playbook categories", count=backfilled)

        if added:
            log.info("Built-in playbooks seeded", added=added, total=len(BUILTIN_PLAYBOOKS))
        else:
            log.info("Built-in playbooks already up to date", total=len(BUILTIN_PLAYBOOKS))
        return added

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


@router.get("/mttr")
async def get_playbook_mttr(request: Request) -> JSONResponse:
    """
    GET /api/playbooks/mttr — return MTTR (Mean Time To Resolve) metrics.

    Aggregates duration (completed_at - started_at) over playbook runs whose
    status is 'completed' or 'failed' and whose timestamps are present.

    Returns:
        {
            "mttr_seconds": float | None,
            "p50_seconds":  float | None,
            "p95_seconds":  float | None,
            "sample_size":  int,
            "by_playbook":  [
                {"playbook_id", "name", "mttr_seconds", "sample_size"}, ...
            ]
        }

    Never raises 500 — returns zero/null payload on error.
    """
    stores = request.app.state.stores

    def _query(store: SQLiteStore) -> list[dict[str, Any]]:
        rows = store._conn.execute(
            """
            SELECT r.run_id, r.playbook_id, r.started_at, r.completed_at,
                   COALESCE(p.name, '') AS playbook_name
            FROM playbook_runs r
            LEFT JOIN playbooks p ON r.playbook_id = p.playbook_id
            WHERE r.status IN ('completed', 'failed')
              AND r.completed_at IS NOT NULL
              AND r.started_at IS NOT NULL
            """
        ).fetchall()
        return [dict(r) for r in rows]

    empty_payload: dict[str, Any] = {
        "mttr_seconds": None,
        "p50_seconds": None,
        "p95_seconds": None,
        "sample_size": 0,
        "by_playbook": [],
    }

    try:
        rows: list[dict[str, Any]] = await asyncio.to_thread(_query, stores.sqlite)

        # Compute duration_seconds per row. Skip any row with unparseable timestamps.
        durations: list[float] = []
        per_pb: dict[str, dict[str, Any]] = {}
        for row in rows:
            started_raw = row.get("started_at")
            completed_raw = row.get("completed_at")
            if not started_raw or not completed_raw:
                continue
            try:
                started = datetime.fromisoformat(started_raw)
                completed = datetime.fromisoformat(completed_raw)
            except (ValueError, TypeError):
                continue
            delta = (completed - started).total_seconds()
            if delta < 0:
                continue
            durations.append(delta)

            pb_id = row.get("playbook_id") or ""
            bucket = per_pb.setdefault(
                pb_id,
                {"playbook_id": pb_id, "name": row.get("playbook_name") or "", "durations": []},
            )
            bucket["durations"].append(delta)

        if not durations:
            return JSONResponse(content=empty_payload)

        def _mean(values: list[float]) -> float:
            return sum(values) / len(values)

        def _percentile(values: list[float], p: float) -> float:
            # Nearest-rank percentile — simple, dependency-free.
            if not values:
                return 0.0
            s = sorted(values)
            k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
            return s[k]

        by_playbook: list[dict[str, Any]] = []
        for pb_id, bucket in per_pb.items():
            pb_durs = bucket["durations"]
            by_playbook.append(
                {
                    "playbook_id": pb_id,
                    "name": bucket["name"],
                    "mttr_seconds": _mean(pb_durs),
                    "sample_size": len(pb_durs),
                }
            )
        by_playbook.sort(key=lambda d: d["playbook_id"])

        return JSONResponse(
            content={
                "mttr_seconds": _mean(durations),
                "p50_seconds": _percentile(durations, 50),
                "p95_seconds": _percentile(durations, 95),
                "sample_size": len(durations),
                "by_playbook": by_playbook,
            }
        )
    except Exception as exc:
        log.warning("MTTR computation failed (returning empty payload)", error=str(exc))
        return JSONResponse(content=empty_payload)


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

    # Record playbook run provenance (non-fatal)
    try:
        steps_json = playbook.get("steps", "[]")
        if not isinstance(steps_json, str):
            steps_json = json.dumps(steps_json)
        pb_sha256 = hashlib.sha256(steps_json.encode()).hexdigest()
        pb_version = playbook.get("version", "1.0") or "1.0"
        await asyncio.to_thread(
            stores.sqlite.record_playbook_provenance,
            str(uuid4()),
            run_dict["run_id"],
            playbook_id,
            pb_sha256,
            pb_version,
            [],  # trigger_event_ids: none in this unauthenticated path
            None,  # operator_id_who_approved: not yet threaded through
        )
    except Exception as exc:
        log.warning("Playbook provenance write failed (non-fatal)", error=str(exc))

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

    # --- Enforcement: policy-gated containment action ---
    enforcement_result: dict[str, Any] | None = None
    if body.containment_action and body.outcome == "confirmed":
        try:
            from backend.core.config import settings as _cfg

            # Look up the step definition to get requires_approval flag
            playbook_steps = playbook.get("steps") or []
            step_def: dict[str, Any] = {}
            for s in playbook_steps:
                if s.get("step_number") == step_n:
                    step_def = s
                    break
            step_requires_approval = bool(step_def.get("requires_approval", True))

            # Evaluate enforcement policy gate
            policy = EnforcementPolicy.from_settings(_cfg)
            decision = policy.allow(
                action_str=body.containment_action,
                confidence=body.confidence,     # analyst/detection confidence 0-1
                step_requires_approval=step_requires_approval,
                human_confirmed=(body.outcome == "confirmed"),
            )

            if not decision.allowed:
                # Policy denied — record the denial but do NOT execute
                log.warning(
                    "Enforcement policy denied action",
                    action=decision.action,
                    target=decision.target,
                    gate=decision.gate_applied,
                    reason=decision.reason,
                )
                enforcement_result = {
                    "action": decision.action,
                    "target": decision.target,
                    "method": "policy_denied",
                    "success": False,
                    "message": decision.reason,
                    "timestamp": now,
                    "gate_applied": decision.gate_applied,
                }
            else:
                # Policy approved — execute the action
                enforcer = build_enforcer_from_settings(_cfg)
                result = await execute_containment_action(body.containment_action, enforcer)
                enforcement_result = {
                    "action": result.action,
                    "target": result.target,
                    "method": result.method,
                    "success": result.success,
                    "message": result.message,
                    "timestamp": result.timestamp,
                    "gate_applied": "allowed",
                }
                if result.error:
                    enforcement_result["error"] = result.error
                log.info(
                    "Enforcement action executed",
                    action=result.action,
                    target=result.target,
                    method=result.method,
                    success=result.success,
                )
        except Exception as exc:
            log.warning("Enforcement action failed (non-fatal): %s", exc)
            enforcement_result = {
                "action": body.containment_action,
                "target": "",
                "method": "error",
                "success": False,
                "message": str(exc),
                "timestamp": now,
            }

    step_entry: dict[str, Any] = {
        "step_number": step_n,
        "outcome": body.outcome,
        "analyst_note": body.analyst_note,
        "completed_at": now,
    }
    if enforcement_result:
        step_entry["enforcement"] = enforcement_result

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


class PlaybookRunPatch(BaseModel):
    """Request body for PATCH /api/playbook-runs/{run_id} — partial update."""
    active_case_id: Optional[str] = None


@runs_router.patch("/{run_id}", response_model=None)
async def patch_playbook_run(
    run_id: str, body: PlaybookRunPatch, request: Request
) -> JSONResponse:
    """
    PATCH /api/playbook-runs/{run_id}

    Partial update for a playbook run. Currently supports setting active_case_id.
    Returns 404 if run not found.
    """
    stores = request.app.state.stores

    run: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_playbook_run, run_id
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if body.active_case_id is not None:
        def _set_case_id(store: SQLiteStore) -> None:
            store._conn.execute(
                "UPDATE playbook_runs SET active_case_id = ? WHERE run_id = ?",
                (body.active_case_id, run_id),
            )
            store._conn.commit()

        await asyncio.to_thread(_set_case_id, stores.sqlite)

    updated: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_playbook_run, run_id
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
