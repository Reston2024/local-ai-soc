import asyncio
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.receipts import router as receipts_router

VALID_BODY = {
    "schema_version": "1.0.0-stub",
    "receipt_id": "11111111-1111-1111-1111-111111111111",
    "recommendation_id": "22222222-2222-2222-2222-222222222222",
    "case_id": "33333333-3333-3333-3333-333333333333",
    "failure_taxonomy": "applied",
    "executed_at": "2026-04-06T00:00:00Z",
}


@pytest.fixture()
def mock_duckdb() -> AsyncMock:
    db = AsyncMock()
    db.execute_write = AsyncMock(return_value=None)
    db.fetch_all = AsyncMock(return_value=[])
    return db


@pytest.fixture()
def mock_sqlite() -> MagicMock:
    store = MagicMock()
    store.update_investigation_case = MagicMock(return_value=None)
    return store


@pytest.fixture()
def client(mock_duckdb, mock_sqlite) -> TestClient:
    app = FastAPI()
    stores = MagicMock()
    stores.duckdb = mock_duckdb
    stores.sqlite = mock_sqlite
    app.state.stores = stores
    app.include_router(receipts_router)
    return TestClient(app, raise_server_exceptions=True)


def test_post_receipt_valid_returns_202(client):
    """P25-T01: POST /api/receipts with valid body returns 202 Accepted."""
    resp = client.post("/api/receipts", json=VALID_BODY)
    assert resp.status_code == 202
    assert resp.json()["receipt_id"] == VALID_BODY["receipt_id"]


def test_post_receipt_invalid_body_returns_422(client):
    """P25-T01: POST /api/receipts with invalid body returns 422."""
    resp = client.post("/api/receipts", json={"garbage": True})
    assert resp.status_code == 422


def test_post_receipt_stores_in_duckdb(client, mock_duckdb):
    """P25-T01: execute_write called with INSERT INTO execution_receipts."""
    client.post("/api/receipts", json=VALID_BODY)
    assert mock_duckdb.execute_write.called
    first_call_sql = mock_duckdb.execute_write.call_args_list[0][0][0]
    assert "execution_receipts" in first_call_sql


def test_case_state_propagated(client, mock_sqlite):
    """P25-T02: update_investigation_case called with correct status after receipt ingest."""
    client.post("/api/receipts", json=VALID_BODY)
    mock_sqlite.update_investigation_case.assert_called_once_with(
        VALID_BODY["case_id"],
        {"case_status": "containment_confirmed"},
    )


def test_duplicate_receipt_returns_409(client, mock_duckdb):
    """P25-T05: Same receipt_id posted twice returns 409 Conflict."""
    mock_duckdb.execute_write = AsyncMock(
        side_effect=[None, Exception("PRIMARY KEY constraint violated")]
    )
    client.post("/api/receipts", json=VALID_BODY)
    resp = client.post("/api/receipts", json=VALID_BODY)
    assert resp.status_code == 409
