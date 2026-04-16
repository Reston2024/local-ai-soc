"""Wave 0 TDD stubs for POST /api/osint/investigate and GET endpoints (Plan 51-03).

These stubs activate when routes exist (Plan 51-03) but remain SKIP until
the FastAPI test client fixture is set up in Plan 51-04.
"""
import pytest

_API_AVAILABLE = False
try:
    from backend.api.osint_api import router
    _routes = [r.path for r in router.routes]
    _API_AVAILABLE = "/osint/investigate" in _routes or any("/investigate" in p for p in _routes)
except Exception:
    pass

# Client fixture is wired in Plan 51-04 — skip all tests until then
_CLIENT_AVAILABLE = False
try:
    import tests.conftest as _conftest  # noqa: F401
    _CLIENT_AVAILABLE = hasattr(_conftest, "client") or hasattr(_conftest, "app_client")
except Exception:
    pass

_skip = pytest.mark.skipif(
    not _API_AVAILABLE or not _CLIENT_AVAILABLE,
    reason="investigate routes or test client not yet available (Plan 51-04)",
)


@_skip
def test_post_investigate_returns_job_id(client):
    """POST /api/osint/investigate returns {job_id, status: RUNNING}."""
    assert False, "implement in Plan 51-04"


@_skip
def test_get_investigation_status(client):
    """GET /api/osint/investigate/{job_id} returns job status dict."""
    assert False, "implement in Plan 51-04"


@_skip
def test_get_investigations_list(client):
    """GET /api/osint/investigations returns list of investigations."""
    assert False, "implement in Plan 51-04"


@_skip
def test_delete_investigation_cancels(client):
    """DELETE /api/osint/investigate/{job_id} stops scan and marks cancelled."""
    assert False, "implement in Plan 51-04"


@_skip
def test_post_dnstwist_returns_lookalikes(client):
    """POST /api/osint/dnstwist returns {lookalikes: [...]} for a domain."""
    assert False, "implement in Plan 51-04"


@_skip
def test_get_investigation_stream_returns_sse(client):
    """GET /api/osint/investigate/{job_id}/stream returns text/event-stream."""
    assert False, "implement in Plan 51-04"


@_skip
def test_spiderfoot_health_in_system_health(client):
    """GET /health response includes spiderfoot key."""
    assert False, "implement in Plan 51-04"
