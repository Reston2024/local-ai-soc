"""
Query API — semantic search and analyst Q&A via Ollama + Chroma RAG.

Endpoints:
  POST /query/semantic    — vector similarity search over ingested events
  POST /query/ask         — analyst Q&A with RAG context (non-streaming)
  POST /query/ask/stream  — analyst Q&A with SSE streaming response
"""

from __future__ import annotations

import json
import re as _re
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.core.logging import get_logger
from backend.core.rate_limit import limiter
from backend.stores.chroma_store import DEFAULT_COLLECTION

log = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["query"])

# ---------------------------------------------------------------------------
# Citation verification
# ---------------------------------------------------------------------------

# Regex matching event ID citations: [anything] style (3-64 chars)
_CITATION_RE = _re.compile(r"\[([^\]]{3,64})\]")


def verify_citations(response_text: str, context_ids: list[str]) -> bool:
    """Return True if every event ID cited in response_text exists in context_ids.

    Extracts [id] patterns from the response and checks each against the
    context_ids list. Returns True vacuously when no citations are present.
    If any cited ID is not in context_ids, returns False.
    """
    cited = _CITATION_RE.findall(response_text)
    if not cited:
        return True
    context_set = set(context_ids)
    return all(c in context_set for c in cited)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    collection: str = Field(default=DEFAULT_COLLECTION)
    n_results: int = Field(default=10, ge=1, le=100)
    case_id: Optional[str] = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    case_id: Optional[str] = None
    n_context_events: int = Field(default=8, ge=1, le=30)
    system_prompt: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper: build RAG context string
# ---------------------------------------------------------------------------

_DEFAULT_SYSTEM = """You are an expert cybersecurity analyst assistant.
You have access to security event evidence from the investigation.
Answer the analyst's question concisely and accurately.
Always cite the event IDs that support your answer using [event_id] notation.
If you are uncertain, say so rather than guessing."""


def _build_rag_prompt(question: str, context_docs: list[str]) -> str:
    ctx_block = "\n\n".join(
        f"[Evidence {i + 1}] {doc}" for i, doc in enumerate(context_docs)
    )
    return f"""Context from security event database:

{ctx_block}

---

Analyst question: {question}

Answer based on the context above:"""


# ---------------------------------------------------------------------------
# POST /query/semantic
# ---------------------------------------------------------------------------


@router.post("/semantic")
async def semantic_search(
    body: SemanticSearchRequest, request: Request
) -> JSONResponse:
    """
    Embed the query and perform nearest-neighbour search in Chroma.

    Returns the top-N most similar events from the SOC evidence collection.
    """
    ollama = request.app.state.ollama
    stores = request.app.state.stores

    try:
        embedding = await ollama.embed(body.query)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding generation failed: {exc}",
        ) from exc

    where_filter: Optional[dict[str, Any]] = None
    if body.case_id:
        where_filter = {"case_id": {"$eq": body.case_id}}

    try:
        results = await stores.chroma.query_async(
            collection_name=body.collection,
            query_embeddings=[embedding],
            n_results=body.n_results,
            where=where_filter,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Vector search failed: {exc}",
        ) from exc

    # Flatten Chroma result format
    ids = (results.get("ids") or [[]])[0]
    docs = (results.get("documents") or [[]])[0]
    metas = (results.get("metadatas") or [[]])[0]
    dists = (results.get("distances") or [[]])[0]

    hits = [
        {
            "event_id": ids[i],
            "document": docs[i],
            "metadata": metas[i],
            "distance": dists[i],
        }
        for i in range(len(ids))
    ]

    log.debug("Semantic search", query=body.query[:80], n_hits=len(hits))
    return JSONResponse(
        content={
            "query": body.query,
            "collection": body.collection,
            "hits": hits,
            "total": len(hits),
        }
    )


# ---------------------------------------------------------------------------
# POST /query/ask
# ---------------------------------------------------------------------------


