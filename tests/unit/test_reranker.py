# Phase 54 -- Reranker unit tests. Implemented in 54-08.
"""
Unit tests for backend/services/reranker_client.py.

Tests behavioral contracts for the bge-reranker-v2-m3 microservice client.
All tests use mocked httpx responses -- no live service required.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_rerank_returns_sorted_scores():
    """Reranker client returns passages sorted by descending score.

    Given a list of passages and a query string, rerank_passages() must
    return them ordered from highest to lowest relevance score.
    """
    from backend.services.reranker_client import rerank_passages

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ranked": [
            {"passage": "best", "score": 0.9, "original_index": 2},
            {"passage": "ok", "score": 0.5, "original_index": 0},
            {"passage": "worst", "score": 0.1, "original_index": 1},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("backend.services.reranker_client.settings") as mock_settings,
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        mock_settings.RERANKER_URL = "http://127.0.0.1:8100"
        mock_settings.RERANKER_ENABLED = True

        result = asyncio.run(
            rerank_passages("query", ["ok", "worst", "best"], top_k=3)
        )

    assert result == ["best", "ok", "worst"]


def test_rerank_graceful_degradation():
    """When RERANKER_URL is empty or RERANKER_ENABLED=False, return passages[:top_k] unchanged.

    No HTTP call must be made -- the client degrades to passthrough immediately.
    """
    from backend.services.reranker_client import rerank_passages

    # Case 1: RERANKER_URL is empty
    with patch("backend.services.reranker_client.settings") as mock_settings:
        mock_settings.RERANKER_URL = ""
        mock_settings.RERANKER_ENABLED = True

        result = asyncio.run(
            rerank_passages("query", ["a", "b", "c", "d", "e"], top_k=3)
        )

    assert result == ["a", "b", "c"]

    # Case 2: RERANKER_ENABLED=False (URL set but disabled)
    with patch("backend.services.reranker_client.settings") as mock_settings:
        mock_settings.RERANKER_URL = "http://127.0.0.1:8100"
        mock_settings.RERANKER_ENABLED = False

        result = asyncio.run(
            rerank_passages("query", ["x", "y", "z"], top_k=2)
        )

    assert result == ["x", "y"]


def test_rerank_empty_passages():
    """Calling rerank_passages with an empty list returns an empty list.

    Edge case: empty passage list must not cause an exception and must not
    contact the reranker service.
    """
    from backend.services.reranker_client import rerank_passages

    with patch("backend.services.reranker_client.settings") as mock_settings:
        mock_settings.RERANKER_URL = "http://127.0.0.1:8100"
        mock_settings.RERANKER_ENABLED = True

        result = asyncio.run(rerank_passages("query", [], top_k=5))

    assert result == []
