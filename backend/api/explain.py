"""POST /api/explain — generate grounded Ollama explanation for an investigation."""
import asyncio
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.intelligence.explain_engine import build_evidence_context, generate_explanation

log = logging.getLogger(__name__)
router = APIRouter()


class ExplainRequest(BaseModel):
    detection_id: str | None = None
    investigation: dict | None = None  # pre-assembled investigation dict (optional)


class ExplainResponse(BaseModel):
    what_happened: str = "insufficient evidence"
    why_it_matters: str = "insufficient evidence"
    recommended_next_steps: str = "insufficient evidence"
    evidence_context: str = ""
    error: str | None = None


@router.post("/explain", response_model=ExplainResponse)
async def post_explain(request: Request, body: ExplainRequest) -> ExplainResponse:
    """Generate a three-section grounded explanation via Ollama.

    Always returns HTTP 200. Returns fallback message if Ollama is unavailable.
    """
    try:
        return await _run_explanation(request, body)
    except Exception as exc:
        log.warning("explain endpoint error (returning fallback): %s", exc)
        return ExplainResponse(error=f"Explanation unavailable: {exc}")


async def _run_explanation(request: Request, body: ExplainRequest) -> ExplainResponse:
    investigation: dict = {}

    # Use pre-assembled investigation if provided
    if body.investigation:
        investigation = body.investigation
    elif body.detection_id:
        investigation = await _assemble_investigation(request, body.detection_id)

    evidence_context = build_evidence_context(investigation)

    # Access OllamaClient via request.app.state.ollama — confirmed pattern from research audit.
    # This avoids any dependency on get_ollama_client() which is not verified to exist in deps.py.
    ollama_client = request.app.state.ollama

    sections = await generate_explanation(investigation, ollama_client)
    return ExplainResponse(
        what_happened=sections.get("what_happened", "insufficient evidence"),
        why_it_matters=sections.get("why_it_matters", "insufficient evidence"),
        recommended_next_steps=sections.get("recommended_next_steps", "insufficient evidence"),
        evidence_context=evidence_context,
    )


async def _assemble_investigation(request: Request, detection_id: str) -> dict:
    """Build a minimal investigation dict from SQLite detection record."""
    import json
    try:
        sqlite_store = request.app.state.stores.sqlite
        row = await asyncio.to_thread(
            lambda: sqlite_store._conn.execute(
                "SELECT id, rule_name, severity, attack_technique, attack_tactic, "
                "matched_event_ids, explanation FROM detections WHERE id = ?",
                (detection_id,),
            ).fetchone()
        )
        if not row:
            return {}
        matched_ids = json.loads(row[5] or "[]")
        investigation: dict = {
            "detection": {
                "id": row[0],
                "rule_name": row[1],
                "severity": row[2],
                "attack_technique": row[3],
                "attack_tactic": row[4],
            },
            "events": [],
            "techniques": [{"technique_id": row[3]}] if row[3] else [],
            "graph": {"elements": {"nodes": []}},
            "timeline": [],
        }
        # Optionally enrich with DuckDB events
        if matched_ids:
            try:
                duckdb_store = request.app.state.stores.duckdb
                placeholders = ",".join("?" * len(matched_ids))
                event_rows = await duckdb_store.fetch_all(
                    f"SELECT * FROM normalized_events WHERE event_id IN ({placeholders})",
                    matched_ids,
                )
                investigation["events"] = [dict(r) for r in event_rows]
            except Exception as dex:
                log.debug("DuckDB event enrichment skipped: %s", dex)
        return investigation
    except Exception as exc:
        log.debug("Investigation assembly skipped: %s", exc)
        return {}
