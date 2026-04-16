"""Unit tests for SpiderFootClient (Plan 51-02)."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Guard import
_SF_AVAILABLE = False
try:
    from backend.services.spiderfoot_client import SpiderFootClient
    _SF_AVAILABLE = True
except ImportError:
    pass

pytestmark = pytest.mark.skipif(not _SF_AVAILABLE, reason="SpiderFootClient not available")


@pytest.mark.asyncio
async def test_ping_returns_false_when_unreachable():
    """ping() returns False when SpiderFoot container is not running."""
    client = SpiderFootClient(base_url="http://localhost:19999")
    result = await client.ping()
    assert result is False


@pytest.mark.asyncio
async def test_start_scan_uses_form_encoding():
    """start_scan() sends form-encoded body and returns text strip() as scan ID."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "  abc-scan-123  \n"
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_ctx

        client = SpiderFootClient(base_url="http://localhost:5001")
        scan_id = await client.start_scan("1.2.3.4", "investigate")

    assert scan_id == "abc-scan-123"
    # Verify form encoding was used (data= not json=)
    call_kwargs = mock_ctx.post.call_args
    assert "data" in call_kwargs.kwargs or (len(call_kwargs.args) >= 2)


@pytest.mark.asyncio
async def test_get_status_extracts_index_6():
    """get_status() extracts status string from index[6] of the response list."""
    row = ["scan-1", "test", "1.2.3.4", "2026-01-01", "2026-01-01", "2026-01-01", "FINISHED", 12, 300]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=row)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_ctx

        client = SpiderFootClient()
        status = await client.get_status("scan-1")

    assert status == "FINISHED"


@pytest.mark.asyncio
async def test_stop_scan_posts_form_id():
    """stop_scan() posts id= as form data and handles errors gracefully."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_ctx

        client = SpiderFootClient()
        await client.stop_scan("scan-99")  # must not raise

    call_kwargs = mock_ctx.post.call_args
    assert "scan-99" in str(call_kwargs)


def test_spiderfoot_client_has_expected_methods():
    """SpiderFootClient exposes all required methods."""
    client = SpiderFootClient()
    for method in ("ping", "start_scan", "get_status", "get_summary",
                   "get_events", "get_graph", "stop_scan", "delete_scan"):
        assert hasattr(client, method), f"missing method: {method}"
