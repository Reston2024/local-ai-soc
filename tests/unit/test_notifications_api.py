from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.notifications import router as notifications_router
from backend.api.receipts import router as receipts_router

BASE_BODY = {
    "schema_version": "1.0.0-stub",
    "receipt_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "recommendation_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "case_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
    "executed_at": "2026-04-06T00:00:00Z",
}


def _make_client(mock_duckdb, mock_sqlite) -> TestClient:
    app = FastAPI()
    stores = MagicMock()
    stores.duckdb = mock_duckdb
    stores.sqlite = mock_sqlite
    app.state.stores = stores
    app.include_router(receipts_router)
    app.include_router(notifications_router)
    return TestClient(app, raise_server_exceptions=True)


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


def _post(client, failure_taxonomy: str, receipt_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"):
    body = {**BASE_BODY, "failure_taxonomy": failure_taxonomy, "receipt_id": receipt_id}
    return client.post("/api/receipts", json=body)


def test_validation_failed_emits_notification(mock_duckdb, mock_sqlite):
    """P25-T03: failure_taxonomy='validation_failed' emits notification with required_action='manual_review_required'."""
    client = _make_client(mock_duckdb, mock_sqlite)
    resp = _post(client, "validation_failed")
    assert resp.status_code == 202
    # At least 2 execute_write calls: receipt + notification
    assert mock_duckdb.execute_write.call_count >= 2
    notif_calls = [c for c in mock_duckdb.execute_write.call_args_list if "notifications" in c[0][0]]
    assert len(notif_calls) == 1
    assert "manual_review_required" in notif_calls[0][0][1]


def test_rolled_back_emits_notification(mock_duckdb, mock_sqlite):
    """P25-T03: failure_taxonomy='rolled_back' emits notification with required_action='manual_review_required'."""
    client = _make_client(mock_duckdb, mock_sqlite)
    resp = _post(client, "rolled_back")
    assert resp.status_code == 202
    notif_calls = [c for c in mock_duckdb.execute_write.call_args_list if "notifications" in c[0][0]]
    assert len(notif_calls) == 1
    assert "manual_review_required" in notif_calls[0][0][1]


def test_expired_rejected_emits_notification(mock_duckdb, mock_sqlite):
    """P25-T03: failure_taxonomy='expired_rejected' emits notification with required_action='re_approve_required'."""
    client = _make_client(mock_duckdb, mock_sqlite)
    resp = _post(client, "expired_rejected")
    assert resp.status_code == 202
    notif_calls = [c for c in mock_duckdb.execute_write.call_args_list if "notifications" in c[0][0]]
    assert len(notif_calls) == 1
    assert "re_approve_required" in notif_calls[0][0][1]


def test_applied_no_notification(mock_duckdb, mock_sqlite):
    """P25-T03: failure_taxonomy='applied' does NOT emit a notification."""
    client = _make_client(mock_duckdb, mock_sqlite)
    _post(client, "applied")
    notif_calls = [c for c in mock_duckdb.execute_write.call_args_list if "notifications" in c[0][0]]
    assert len(notif_calls) == 0


def test_noop_no_notification(mock_duckdb, mock_sqlite):
    """P25-T03: failure_taxonomy='noop_already_present' does NOT emit a notification."""
    client = _make_client(mock_duckdb, mock_sqlite)
    _post(client, "noop_already_present")
    notif_calls = [c for c in mock_duckdb.execute_write.call_args_list if "notifications" in c[0][0]]
    assert len(notif_calls) == 0


def test_get_notifications_returns_pending(mock_duckdb, mock_sqlite):
    """P25-T03: GET /api/notifications returns list of pending notifications."""
    mock_duckdb.fetch_all = AsyncMock(
        return_value=[
            (
                "dddddddd-dddd-dddd-dddd-dddddddddddd",
                "cccccccc-cccc-cccc-cccc-cccccccccccc",
                "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "manual_review_required",
                "pending",
                "2026-04-06T00:00:00+00:00",
            )
        ]
    )
    client = _make_client(mock_duckdb, mock_sqlite)
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert "notifications" in data
    assert len(data["notifications"]) == 1
    assert data["notifications"][0]["required_action"] == "manual_review_required"
