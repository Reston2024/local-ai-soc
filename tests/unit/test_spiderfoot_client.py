"""Wave 0 TDD stubs for SpiderFootClient (Plan 51-02)."""
import pytest

_SF_AVAILABLE = False
try:
    from backend.services.spiderfoot_client import SpiderFootClient
    _SF_AVAILABLE = True
except ImportError:
    pass

_skip = pytest.mark.skipif(not _SF_AVAILABLE, reason="SpiderFootClient not yet implemented")


@_skip
@pytest.mark.asyncio
async def test_ping_returns_false_when_unreachable():
    """ping() returns False when SpiderFoot container is not running."""
    client = SpiderFootClient(base_url="http://localhost:19999")
    result = await client.ping()
    assert result is False


@_skip
@pytest.mark.asyncio
async def test_start_scan_uses_form_encoding(httpx_mock):
    """start_scan() sends application/x-www-form-urlencoded body, not JSON."""
    from backend.services.spiderfoot_client import SpiderFootClient
    # stub: will be implemented in Plan 51-02
    assert False, "implement in Plan 51-02"


@_skip
@pytest.mark.asyncio
async def test_get_status_extracts_index_6():
    """get_status() extracts status string from index[6] of the response list."""
    assert False, "implement in Plan 51-02"


@_skip
@pytest.mark.asyncio
async def test_stop_scan_posts_form_id():
    """stop_scan() posts id= as form data."""
    assert False, "implement in Plan 51-02"


@_skip
def test_spiderfoot_client_has_expected_methods():
    """SpiderFootClient exposes ping, start_scan, get_status, get_summary, get_events, get_graph, stop_scan, delete_scan."""
    client = SpiderFootClient()
    for method in ("ping", "start_scan", "get_status", "get_summary", "get_events", "get_graph", "stop_scan", "delete_scan"):
        assert hasattr(client, method), f"missing method: {method}"
