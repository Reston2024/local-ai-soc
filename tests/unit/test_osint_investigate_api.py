"""Wave 0 TDD stubs for POST /api/osint/investigate and GET endpoints (Plan 51-03)."""
import pytest

_API_AVAILABLE = False
try:
    from backend.api.osint_api import router
    _routes = [r.path for r in router.routes]
    _API_AVAILABLE = "/osint/investigate" in _routes or any("/investigate" in p for p in _routes)
except Exception:
    pass

_skip = pytest.mark.skipif(not _API_AVAILABLE, reason="investigate routes not yet registered")


@_skip
def test_post_investigate_returns_job_id(client):
    """POST /api/osint/investigate returns {job_id, status: RUNNING}."""
    assert False, "implement in Plan 51-03"


@_skip
def test_get_investigation_status(client):
    """GET /api/osint/investigate/{job_id} returns job status dict."""
    assert False, "implement in Plan 51-03"


@_skip
def test_get_investigations_list(client):
    """GET /api/osint/investigations returns list of investigations."""
    assert False, "implement in Plan 51-03"


@_skip
def test_delete_investigation_cancels(client):
    """DELETE /api/osint/investigate/{job_id} stops scan and marks cancelled."""
    assert False, "implement in Plan 51-03"


@_skip
def test_post_dnstwist_returns_lookalikes(client):
    """POST /api/osint/dnstwist returns {lookalikes: [...]} for a domain."""
    assert False, "implement in Plan 51-03"


@_skip
def test_get_investigation_stream_returns_sse(client):
    """GET /api/osint/investigate/{job_id}/stream returns text/event-stream."""
    assert False, "implement in Plan 51-03"


@_skip
def test_spiderfoot_health_in_system_health(client):
    """GET /health response includes spiderfoot key."""
    assert False, "implement in Plan 51-03"
