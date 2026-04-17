"""
Reranker client. Gracefully degrades to passthrough when RERANKER_URL is empty,
RERANKER_ENABLED=False, or the service is unreachable.

Usage:
    from backend.services.reranker_client import rerank_passages
    passages = await rerank_passages(query, passage_list, top_k=5)

When RERANKER_URL is empty or RERANKER_ENABLED is False, returns passages[:top_k]
unchanged without making any HTTP calls.
"""
from __future__ import annotations

from backend.core.config import settings
from backend.core.logging import get_logger

log = get_logger(__name__)


async def rerank_passages(
    query: str,
    passages: list[str],
    top_k: int = 5,
) -> list[str]:
    """
    Rerank passages for a query using the bge-reranker-v2-m3 microservice.

    Gracefully degrades to passthrough (passages[:top_k], original order)
    when:
    - settings.RERANKER_URL is empty
    - settings.RERANKER_ENABLED is False
    - The reranker service is unreachable or returns an error

    Args:
        query:    The analyst query string.
        passages: List of passage strings to rerank.
        top_k:    Number of top passages to return.

    Returns:
        List of passage strings sorted by relevance (or original order on error).
        Always returns at most top_k items. Never raises.
    """
    if not settings.RERANKER_URL or not settings.RERANKER_ENABLED:
        log.debug(
            "reranker passthrough mode active",
            url_set=bool(settings.RERANKER_URL),
            enabled=settings.RERANKER_ENABLED,
        )
        return passages[:top_k]

    if not passages:
        return []

    import httpx  # noqa: PLC0415

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=2.0, read=8.0, write=4.0, pool=2.0)
        ) as client:
            resp = await client.post(
                f"{settings.RERANKER_URL}/rerank",
                json={
                    "query": query,
                    "passages": passages,
                    "top_k": top_k,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            ranked = data.get("ranked", [])
            return [item["passage"] for item in ranked]

    except Exception as exc:
        log.warning(
            "Reranker call failed -- falling back to passthrough",
            error=str(exc),
            url=settings.RERANKER_URL,
        )
        return passages[:top_k]
