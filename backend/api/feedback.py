"""
Analyst feedback API — TP/FP verdict submission and similar case retrieval.

Endpoints:
  POST /api/feedback          — submit TP/FP verdict for a detection
  GET  /api/feedback/similar  — retrieve top 3 similar confirmed incidents
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.core.logging import get_logger

log = get_logger(__name__)

feedback_router = APIRouter()

_FEEDBACK_COLLECTION = "feedback_verdicts"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class FeedbackRequest(BaseModel):
    detection_id: str
    verdict: str
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    severity: Optional[int] = None


class SimilarCase(BaseModel):
    detection_id: str
    verdict: str
    rule_name: Optional[str]
    similarity_pct: int
    summary: Optional[str]


# ---------------------------------------------------------------------------
# Background ML update (fire-and-forget)
# ---------------------------------------------------------------------------


async def _async_ml_update(state, body: FeedbackRequest) -> None:
    """Embed verdict in Chroma + call River learn_one — all non-fatal."""
    try:
        stores = getattr(state, "stores", None)
        chroma = getattr(stores, "chroma", None) if stores else None
        ollama = getattr(state, "ollama", None)

        if chroma and ollama:
            doc = f"{body.rule_name or body.rule_id or 'detection'} severity={body.severity}"
            try:
                embedding = await ollama.embed(doc)
            except Exception as exc:
                log.debug("feedback embed failed (non-fatal): %s", exc)
                embedding = None

            if embedding:
                await chroma.add_documents_async(
                    collection_name=_FEEDBACK_COLLECTION,
                    ids=[body.detection_id],
                    documents=[doc],
                    embeddings=[embedding],
                    metadatas=[
                        {
                            "detection_id": body.detection_id,
                            "verdict": body.verdict,
                            "rule_id": body.rule_id or "",
                            "rule_name": body.rule_name or "",
                            "severity": str(body.severity or 2),
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ],
                )
    except Exception as exc:
        log.debug("feedback Chroma update failed (non-fatal): %s", exc)

    try:
        classifier = getattr(state, "feedback_classifier", None)
        if classifier:
            features = {
                "severity": body.severity or 2,
                "rule_id_hash": hash(body.rule_id or "") % 1000,
            }
            await asyncio.to_thread(classifier.learn_one, features, body.verdict)
    except Exception as exc:
        log.debug("feedback classifier update failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# POST /api/feedback
# ---------------------------------------------------------------------------


@feedback_router.post("")
async def submit_feedback(request: Request, body: FeedbackRequest) -> JSONResponse:
    """Submit a TP/FP verdict for a detection.

    Stores verdict in SQLite immediately. Chroma embed and River classifier
    update happen asynchronously and silently — analysts never see ML errors.
    """
    if body.verdict not in {"TP", "FP"}:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid verdict '{body.verdict}' — must be 'TP' or 'FP'",
        )

    stores = request.app.state.stores
    await asyncio.to_thread(
        stores.sqlite.upsert_feedback, body.detection_id, body.verdict
    )

    # Fire-and-forget — never blocks the response or surfaces ML errors
    asyncio.ensure_future(_async_ml_update(request.app.state, body))

    log.info(
        "Feedback verdict stored",
        detection_id=body.detection_id,
        verdict=body.verdict,
    )
    return JSONResponse(content={"ok": True, "verdict": body.verdict})


# ---------------------------------------------------------------------------
# GET /api/feedback/similar
# ---------------------------------------------------------------------------


@feedback_router.get("/similar")
async def get_similar_cases(
    request: Request,
    detection_id: str = Query(...),
    rule_id: str = Query(default=""),
    rule_name: str = Query(default=""),
) -> JSONResponse:
    """Return top 3 similar confirmed incidents from Chroma feedback_verdicts.

    Skips self-match (the queried detection_id itself).
    Returns empty list on any error (Chroma may be offline or collection empty).
    """
    stores = request.app.state.stores
    ollama = request.app.state.ollama

    query_text = rule_name or rule_id or detection_id

    try:
        embedding = await ollama.embed(query_text)
        if not embedding:
            return JSONResponse(content={"cases": []})

        result = await stores.chroma.query_async(
            collection_name=_FEEDBACK_COLLECTION,
            query_embeddings=[embedding],
            n_results=4,
            where=None,
        )

        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]

        cases: list[dict] = []
        for i, doc_id in enumerate(ids):
            if doc_id == detection_id:
                continue  # skip self-match

            meta = metadatas[i] if i < len(metadatas) else {}
            dist = distances[i] if i < len(distances) else 1.0
            # Cosine distance in [0, 2]; convert to similarity %
            similarity_pct = max(0, round((1.0 - dist) * 100))

            cases.append(
                {
                    "detection_id": doc_id,
                    "verdict": meta.get("verdict", ""),
                    "rule_name": meta.get("rule_name") or None,
                    "similarity_pct": similarity_pct,
                    "summary": f"{meta.get('rule_name', '')} severity={meta.get('severity', '?')}".strip() or None,
                }
            )
            if len(cases) >= 3:
                break

    except Exception as exc:
        log.debug("feedback similar query failed (non-fatal): %s", exc)
        return JSONResponse(content={"cases": []})

    return JSONResponse(content={"cases": cases})
