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
