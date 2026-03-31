"""Bearer token authentication dependency for FastAPI routes.

When AUTH_TOKEN is empty string, ALL requests are rejected (misconfiguration guard).
To disable auth for local dev: set AUTH_TOKEN=dev-only-bypass in .env explicitly.

The default AUTH_TOKEN is "changeme" — auth is ON in all environments unless
the operator explicitly overrides AUTH_TOKEN in .env or the environment.

To enable auth with a strong token:
    python -c "import secrets; print(secrets.token_hex(32))"
and set AUTH_TOKEN=<token> in .env.
"""
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.config import settings

_bearer = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """FastAPI dependency: validate Authorization: Bearer <token>.

    Rejects all requests when AUTH_TOKEN is empty or whitespace — this is
    treated as misconfiguration to prevent accidental open-access deployment.
    """
    configured = settings.AUTH_TOKEN.strip()
    if not configured:
        # Empty string is misconfiguration — reject all requests to prevent
        # accidental open-access deployment. Set AUTH_TOKEN in .env.
        raise HTTPException(status_code=401, detail="Auth misconfigured: AUTH_TOKEN is empty")
    if credentials is None or credentials.credentials != configured:
        raise HTTPException(status_code=401, detail="Unauthorized")
