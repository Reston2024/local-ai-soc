"""Stub tests for phase-26 graph schema versioning.

Covers:
- P26-T01: system_kv seeding of graph_schema_version on SQLiteStore init
           and GET /api/graph/schema-version endpoint
- P26-T04: INSERT OR IGNORE idempotency (no clobbering existing version)
           and additive-only column guard for entities/edges tables

All tests are skipped (wave-0 stubs) and will be activated in plan 26-05.
"""

import pytest
import sqlite3
from pathlib import Path

pytestmark = pytest.mark.skip(reason="wave-0 stub — activate in plan 26-05")

from backend.stores.sqlite_store import SQLiteStore


# ---------------------------------------------------------------------------
# Helpers (mirroring test_graph_api.py _build_app pattern)
# ---------------------------------------------------------------------------


def _build_app(tmp_path):
    """Build a TestClient backed by a real SQLiteStore (mirrors test_graph_api.py)."""
    from unittest.mock import AsyncMock, MagicMock
    from fastapi.testclient import TestClient
    from backend.core.auth import verify_token
    from backend.core.deps import Stores
    from backend.core.rbac import OperatorContext
    from backend.main import create_app

    duckdb = MagicMock()
    duckdb.fetch_all = AsyncMock(return_value=[])
    duckdb.fetch_df = AsyncMock(return_value=[])
    duckdb.execute_write = AsyncMock(return_value=None)

    chroma = MagicMock()
    chroma.query_async = AsyncMock(return_value={
        "ids": [[]], "distances": [[]], "documents": [[]], "metadatas": [[]]
    })

    sqlite = SQLiteStore(str(tmp_path))
    stores = Stores(duckdb=duckdb, chroma=chroma, sqlite=sqlite)

    app = create_app()
    app.state.stores = stores
    app.state.ollama = MagicMock()
    app.state.ollama.embed = AsyncMock(return_value=[0.1] * 128)
    app.state.settings = MagicMock()

    _ctx = OperatorContext(operator_id="test-admin", username="test", role="admin")
    app.dependency_overrides[verify_token] = lambda: _ctx

    client = TestClient(app, raise_server_exceptions=False)
    return client, sqlite


# ---------------------------------------------------------------------------
# P26-T01: version seeding
# ---------------------------------------------------------------------------


def test_fresh_install_gets_version_2(tmp_path):
    """A brand-new SQLiteStore (empty entities table) must seed version 2.0.0 (P26-T01).

    get_graph_schema_version() does not exist yet; stub will fail at activation
    if not implemented on SQLiteStore.
    """
    store = SQLiteStore(str(tmp_path))
    version = store.get_graph_schema_version()
    assert version == "2.0.0", (
        f"Expected '2.0.0' for fresh install, got {version!r}"
    )


def test_preexisting_install_gets_version_1(tmp_path):
    """A SQLiteStore with pre-existing rows must report schema version 1.0.0 (P26-T01).

    Simulates an upgrade scenario where entities already exist.
    """
    db_path = tmp_path / "graph.db"

    # Bootstrap the schema by creating a store first
    SQLiteStore(str(tmp_path))

    # Insert a pre-existing entity row directly to simulate an old install
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO entities (id, type, name, attributes, case_id, created_at) "
        "VALUES ('old-ent-001', 'host', 'legacy-host', '{}', NULL, '2025-01-01T00:00:00Z')"
    )
    conn.commit()
    conn.close()

    # A second store pointing at the same file should detect existing data
    store2 = SQLiteStore(str(tmp_path))
    version = store2.get_graph_schema_version()
    assert version == "1.0.0", (
        f"Expected '1.0.0' for pre-existing install, got {version!r}"
    )


def test_schema_version_endpoint(tmp_path):
    """GET /api/graph/schema-version must return 200 with graph_schema_version string (P26-T01)."""
    client, _ = _build_app(tmp_path)
    resp = client.get("/api/graph/schema-version")
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code} — endpoint may not exist yet"
    )
    body = resp.json()
    assert "graph_schema_version" in body, (
        f"Response missing 'graph_schema_version' key: {body!r}"
    )
    assert isinstance(body["graph_schema_version"], str)
    assert len(body["graph_schema_version"]) > 0, "graph_schema_version must be non-empty"


# ---------------------------------------------------------------------------
# P26-T04: INSERT OR IGNORE idempotency
# ---------------------------------------------------------------------------


def test_system_kv_not_clobbered(tmp_path):
    """Existing graph_schema_version in system_kv must NOT be overwritten on re-init (P26-T04).

    Relies on INSERT OR IGNORE semantics in the seeding logic.
    """
    db_path = tmp_path / "graph.db"

    # Create first store to bootstrap schema
    SQLiteStore(str(tmp_path))

    # Manually set version to 1.0.0 in system_kv
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR REPLACE INTO system_kv (key, value) VALUES ('graph_schema_version', '1.0.0')"
    )
    conn.commit()
    conn.close()

    # Re-opening the store must NOT overwrite the manually set version
    store2 = SQLiteStore(str(tmp_path))
    version = store2.get_graph_schema_version()
    assert version == "1.0.0", (
        f"system_kv was clobbered — expected '1.0.0', got {version!r}"
    )


# ---------------------------------------------------------------------------
# P26-T04: column guard
# ---------------------------------------------------------------------------


def test_no_columns_removed(tmp_path):
    """Known columns in entities and edges tables must still be present after init (P26-T04).

    Uses PRAGMA table_info() to enumerate actual columns.
    """
    db_path = tmp_path / "graph.db"
    SQLiteStore(str(tmp_path))

    conn = sqlite3.connect(str(db_path))

    entities_cols = {row[1] for row in conn.execute("PRAGMA table_info(entities)")}
    edges_cols = {row[1] for row in conn.execute("PRAGMA table_info(edges)")}

    conn.close()

    expected_entities_cols = {"id", "type", "name", "attributes", "case_id", "created_at"}
    expected_edges_cols = {
        "id", "source_type", "source_id", "edge_type", "target_type", "target_id",
        "properties", "created_at",
    }

    missing_entities = expected_entities_cols - entities_cols
    assert not missing_entities, (
        f"Columns removed from entities table: {missing_entities!r}"
    )

    missing_edges = expected_edges_cols - edges_cols
    assert not missing_edges, (
        f"Columns removed from edges table: {missing_edges!r}"
    )
