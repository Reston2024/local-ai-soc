"""
Standalone FastAPI reranker microservice backed by BAAI/bge-reranker-v2-m3.

This is a STANDALONE app -- it is NOT imported by the main backend (main.py).
Run with: uv run python scripts/start_reranker.py

If transformers/torch are not installed, /health returns {"status": "unavailable"}
and POST /rerank returns a passthrough response.

Port: 8100 (separate from the main backend on port 8000)

Install requirements before starting:
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install transformers sentencepiece
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.core.logging import get_logger

log = get_logger(__name__)

MODEL_NAME = "BAAI/bge-reranker-v2-m3"

_model: Any = None
_tokenizer: Any = None
_device: str = "cpu"
_load_error: str | None = None

try:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    log.info("Loading reranker model", model=MODEL_NAME, device=_device)

    try:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        _model = _model.to(_device)
        _model.train(False)
        log.info("Reranker model loaded", model=MODEL_NAME, device=_device)
    except Exception as exc:
        _load_error = f"Model load failed: {exc}"
        log.warning("Reranker model load failed", error=_load_error)

except ImportError as exc:
    _load_error = f"transformers not installed: {exc}"
    log.warning(
        "Reranker unavailable -- install torch + transformers",
        error=_load_error,
        install_hint=(
            "pip install torch --index-url https://download.pytorch.org/whl/cu121 "
            "&& pip install transformers sentencepiece"
        ),
    )


class RerankRequest(BaseModel):
    query: str
    passages: list[str]
    top_k: int = 5


class RankedPassage(BaseModel):
    passage: str
    score: float
    original_index: int


class RerankResponse(BaseModel):
    ranked: list[RankedPassage]


app = FastAPI(title="SOC Reranker", version="1.0.0")


def _run_inference(query: str, passages: list[str]) -> list[float]:
    """Score (query, passage) pairs via cross-encoder. Runs synchronously."""
    import torch  # noqa: PLC0415

    if _model is None or _tokenizer is None:
        raise RuntimeError("Model not loaded")

    scores: list[float] = []
    for passage in passages:
        inputs = _tokenizer(
            query,
            passage,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        inputs = {k: v.to(_device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = _model(**inputs)
        logit = outputs.logits
        if logit.shape[-1] == 1:
            score = float(logit[0][0].item())
        else:
            score = float(logit[0][1].item())
        scores.append(score)

    return scores


@app.get("/health")
async def health() -> JSONResponse:
    """GET /health -- returns service status, model name, and compute device."""
    if _load_error is not None:
        return JSONResponse(
            content={
                "status": "unavailable",
                "reason": _load_error,
                "model": MODEL_NAME,
            }
        )
    return JSONResponse(
        content={
            "status": "ok",
            "model": MODEL_NAME,
            "device": _device,
        }
    )


@app.post("/rerank", response_model=RerankResponse)
async def rerank(body: RerankRequest) -> RerankResponse:
    """POST /rerank -- cross-encoder reranking of passages for a query."""
    if not body.passages:
        return RerankResponse(ranked=[])

    top_k = min(body.top_k, len(body.passages))

    if _load_error is not None or _model is None:
        log.warning("Reranker in passthrough mode (model not loaded)", reason=_load_error)
        ranked = [
            RankedPassage(
                passage=p,
                score=float(len(body.passages) - i),
                original_index=i,
            )
            for i, p in enumerate(body.passages[:top_k])
        ]
        return RerankResponse(ranked=ranked)

    try:
        scores = await asyncio.to_thread(_run_inference, body.query, body.passages)
    except Exception as exc:
        log.error("Cross-encoder inference failed", error=str(exc))
        ranked = [
            RankedPassage(passage=p, score=float(len(body.passages) - i), original_index=i)
            for i, p in enumerate(body.passages[:top_k])
        ]
        return RerankResponse(ranked=ranked)

    indexed_scores = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    ranked = [
        RankedPassage(
            passage=body.passages[idx],
            score=score,
            original_index=idx,
        )
        for idx, score in indexed_scores[:top_k]
    ]

    log.info("Rerank complete", n_passages=len(body.passages), top_k=top_k)
    return RerankResponse(ranked=ranked)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
