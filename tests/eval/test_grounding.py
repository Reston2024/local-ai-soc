"""Eval tests for P22-T01: Response grounding threading."""
from __future__ import annotations

import re
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

_AUTH_TOKEN = "grounding-test-token"
_AUTH_HEADERS = {"Authorization": f"Bearer {_AUTH_TOKEN}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def _build_client(chroma_ids: list[str] | None = None):
    """Build a TestClient with mocked ollama and chroma stores, auth patched."""
    from fastapi.testclient import TestClient

    from backend.core.deps import Stores
    from backend.main import create_app

    if chroma_ids is None:
        chroma_ids = ["evt-001", "evt-002"]

    chroma_docs = [f"event doc {i}" for i in range(len(chroma_ids))]

    duckdb = MagicMock()
    duckdb.fetch_all = AsyncMock(return_value=[])
    duckdb.fetch_df = AsyncMock(return_value=[])
    duckdb.execute_write = AsyncMock(return_value=None)

    chroma = MagicMock()
    chroma.query_async = AsyncMock(return_value={
        "ids": [chroma_ids],
        "distances": [[0.1] * len(chroma_ids)],
        "documents": [chroma_docs],
        "metadatas": [[{}] * len(chroma_ids)],
    })

    sqlite = MagicMock()
    sqlite.get_operator_by_prefix = MagicMock(return_value=None)
    sqlite.record_llm_provenance = MagicMock(return_value=None)

    stores = Stores(duckdb=duckdb, chroma=chroma, sqlite=sqlite)

    _audit_id = str(uuid.uuid4())

    async def _generate_side_effect(
        prompt,
        *,
        system=None,
        grounding_event_ids=None,
        out_context=None,
        operator_id="system",
        **kwargs,
    ):
        if out_context is not None:
            out_context["audit_id"] = _audit_id
            out_context["grounding_event_ids"] = grounding_event_ids or []
        return "Test answer."

    app = create_app()
    app.state.stores = stores

    ollama = MagicMock()
    ollama.embed = AsyncMock(return_value=[0.1] * 128)
    ollama.generate = AsyncMock(side_effect=_generate_side_effect)
    app.state.ollama = ollama
    app.state.settings = MagicMock()

    # Bypass auth with dependency override — legacy token path is now TOTP-gated.
    # Grounding eval tests test response logic, not auth mechanics.
    from backend.core.auth import verify_token
    from backend.core.rbac import OperatorContext
    _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
    app.dependency_overrides[verify_token] = lambda: _ctx

    client = TestClient(app, raise_server_exceptions=True)
    yield client, _audit_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_grounding_event_ids_in_response():
    """audit_id and grounding_event_ids appear in /ask JSON response."""
    with _build_client(chroma_ids=["evt-001", "evt-002"]) as (client, audit_id):
        resp = client.post(
            "/api/query/ask",
            json={"question": "What happened?"},
            headers=_AUTH_HEADERS,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "audit_id" in data, f"audit_id missing from response: {list(data.keys())}"
        assert "grounding_event_ids" in data, f"grounding_event_ids missing: {list(data.keys())}"
        assert "is_grounded" in data, f"is_grounded missing: {list(data.keys())}"
        assert data["audit_id"] == audit_id
        assert set(data["grounding_event_ids"]) == {"evt-001", "evt-002"}
        assert data["is_grounded"] is True


def test_ungrounded_response():
    """is_grounded=False when context_event_ids is empty."""
    with _build_client(chroma_ids=[]) as (client, _):
        resp = client.post(
            "/api/query/ask",
            json={"question": "Empty context?"},
            headers=_AUTH_HEADERS,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["is_grounded"] is False
        assert data["grounding_event_ids"] == []


def test_audit_id_is_uuid():
    """audit_id in response is a valid UUID string."""
    with _build_client() as (client, _):
        resp = client.post(
            "/api/query/ask",
            json={"question": "UUID check?"},
            headers=_AUTH_HEADERS,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        audit_id = data.get("audit_id", "")
        assert audit_id, "audit_id should be non-empty"
        assert re.match(r"^[0-9a-f-]{36}$", audit_id), (
            f"audit_id '{audit_id}' does not look like a UUID4"
        )
