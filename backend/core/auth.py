"""Bearer token authentication dependency for FastAPI routes.

When AUTH_TOKEN is empty string, ALL requests are rejected (misconfiguration guard).
To disable auth for local dev: set AUTH_TOKEN=dev-only-bypass in .env explicitly.

The default AUTH_TOKEN is "changeme" — auth is ON in all environments unless
the operator explicitly overrides AUTH_TOKEN in .env or the environment.

To enable auth with a strong token:
    python -c "import secrets; print(secrets.token_hex(32))"
and set AUTH_TOKEN=<token> in .env.
"""
from fastapi import HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.config import settings

_bearer = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    token: str | None = Query(default=None),
) -> None:
    """FastAPI dependency: validate Authorization: Bearer <token> or ?token= query param.

    The query param fallback is required for browser-initiated binary downloads
    (PDF, ZIP) where the browser opens a URL directly and cannot set headers.

    Rejects all requests when AUTH_TOKEN is empty or whitespace — this is
    treated as misconfiguration to prevent accidental open-access deployment.
    """
    configured = settings.AUTH_TOKEN.strip()
    if not configured:
        raise HTTPException(status_code=401, detail="Auth misconfigured: AUTH_TOKEN is empty")
    # Accept token from Bearer header OR ?token= query param
    bearer_token = credentials.credentials if credentials is not None else None
    if bearer_token == configured or token == configured:
        return
    raise HTTPException(status_code=401, detail="Unauthorized")
