"""
Wave 0 test stubs for Phase 34 Attack API endpoints.
P34-T03 / P34-T04 — GET /api/attack/coverage, GET /api/attack/actor-matches.

Uses FastAPI TestClient with mocked stores — no real disk I/O.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing the attack router — skip if not yet implemented
# ---------------------------------------------------------------------------
try:
    from backend.api import attack as attack_api  # noqa: F401
    _ATTACK_API_AVAILABLE = True
except ImportError:
    _ATTACK_API_AVAILABLE = False

# ---------------------------------------------------------------------------
# Try importing create_app — skip whole file if main not loadable
# ---------------------------------------------------------------------------
try:
    from backend.main import create_app  # noqa: F401
    _APP_AVAILABLE = True
except ImportError:
    _APP_AVAILABLE = False

_AVAILABLE = _ATTACK_API_AVAILABLE and _APP_AVAILABLE


# ---------------------------------------------------------------------------
# Stub AttackStore
# ---------------------------------------------------------------------------

class StubAttackStore:
    """Minimal in-memory AttackStore for testing — no SQLite required."""

    def __init__(self):
        pass

    def actor_matches(self, tech_ids: list[str]) -> list[dict]:
        return []

    def technique_count(self) -> int:
        return 1

    def list_techniques_by_tactic(self, tactic: str) -> list[dict]:
        return [{"tech_id": "T1059", "name": "Command and Scripting Interpreter"}]


# ---------------------------------------------------------------------------
# App builder helper
# ---------------------------------------------------------------------------

def _build_attack_app(attack_store_mock=None, authed: bool = True):
    """Build a minimal FastAPI app with attack router for testing."""
    from fastapi.testclient import TestClient

    from backend.core.auth import verify_token
    from backend.core.rbac import OperatorContext
    from backend.main import create_app

    app = create_app()

    # Inject app.state.attack_store
    store = attack_store_mock if attack_store_mock is not None else StubAttackStore()
    app.state.attack_store = store

    # Inject other required state
    app.state.stores = MagicMock()
    app.state.ollama = MagicMock()
    app.state.settings = MagicMock()
    app.state.asset_store = MagicMock()
    app.state.ioc_store = MagicMock()

    if authed:
        _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
        app.dependency_overrides[verify_token] = lambda: _ctx

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# test_coverage_endpoint
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Plan 03")
def test_coverage_endpoint():
    """GET /api/attack/coverage returns 200 with per-tactic structure."""
    with patch(
        "backend.api.attack.scan_rules_dir_for_coverage",
        return_value={"T1059": ["Test Rule"]},
    ):
        client = _build_attack_app(authed=True)
        resp = client.get("/api/attack/coverage")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert "tactic" in item
        assert "total_techniques" in item
        assert "covered_count" in item
        assert "techniques" in item
        assert isinstance(item["techniques"], list)


# ---------------------------------------------------------------------------
# test_actor_matches_endpoint
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Plan 03")
def test_actor_matches_endpoint():
    """GET /api/attack/actor-matches returns 200 with list (may be empty)."""
    client = _build_attack_app(authed=True)
    resp = client.get("/api/attack/actor-matches")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for item in data:
        assert "name" in item
        assert "confidence" in item
        assert "overlap_pct" in item


# ---------------------------------------------------------------------------
# test_coverage_unauthenticated
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Plan 03")
def test_coverage_unauthenticated():
    """GET /api/attack/coverage without auth header → 401 or 403."""
    client = _build_attack_app(authed=False)
    resp = client.get("/api/attack/coverage")
    assert resp.status_code in (401, 403, 422)


# ---------------------------------------------------------------------------
# test_actor_matches_unauthenticated
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _AVAILABLE, reason="Wave 0 stub — implementation in Plan 03")
def test_actor_matches_unauthenticated():
    """GET /api/attack/actor-matches without auth header → 401 or 403."""
    client = _build_attack_app(authed=False)
    resp = client.get("/api/attack/actor-matches")
    assert resp.status_code in (401, 403, 422)
