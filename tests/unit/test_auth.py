"""
Tests for backend/core/auth.py — verify_token multi-operator + legacy fallback.

The first 6 tests (legacy path) have been updated to pass a mock Request so the
legacy path activates when the operators table lookup returns None.

New tests cover: named operator lookup, legacy fallback, state injection, 401 cases.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.core.rbac import OperatorContext


def _mock_request(operator_row=None):
    """Build a mock Request whose sqlite store returns operator_row for any prefix lookup."""
    mock_request = MagicMock()
    mock_request.app.state.stores.sqlite.get_operator_by_prefix.return_value = operator_row
    mock_request.app.state.stores.sqlite.update_last_seen = MagicMock()
    mock_request.state = MagicMock()
    return mock_request


# ---------------------------------------------------------------------------
# Legacy path tests (updated to pass mock Request)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_token_passes():
    """A token matching a valid operator row succeeds without TOTP (operator has no totp_secret)."""
    from backend.core.operator_utils import hash_api_key

    raw = "valid-operator-token-1234abcd"
    hashed = hash_api_key(raw)
    operator_row = {
        "operator_id": "op-test",
        "username": "testuser",
        "hashed_key": hashed,
        "role": "analyst",
        "totp_secret": None,
        "is_active": 1,
    }
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = "testtoken"
        mock_settings.LEGACY_TOTP_SECRET = ""
        from backend.core.auth import verify_token
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw)
        req = _mock_request(operator_row=operator_row)
        result = await verify_token(request=req, credentials=creds)
        assert isinstance(result, OperatorContext)
        assert result.operator_id == "op-test"


@pytest.mark.asyncio
async def test_missing_token_returns_401():
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = "testtoken"
        from backend.core.auth import verify_token
        req = _mock_request(operator_row=None)
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(request=req, credentials=None)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_wrong_token_returns_401():
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = "testtoken"
        from backend.core.auth import verify_token
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrongtoken")
        req = _mock_request(operator_row=None)
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(request=req, credentials=creds)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_empty_token_raises_401():
    """Empty AUTH_TOKEN is misconfiguration — must reject all requests, not bypass auth."""
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = ""
        from backend.core.auth import verify_token
        req = _mock_request(operator_row=None)
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(request=req, credentials=None)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_changeme_default_enforces_auth():
    """AUTH_TOKEN='changeme' (new default) must require a valid token — no bypass."""
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = "changeme"
        from backend.core.auth import verify_token
        req = _mock_request(operator_row=None)
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(request=req, credentials=None)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_whitespace_only_token_raises_401():
    """Whitespace-only AUTH_TOKEN is treated as empty (misconfiguration) — 401 for all."""
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = "   "
        from backend.core.auth import verify_token
        req = _mock_request(operator_row=None)
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(request=req, credentials=None)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# New tests: operator lookup path
# ---------------------------------------------------------------------------

class TestOperatorLookup:
    @pytest.mark.asyncio
    async def test_operator_lookup_valid(self):
        """verify_token returns OperatorContext for a valid named operator key."""
        from backend.core.operator_utils import hash_api_key

        raw = "abcdefgh-real-key-1234"
        hashed = hash_api_key(raw)
        operator_row = {
            "operator_id": "op-uuid-123",
            "username": "alice",
            "hashed_key": hashed,
            "role": "analyst",
            "totp_secret": None,
            "is_active": 1,
        }

        with patch("backend.core.auth.settings") as mock_settings:
            mock_settings.AUTH_TOKEN = "changeme"
            from backend.core.auth import verify_token
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw)
            req = _mock_request(operator_row=operator_row)
            result = await verify_token(request=req, credentials=creds)

        assert isinstance(result, OperatorContext)
        assert result.operator_id == "op-uuid-123"
        assert result.operator_id != "legacy-admin"
        assert result.username == "alice"

    @pytest.mark.asyncio
    async def test_legacy_token_fallback(self):
        """Legacy path now requires TOTP — returns 401 when LEGACY_TOTP_SECRET is not configured."""
        with patch("backend.core.auth.settings") as mock_settings:
            mock_settings.AUTH_TOKEN = "my-secret-token"
            mock_settings.LEGACY_TOTP_SECRET = ""  # legacy path disabled — 401 always
            from backend.core.auth import verify_token
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="my-secret-token")
            req = _mock_request(operator_row=None)
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(request=req, credentials=creds)

        assert exc_info.value.status_code == 401
        assert "legacy" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_state_injection(self):
        """After verify_token via operator table, request.state.operator is an OperatorContext."""
        from backend.core.operator_utils import hash_api_key

        raw = "operator-state-inject-test-xyz"
        hashed = hash_api_key(raw)
        operator_row = {
            "operator_id": "op-state-test",
            "username": "stateuser",
            "hashed_key": hashed,
            "role": "analyst",
            "totp_secret": None,
            "is_active": 1,
        }
        with patch("backend.core.auth.settings") as mock_settings:
            mock_settings.AUTH_TOKEN = "my-secret-token"
            mock_settings.LEGACY_TOTP_SECRET = ""
            from backend.core.auth import verify_token
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw)
            req = _mock_request(operator_row=operator_row)
            result = await verify_token(request=req, credentials=creds)

        assert req.state.operator is result
        assert isinstance(req.state.operator, OperatorContext)
        assert result.operator_id == "op-state-test"

    @pytest.mark.asyncio
    async def test_no_token_401(self):
        """No bearer token and no ?token= raises HTTPException(401)."""
        with patch("backend.core.auth.settings") as mock_settings:
            mock_settings.AUTH_TOKEN = "my-secret-token"
            from backend.core.auth import verify_token
            req = _mock_request(operator_row=None)
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(request=req, credentials=None)
            assert exc_info.value.status_code == 401


class TestAuditAttribution:
    @pytest.mark.asyncio
    async def test_operator_id_in_audit(self):
        """OllamaClient.generate() emits operator_id in llm_audit log extra."""
        import logging
        from unittest.mock import AsyncMock, patch
        from backend.services.ollama_client import OllamaClient

        # Capture audit log records
        audit_records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                audit_records.append(record)

        audit_logger = logging.getLogger("llm_audit")
        audit_logger.setLevel(logging.DEBUG)
        handler = _Capture()
        audit_logger.addHandler(handler)

        try:
            client = OllamaClient()
            # Patch the httpx client to avoid real network calls
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {"response": "test answer"}

            with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                await client.generate("test prompt", operator_id="op-uuid-123")
        finally:
            audit_logger.removeHandler(handler)
            await client.close()

        # Find the "start" audit log entry
        start_records = [r for r in audit_records if getattr(r, "event_type", None) == "llm_generate"]
        assert len(start_records) >= 1
        assert any(getattr(r, "operator_id", None) == "op-uuid-123" for r in start_records)
