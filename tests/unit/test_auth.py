from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


@pytest.mark.asyncio
async def test_valid_token_passes():
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = "testtoken"
        from backend.core.auth import verify_token
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="testtoken")
        await verify_token(credentials=creds)  # must not raise


@pytest.mark.asyncio
async def test_missing_token_returns_401():
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = "testtoken"
        from backend.core.auth import verify_token
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(credentials=None)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_wrong_token_returns_401():
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = "testtoken"
        from backend.core.auth import verify_token
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrongtoken")
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(credentials=creds)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_empty_token_raises_401():
    """Empty AUTH_TOKEN is misconfiguration — must reject all requests, not bypass auth."""
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = ""
        from backend.core.auth import verify_token
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(credentials=None)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_changeme_default_enforces_auth():
    """AUTH_TOKEN='changeme' (new default) must require a valid token — no bypass."""
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = "changeme"
        from backend.core.auth import verify_token
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(credentials=None)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_whitespace_only_token_raises_401():
    """Whitespace-only AUTH_TOKEN is treated as empty (misconfiguration) — 401 for all."""
    with patch("backend.core.auth.settings") as mock_settings:
        mock_settings.AUTH_TOKEN = "   "
        from backend.core.auth import verify_token
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(credentials=None)
        assert exc_info.value.status_code == 401


class TestOperatorLookup:
    @pytest.mark.asyncio
    async def test_operator_lookup_valid(self):
        """verify_token returns OperatorContext for a valid named operator key."""
        pytest.fail("NOT IMPLEMENTED")

    @pytest.mark.asyncio
    async def test_legacy_token_fallback(self):
        """verify_token falls back to AUTH_TOKEN when operators table is empty."""
        pytest.fail("NOT IMPLEMENTED")

    @pytest.mark.asyncio
    async def test_state_injection(self):
        """request.state.operator is set after successful verify_token."""
        pytest.fail("NOT IMPLEMENTED")

    @pytest.mark.asyncio
    async def test_no_token_401(self):
        """No bearer token and no ?token= → 401 (not 403)."""
        pytest.fail("NOT IMPLEMENTED")


class TestAuditAttribution:
    @pytest.mark.asyncio
    async def test_operator_id_in_audit(self):
        """OllamaClient.generate() emits operator_id in llm_audit log extra."""
        pytest.fail("NOT IMPLEMENTED")