@limiter.limit("30/minute")
@router.post("/ask")
async def ask(body: AskRequest, request: Request) -> JSONResponse:
    """
    Answer an analyst question using RAG: embed question → retrieve context → generate answer.

    Non-streaming.  For streaming use POST /query/ask/stream.
    """
    ollama = request.app.state.ollama
    stores = request.app.state.stores

    # Embed the question
    try:
        q_embedding = await ollama.embed(body.question)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding generation failed: {exc}",
        ) from exc

    # Retrieve context from Chroma
    where_filter: Optional[dict[str, Any]] = None
    if body.case_id:
        where_filter = {"case_id": {"$eq": body.case_id}}

    try:
        results = await stores.chroma.query_async(
            collection_name=DEFAULT_COLLECTION,
            query_embeddings=[q_embedding],
            n_results=body.n_context_events,
            where=where_filter,
        )
    except Exception as exc:
        log.warning("RAG context retrieval failed", error=str(exc))
        results = {}

    docs = (results.get("documents") or [[]])[0]
    ids = (results.get("ids") or [[]])[0]

    prompt = _build_rag_prompt(body.question, docs)
    system = body.system_prompt or _DEFAULT_SYSTEM

    # Resolve operator_id from request state if available (ADR-020 fallback)
    operator_id = getattr(request.state, "operator_id", "system")

    # Generate answer — collect audit metadata via out_context
    out_ctx: dict = {}
    try:
        answer = await ollama.generate(
            prompt,
            system=system,
            grounding_event_ids=ids,
            out_context=out_ctx,
            operator_id=operator_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM generation failed: {exc}",
        ) from exc

    audit_id = out_ctx.get("audit_id")
    is_grounded = len(ids) > 0

    citation_ok = verify_citations(answer, ids)
    if not citation_ok:
        log.warning(
            "Unverified citations in LLM response",
            question_preview=body.question[:80],
            context_ids=ids,
        )

    log.info(
        "Ask answered",
        question_len=len(body.question),
        context_docs=len(docs),
        answer_len=len(answer),
    )

    return JSONResponse(
        content={
            "question": body.question,
            "answer": answer,
            "context_event_ids": ids,
            "context_count": len(docs),
            "citation_verified": citation_ok,
            "audit_id": audit_id,
            "grounding_event_ids": ids,
            "is_grounded": is_grounded,
        }
    )


# ---------------------------------------------------------------------------
# POST /query/ask/stream
# ---------------------------------------------------------------------------


@router.post("/ask/stream")
async def ask_stream(body: AskRequest, request: Request) -> StreamingResponse:
    """
    Streaming analyst Q&A via Server-Sent Events.

    Emits: data: {"token": "..."} per token, then data: {"done": true, "context_event_ids": [...]}
    """
    ollama = request.app.state.ollama
    stores = request.app.state.stores

    # Embed question
    try:
        q_embedding = await ollama.embed(body.question)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding failed: {exc}",
        ) from exc

    # Retrieve context
    where_filter: Optional[dict[str, Any]] = None
    if body.case_id:
        where_filter = {"case_id": {"$eq": body.case_id}}

    try:
        results = await stores.chroma.query_async(
            collection_name=DEFAULT_COLLECTION,
            query_embeddings=[q_embedding],
            n_results=body.n_context_events,
            where=where_filter,
        )
    except Exception:
        results = {}

    docs = (results.get("documents") or [[]])[0]
    ids = (results.get("ids") or [[]])[0]

    prompt = _build_rag_prompt(body.question, docs)
    system = body.system_prompt or _DEFAULT_SYSTEM

    async def event_stream() -> AsyncIterator[str]:
        try:
            tokens_yielded: list[str] = []
            out_ctx: dict = {}

            def _on_token(t: str) -> None:
                tokens_yielded.append(t)

            await ollama.stream_generate(
                prompt,
                system=system,
                on_token=_on_token,
                grounding_event_ids=ids,
                out_context=out_ctx,
            )
            for t in tokens_yielded:
                yield f"data: {json.dumps({'token': t})}\n\n"

            audit_id = out_ctx.get("audit_id")
            is_grounded = len(ids) > 0
            yield f"data: {json.dumps({'done': True, 'context_event_ids': ids, 'audit_id': audit_id, 'is_grounded': is_grounded})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
