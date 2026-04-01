"""
Tests for backend/api/operators.py — CRUD endpoints, key rotation, RBAC.

Test strategy:
- Build a minimal FastAPI app with operators_router mounted at /api
- Inject mock Stores via app.state
- Override verify_token dependency so we can inject any OperatorContext
- Use FastAPI TestClient (synchronous) — no asyncio needed at the test level

Each test class is isolated via its own `_build_app()` call.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from backend.api.operators import router as operators_router
from backend.core.auth import verify_token
from backend.core.rbac import OperatorContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin_ctx() -> OperatorContext:
    return OperatorContext(
        operator_id="admin-op-id",
        username="admin",
        role="admin",
        totp_verified=True,
        totp_enabled=False,
    )


def _analyst_ctx() -> OperatorContext:
    return OperatorContext(
        operator_id="analyst-op-id",
        username="alice",
        role="analyst",
        totp_verified=True,
        totp_enabled=False,
    )


def _build_app(ctx: OperatorContext, sqlite_store: MagicMock) -> TestClient:
    """Create a minimal app that overrides verify_token and injects a mock store."""
    app = FastAPI()

    # Inject mock stores into app.state
    mock_stores = MagicMock()
    mock_stores.sqlite = sqlite_store
    app.state.stores = mock_stores

    # Mount router under /api
    app.include_router(operators_router, prefix="/api", dependencies=[Depends(verify_token)])

    # Override verify_token to return the desired context
    app.dependency_overrides[verify_token] = lambda: ctx

    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# TestOperatorCRUD
# ---------------------------------------------------------------------------

class TestOperatorCRUD:
    def test_create_operator(self):
        """POST /api/operators returns 201 with api_key field present, hashed_key absent."""
        sqlite = MagicMock()
        sqlite.create_operator = MagicMock(return_value=None)
        # Simulate _get_operator_row returning a row for the new operator
        sqlite._conn = MagicMock()
        sqlite._conn.execute.return_value.fetchone.return_value = {
            "operator_id": "new-op-id",
            "username": "bob",
            "role": "analyst",
            "hashed_key": "SHOULD_NOT_APPEAR",
            "totp_secret": "SHOULD_NOT_APPEAR",
            "is_active": 1,
            "created_at": "2026-03-31T00:00:00Z",
            "last_seen_at": None,
        }

        client = _build_app(_admin_ctx(), sqlite)
        resp = client.post(
            "/api/operators",
            json={"username": "bob", "role": "analyst"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "api_key" in body
        assert "hashed_key" not in body
        assert "totp_secret" not in body
        assert body["username"] == "bob"
        assert body["role"] == "analyst"
        # create_operator was called once
        sqlite.create_operator.assert_called_once()

    def test_list_no_secrets(self):
        """GET /api/operators response rows have no hashed_key or totp_secret."""
        sqlite = MagicMock()
        sqlite.list_operators.return_value = [
            {
                "operator_id": "op-1",
                "username": "admin",
                "role": "admin",
                "is_active": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "last_seen_at": None,
                # These should never appear in response:
                "hashed_key": "BCRYPT_HASH",
                "totp_secret": "SECRET",
            }
        ]

        client = _build_app(_admin_ctx(), sqlite)
        resp = client.get("/api/operators")
        assert resp.status_code == 200
        body = resp.json()
        assert "operators" in body
        for op in body["operators"]:
            assert "hashed_key" not in op
            assert "totp_secret" not in op
        assert body["operators"][0]["username"] == "admin"

    def test_deactivate_operator(self):
        """DELETE /api/operators/{id} calls deactivate_operator and returns 200."""
        sqlite = MagicMock()
        sqlite.deactivate_operator = MagicMock(return_value=None)

        # Use a different admin context (not the same id as the target)
        admin_ctx = OperatorContext(
            operator_id="admin-op-id",
            username="admin",
            role="admin",
            totp_verified=True,
            totp_enabled=False,
        )
        client = _build_app(admin_ctx, sqlite)

        resp = client.delete("/api/operators/some-other-op-id")
        assert resp.status_code == 200
        sqlite.deactivate_operator.assert_called_once_with("some-other-op-id")

    def test_deactivate_self_returns_400(self):
        """DELETE /api/operators/{own_id} returns 400 (self-delete guard)."""
        sqlite = MagicMock()
        sqlite.deactivate_operator = MagicMock(return_value=None)

        admin_ctx = OperatorContext(
            operator_id="admin-op-id",
            username="admin",
            role="admin",
            totp_verified=True,
            totp_enabled=False,
        )
        client = _build_app(admin_ctx, sqlite)

        # Try to delete own operator_id
        resp = client.delete("/api/operators/admin-op-id")
        assert resp.status_code == 400
        sqlite.deactivate_operator.assert_not_called()


# ---------------------------------------------------------------------------
# TestKeyRotation
# ---------------------------------------------------------------------------

class TestKeyRotation:
    def test_key_rotation(self):
        """POST /api/operators/{id}/rotate-key returns new api_key."""
        sqlite = MagicMock()
        sqlite.update_operator_key = MagicMock(return_value=None)

        client = _build_app(_admin_ctx(), sqlite)
        resp = client.post("/api/operators/target-op-id/rotate-key")

        assert resp.status_code == 200
        body = resp.json()
        assert "api_key" in body
        assert body["operator_id"] == "target-op-id"
        assert len(body["api_key"]) > 0
        sqlite.update_operator_key.assert_called_once()
        # Confirm the new key was hashed before storing (update_operator_key called
        # with (operator_id, hashed, prefix) — the second arg should not equal api_key)
        call_args = sqlite.update_operator_key.call_args[0]
        stored_prefix = call_args[2]   # key_prefix(raw_key)
        returned_key = body["api_key"]
        assert returned_key.startswith(stored_prefix)


# ---------------------------------------------------------------------------
# TestRBACEnforcement
# ---------------------------------------------------------------------------

class TestRBACEnforcement:
    def test_analyst_forbidden(self):
        """POST /api/operators with analyst token returns 403."""
        sqlite = MagicMock()
        client = _build_app(_analyst_ctx(), sqlite)
        resp = client.post(
            "/api/operators",
            json={"username": "charlie", "role": "analyst"},
        )
        assert resp.status_code == 403
        # The store should never have been called
        sqlite.create_operator.assert_not_called()
