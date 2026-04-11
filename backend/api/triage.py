"""POST /api/triage/run — AI triage of untriaged detections.
   GET  /api/triage/latest — most recent triage result.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from prompts.triage import build_prompt

log = logging.getLogger(__name__)
router = APIRouter(prefix="/triage", tags=["triage"])


class _TriageResult(BaseModel):
    """D-43: Validates triage output fields before persisting to SQLite."""

    run_id: str
    severity_summary: str
    result_text: str
    detection_count: int
    model_name: str
    created_at: str

    @field_validator("run_id")
    @classmethod
    def _run_id_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("run_id must not be empty")
        return v

    @field_validator("severity_summary", "result_text", "model_name")
    @classmethod
    def _str_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field must not be empty")
        return v

    @field_validator("detection_count")
    @classmethod
    def _count_nonneg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("detection_count must be >= 0")
        return v


@router.post("/run")
async def post_triage_run(request: Request) -> JSONResponse:
    """Triage all untriaged detections. Returns result summary."""
    result = await _run_triage(request.app)
    return JSONResponse(result)


@router.get("/latest")
async def get_triage_latest(request: Request) -> JSONResponse:
    """Return the most recent triage result row."""
    stores = request.app.state.stores
    row = await asyncio.to_thread(stores.sqlite.get_latest_triage)
    return JSONResponse({"result": row})


async def _run_triage(app) -> dict:
    """Core triage logic — callable from endpoint and background worker."""
    stores = app.state.stores
    ollama_client = app.state.ollama

    # Fetch untriaged detections
    def _fetch_untriaged(conn):
        rows = conn.execute(
            """SELECT id, rule_name, severity, attack_technique, attack_tactic
               FROM detections
               WHERE triaged_at IS NULL
               ORDER BY created_at DESC
               LIMIT 20""",
        ).fetchall()
        return [dict(r) for r in rows]

    detections = await asyncio.to_thread(_fetch_untriaged, stores.sqlite._conn)

    if not detections:
        return {"detection_count": 0, "message": "No untriaged detections"}

    # Build detection summary strings for prompt
    det_summaries = [
        f"Rule: {d.get('rule_name', '?')} | Severity: {d.get('severity', '?')} | "
        f"Technique: {d.get('attack_technique', '?')} | Tactic: {d.get('attack_tactic', '?')}"
        for d in detections
    ]

    system_turn, user_turn = build_prompt(det_summaries)

    result_text = ""
    model_name = "unknown"
    try:
        result_text = await ollama_client.generate(system=system_turn, prompt=user_turn)
        model_name = getattr(ollama_client, "model", "ollama")
    except Exception as exc:
        log.warning("Ollama triage call failed: %s", exc)
        result_text = f"Triage unavailable: {exc}"

    # Derive severity_summary from first non-empty line of result
    first_line = next((ln.strip() for ln in result_text.splitlines() if ln.strip()), "See full result")
    severity_summary = first_line[:200]

    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # D-43: validate triage output before persisting
    result_obj = _TriageResult(
        run_id=run_id,
        severity_summary=severity_summary,
        result_text=result_text,
        detection_count=len(detections),
        model_name=model_name,
        created_at=created_at,
    )
    result_dict = result_obj.model_dump()

    # Save result
    await asyncio.to_thread(stores.sqlite.save_triage_result, result_dict)

    # Mark detections triaged
    det_ids = [d["id"] for d in detections]

    def _mark_triaged(conn, ids, ts):
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE detections SET triaged_at = ? WHERE id IN ({placeholders})",
            [ts] + ids,
        )
        conn.commit()

    await asyncio.to_thread(_mark_triaged, stores.sqlite._conn, det_ids, created_at)

    return result_dict


async def _auto_triage_loop(app) -> None:
    """Background worker: poll for untriaged detections every 60 seconds."""
    log.info("Auto-triage worker started (60s interval)")
    while True:
        try:
            result = await _run_triage(app)
            if result.get("detection_count", 0) > 0:
                log.info(
                    "Auto-triage complete: %d detections triaged",
                    result["detection_count"],
                )
        except asyncio.CancelledError:
            log.info("Auto-triage worker stopped")
            raise
        except Exception as exc:
            log.warning("Auto-triage iteration error (continuing): %s", exc)
        await asyncio.sleep(60)
