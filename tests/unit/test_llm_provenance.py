"""Tests for P21-T03: LLM audit provenance.

Task 1 covers: llm_audit_provenance table creation, record/get methods, TEMPLATE_SHA256.
Task 2 covers: audit_id threading through generate() and stream_generate().
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.provenance import LlmProvenanceRecord
from backend.stores.sqlite_store import SQLiteStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> SQLiteStore:
    """In-memory SQLiteStore for unit tests."""
    return SQLiteStore(":memory:")


# ---------------------------------------------------------------------------
# Task 1 tests
# ---------------------------------------------------------------------------


def test_llm_provenance_table_exists(store: SQLiteStore) -> None:
    """SQLiteStore creates llm_audit_provenance table on init."""
    cursor = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='llm_audit_provenance'"
    )
    row = cursor.fetchone()
    assert row is not None, "llm_audit_provenance table must exist after SQLiteStore init"


def test_llm_provenance_written(store: SQLiteStore) -> None:
    """generate() writes a row with audit_id, prompt_template_sha256, and grounding_event_ids."""
    from backend.services.ollama_client import OllamaClient

    async def _run() -> None:
        client = OllamaClient(sqlite_store=store)

        # Patch the HTTP call
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"response": "test response text"})

        with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await client.generate(
                prompt="explain T1059",
                prompt_template_name="analyst_qa",
                prompt_template_sha256="a" * 64,
                grounding_event_ids=["evt-001", "evt-002"],
                operator_id="op-test",
            )

        await client.close()

        # Exactly one row must exist
        rows = store._conn.execute(
            "SELECT * FROM llm_audit_provenance"
        ).fetchall()
        assert len(rows) == 1, f"Expected 1 provenance row, got {len(rows)}"

        row = dict(rows[0])
        assert row["prompt_template_name"] == "analyst_qa"
        assert row["prompt_template_sha256"] == "a" * 64
        assert row["operator_id"] == "op-test"
        assert row["grounding_event_ids"] is not None

        # grounding_event_ids stored as JSON
        import json
        ids = json.loads(row["grounding_event_ids"])
        assert ids == ["evt-001", "evt-002"]

    asyncio.get_event_loop().run_until_complete(_run())


def test_llm_provenance_no_duplicate_rows(store: SQLiteStore) -> None:
    """Only one provenance row is written per logical LLM call, not per streaming chunk."""
    from backend.services.ollama_client import OllamaClient

    async def _run() -> None:
        client = OllamaClient(sqlite_store=store)

        # stream_generate uses client.stream — patch it
        with patch.object(client._client, "stream") as mock_stream_ctx:
            # Build an async context manager that yields lines
            async def _aiter_lines():
                import json as _json
                yield _json.dumps({"response": "hello", "done": False})
                yield _json.dumps({"response": " world", "done": True})

            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.aiter_lines = _aiter_lines

            mock_stream_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_stream_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            await client.stream_generate(
                prompt="summarise alert",
                prompt_template_name="analyst_qa",
                prompt_template_sha256="b" * 64,
                grounding_event_ids=["evt-003"],
                operator_id="op-stream",
            )

        await client.close()

        rows = store._conn.execute(
            "SELECT * FROM llm_audit_provenance"
        ).fetchall()
        assert len(rows) == 1, (
            f"Expected exactly 1 provenance row from stream_generate, got {len(rows)}"
        )

    asyncio.get_event_loop().run_until_complete(_run())


def test_llm_provenance_api() -> None:
    """GET /api/provenance/llm/{audit_id} returns 200 with model_id and response_sha256."""
    from fastapi.testclient import TestClient
    from backend.main import create_app
    from backend.core.deps import get_stores, Stores
    from backend.stores.duckdb_store import DuckDBStore
    from backend.stores.chroma_store import ChromaStore

    sqlite_store = SQLiteStore(":memory:")

    # Pre-insert a known provenance row
    import json as _json
    audit_id = "test-audit-001"
    sqlite_store.record_llm_provenance(
        audit_id=audit_id,
        model_id="qwen3:14b",
        prompt_template_name="analyst_qa",
        prompt_template_sha256="c" * 64,
        response_sha256="d" * 64,
        grounding_event_ids=["evt-100"],
        operator_id="op-api-test",
    )

    app = create_app()

    # Override get_stores dependency
    mock_duckdb = MagicMock(spec=DuckDBStore)
    mock_chroma = MagicMock(spec=ChromaStore)
    stores_override = Stores(duckdb=mock_duckdb, chroma=mock_chroma, sqlite=sqlite_store)

    app.dependency_overrides[get_stores] = lambda: stores_override

    with TestClient(app) as client:
        resp = client.get(f"/api/provenance/llm/{audit_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["audit_id"] == audit_id
        assert data["model_id"] == "qwen3:14b"
        assert data["response_sha256"] == "d" * 64
        assert data["grounding_event_ids"] == ["evt-100"]
