"""Bearer token authentication dependency for FastAPI routes.

When AUTH_TOKEN is not configured (empty string), all requests pass through
without authentication — this is intentional dev/localhost mode behavior that
keeps existing tests passing without any changes.

To enable auth: set AUTH_TOKEN=<token> in .env or environment before starting.
Generate a token: python -c "import secrets; print(secrets.token_hex(32))"
"""
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.config import settings

_bearer = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """FastAPI dependency: validate Authorization: Bearer <token>.

    Open-mode bypass: if AUTH_TOKEN is not configured, all requests pass.
    This preserves backward compatibility for existing tests and dev usage.
    """
    if not settings.AUTH_TOKEN:
        return  # AUTH_TOKEN not set → open mode (dev/localhost)
    if credentials is None or credentials.credentials != settings.AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
