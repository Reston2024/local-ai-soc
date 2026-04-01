"""Bearer token authentication dependency for FastAPI routes.

Multi-operator authentication with legacy single-token fallback.

Lookup order:
1. Extract raw token from Authorization header or ?token= query param
2. Attempt prefix-based operator lookup in SQLite operators table
3. If operator found and bcrypt verify passes → return OperatorContext
4. If no operator found → constant-time dummy verify (prevent timing oracle)
5. If no operator match → try hmac.compare_digest against AUTH_TOKEN (legacy)
6. If legacy match → return OperatorContext(operator_id='legacy-admin')
7. Nothing matches → raise HTTPException(401)

When AUTH_TOKEN is empty string, ALL requests are rejected (misconfiguration guard).
To disable auth for local dev: set AUTH_TOKEN=dev-only-bypass in .env explicitly.

The default AUTH_TOKEN is "changeme" — auth is ON in all environments unless
the operator explicitly overrides AUTH_TOKEN in .env or the environment.

To enable auth with a strong token:
    python -c "import secrets; print(secrets.token_hex(32))"
and set AUTH_TOKEN=<token> in .env.
"""
import asyncio
import hmac

from fastapi import HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.config import settings
from backend.core.operator_utils import _dummy_hash, key_prefix, verify_api_key
from backend.core.rbac import OperatorContext

_bearer = HTTPBearer(auto_error=False)


def _lookup_operator_sync(sqlite_store, prefix: str):
    """Synchronous operator lookup — wraps get_operator_by_prefix."""
    return sqlite_store.get_operator_by_prefix(prefix)


def _touch_last_seen_sync(sqlite_store, operator_id: str) -> None:
    """Synchronous last-seen update."""
    sqlite_store.update_last_seen(operator_id)


async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    token: str | None = Query(default=None),
) -> OperatorContext:
    """FastAPI dependency: validate Authorization: Bearer <token> or ?token= query param.

    The query param fallback is required for browser-initiated binary downloads
    (PDF, ZIP) where the browser opens a URL directly and cannot set headers.

    Rejects all requests when AUTH_TOKEN is empty or whitespace — this is
    treated as misconfiguration to prevent accidental open-access deployment.

    Returns:
        OperatorContext populated for the authenticated operator.
    """
    configured = settings.AUTH_TOKEN.strip()
    if not configured:
        raise HTTPException(status_code=401, detail="Auth misconfigured: AUTH_TOKEN is empty")

    # Accept token from Bearer header OR ?token= query param
    # Guard: token may be a FastAPI Query sentinel when called directly in tests.
    raw: str | None = None
    if credentials is not None:
        raw = credentials.credentials
    elif isinstance(token, str):
        raw = token

    if raw is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # --- Named operator lookup (prefix-based) ---
    try:
        sqlite_store = request.app.state.stores.sqlite
        prefix = key_prefix(raw)
        row = await asyncio.to_thread(_lookup_operator_sync, sqlite_store, prefix)
    except Exception:
        row = None

    if row is not None:
        if verify_api_key(raw, row["hashed_key"]):
            ctx = OperatorContext(
                operator_id=row["operator_id"],
                username=row["username"],
                role=row["role"],
                totp_verified=True,   # Phase 19-03 will add TOTP enforcement
                totp_enabled=bool(row.get("totp_secret")),
            )
            # Async-safe fire-and-forget last_seen update
            try:
                await asyncio.to_thread(_touch_last_seen_sync, sqlite_store, row["operator_id"])
            except Exception:
                pass
            request.state.operator = ctx
            return ctx
        else:
            # Wrong key for this prefix — fall through to legacy check
            pass
    else:
        # Constant-time dummy verify to prevent timing oracle
        verify_api_key(raw, _dummy_hash)

    # --- Legacy AUTH_TOKEN fallback ---
    if hmac.compare_digest(raw, configured):
        ctx = OperatorContext(
            operator_id="legacy-admin",
            username="admin",
            role="admin",
            totp_verified=True,
            totp_enabled=False,
        )
        request.state.operator = ctx
        return ctx

    raise HTTPException(status_code=401, detail="Unauthorized")
