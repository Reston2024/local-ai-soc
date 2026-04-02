"""Tests for P21-T02: detection provenance.

Tests are structured in RED→GREEN order following TDD workflow.
"""
import asyncio
from uuid import uuid4

import pytest

from backend.models.provenance import DetectionProvenanceRecord
from backend.stores.sqlite_store import SQLiteStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store() -> SQLiteStore:
    """Return an in-memory SQLiteStore for test isolation."""
    return SQLiteStore(":memory:")


# ---------------------------------------------------------------------------
# Task 1: detection_provenance table DDL + methods
# ---------------------------------------------------------------------------


def test_detection_provenance_table_exists():
    """SQLiteStore creates detection_provenance table on init."""
    store = _make_store()
    row = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='detection_provenance'"
    ).fetchone()
    assert row is not None, "detection_provenance table must exist after SQLiteStore init"


# ---------------------------------------------------------------------------
# Task 2: SigmaMatcher writes provenance; API endpoint reads it back
# ---------------------------------------------------------------------------


def test_detection_provenance_fields():
    """Detection provenance row contains pySigma version, rule_sha256, and field_map_version."""
    store = _make_store()
    detection_id = str(uuid4())
    prov_id = str(uuid4())

    store.record_detection_provenance(
        prov_id=prov_id,
        detection_id=detection_id,
        rule_id="test-rule-id",
        rule_title="Test Rule",
        rule_sha256="a" * 64,
        pysigma_version="1.2.0",
        field_map_version="20",
        operator_id=None,
    )

    row = store.get_detection_provenance(detection_id)
    assert row is not None, "get_detection_provenance must return a dict after insert"
    assert len(row["rule_sha256"]) == 64, "rule_sha256 must be 64-char hex"
    assert row["pysigma_version"] == "1.2.0"
    assert row["field_map_version"] == "20"


def test_detection_provenance_api():
    """GET /api/provenance/detection/{id} returns 200 with rule_sha256 and pysigma_version."""
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock, patch

    detection_id = str(uuid4())
    prov_id = str(uuid4())

    mock_store = _make_store()
    mock_store.record_detection_provenance(
        prov_id=prov_id,
        detection_id=detection_id,
        rule_id="test-rule-id",
        rule_title="Test Rule",
        rule_sha256="b" * 64,
        pysigma_version="1.2.0",
        field_map_version="20",
        operator_id=None,
    )

    from backend.api.provenance import router as provenance_router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(provenance_router)

    # Patch get_stores dependency to return our mock stores
    from backend.core.deps import get_stores

    mock_stores = MagicMock()
    mock_stores.sqlite = mock_store

    app.dependency_overrides[get_stores] = lambda: mock_stores

    client = TestClient(app)
    resp = client.get(f"/api/provenance/detection/{detection_id}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["rule_sha256"] == "b" * 64
    assert data["pysigma_version"] == "1.2.0"
