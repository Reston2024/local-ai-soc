"""
Phase 50 Wave 0 stub: MISP API endpoint tests.
test_misp_events_endpoint fails until Plan 50-03 adds /api/intel/misp-events.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

try:
    from backend.api import intel as intel_api
    _INTEL_API_AVAILABLE = True
except ImportError:
    _INTEL_API_AVAILABLE = False


@pytest.mark.skipif(not _INTEL_API_AVAILABLE, reason="Wave 0 stub — intel API not importable")
def test_misp_events_endpoint():
    """GET /api/intel/misp-events returns 200 with list of MISP-sourced IOC dicts."""
    from fastapi.testclient import TestClient
    from backend.main import create_app

    app = create_app()
    ioc_mock = MagicMock()
    ioc_mock.list_misp_iocs.return_value = [
        {
            "ioc_value": "10.0.0.1",
            "ioc_type": "ip",
            "confidence": 70,
            "feed_source": "misp",
            "extra_json": '{"misp_event_id": "42", "misp_tags": ["tlp:white"]}',
        }
    ]
    app.state.ioc_store = ioc_mock

    # Override auth for test
    from backend.core.auth import verify_token
    from backend.core.rbac import OperatorContext
    app.dependency_overrides[verify_token] = lambda: OperatorContext(
        operator_id="test", username="test", role="analyst"
    )

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/intel/misp-events")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
