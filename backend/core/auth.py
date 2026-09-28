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
import hashlib
import hmac
import time

from fastapi import HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.config import settings
from backend.core.operator_utils import _dummy_hash, key_prefix, verify_api_key
from backend.core.rbac import OperatorContext

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Short-lived, path-scoped download tokens (?dl=<exp>.<hexsig>)
# ---------------------------------------------------------------------------
DOWNLOAD_TOKEN_TTL = 120  # seconds


def _now() -> int:
    """Current unix time in whole seconds (indirected so tests can monkeypatch)."""
    return int(time.time())


def _download_sig(path: str, exp: int) -> str:
    key = settings.AUTH_TOKEN.strip().encode("utf-8")
    return hmac.new(key, f"{path}|{exp}".encode("utf-8"), hashlib.sha256).hexdigest()


def issue_download_token(path: str) -> str:
    """Return '<exp>.<hexsig>' binding *path* (no query string) for DOWNLOAD_TOKEN_TTL seconds."""
    exp = _now() + DOWNLOAD_TOKEN_TTL
    return f"{exp}.{_download_sig(path, exp)}"


def verify_download_token(dl: str, path: str) -> bool:
    """True when *dl* is unexpired and its HMAC matches *path*."""
    exp_str, sep, sig = dl.partition(".")
    if not sep or not exp_str.isdigit() or not sig:
        return False
    exp = int(exp_str)
    now = _now()
    if exp < now or exp > now + DOWNLOAD_TOKEN_TTL:
        return False
    # Compare as bytes — str compare_digest raises TypeError on non-ASCII input.
    return hmac.compare_digest(
        sig.encode("utf-8"), _download_sig(path, exp).encode("utf-8")
    )


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
    dl: str | None = Query(default=None),
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
        # Short-lived download token (?dl=) — only when no Bearer/?token= supplied.
        # Scoped to one path and to safe (read-only) methods; the principal is a
        # least-privilege analyst context so a dl minted by an analyst can never
        # reach admin-only routes.
        if (
            isinstance(dl, str)
            and request.method in ("GET", "HEAD")
            and verify_download_token(dl, request.url.path)
        ):
            ctx = OperatorContext(
                operator_id="download-token",
                username="download-token",
                role="analyst",
                totp_enabled=False,
                totp_verified=True,
            )
            request.state.operator = ctx
            return ctx
        raise HTTPException(status_code=401, detail="Unauthorized")

    # --- Named operator lookup (prefix-based) ---
    sqlite_store = None
    try:
        sqlite_store = request.app.state.stores.sqlite
        prefix = key_prefix(raw)
        row = await asyncio.to_thread(_lookup_operator_sync, sqlite_store, prefix)
    except Exception:
        row = None

    if row is not None:
        if verify_api_key(raw, row["hashed_key"]):
            # TOTP enforcement (only when operator has totp_secret configured)
            if row.get("totp_secret"):
                ctx = OperatorContext(
                    operator_id=row["operator_id"],
                    username=row["username"],
                    role=row["role"],
                    totp_enabled=True,
                    totp_verified=False,  # set True only after code verifies
                )
                totp_code = request.headers.get("X-TOTP-Code")
                if not totp_code:
                    raise HTTPException(
                        status_code=401,
                        detail="TOTP code required (X-TOTP-Code header)",
                    )
                from backend.core.totp_utils import verify_totp
                if not verify_totp(row["totp_secret"], totp_code, row["operator_id"], sqlite_store):
                    raise HTTPException(status_code=401, detail="Invalid or replayed TOTP code")
                ctx.totp_verified = True
            else:
                ctx = OperatorContext(
                    operator_id=row["operator_id"],
                    username=row["username"],
                    role=row["role"],
                    totp_enabled=False,
                    totp_verified=True,
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

    # DEPRECATED — scheduled for removal 2026-07-01 (see DEPRECATION.md)
    # This path remains for backward compatibility only. Use the operator table auth path.
    # New deployments must use the operator table (POST /api/auth/login).
    # Migrate: create an operator via POST /api/operators and switch to per-operator API keys.
    # ADR-025 documents the security controls. Tracking: S-02.
    # --- Legacy AUTH_TOKEN fallback ---
    if hmac.compare_digest(raw, configured):
        # TOTP enforcement is conditional on LEGACY_TOTP_SECRET being configured.
        # When LEGACY_TOTP_SECRET is set: enforce TOTP on every legacy-path request.
        # When LEGACY_TOTP_SECRET is empty: allow raw AUTH_TOKEN match alone —
        #   appropriate for local single-machine SOC deployments where the 64-char
        #   random AUTH_TOKEN already provides sufficient protection.
        _raw_secret = getattr(settings, "LEGACY_TOTP_SECRET", "")
        # Guard: accept only plain strings — rejects mock objects and other non-str types
        legacy_secret = _raw_secret.strip() if isinstance(_raw_secret, str) else ""
        if legacy_secret:
            # TOTP configured — enforce it
            totp_code = request.headers.get("X-TOTP-Code")
            if not totp_code:
                raise HTTPException(
                    status_code=401,
                    detail="TOTP code required for legacy admin path (X-TOTP-Code header)",
                )
            from backend.core.totp_utils import verify_totp
            if not verify_totp(legacy_secret, totp_code, "legacy-admin", sqlite_store):
                raise HTTPException(status_code=401, detail="Invalid or replayed TOTP code")
        ctx = OperatorContext(
            operator_id="legacy-admin",
            username="admin",
            role="admin",
            totp_verified=bool(legacy_secret),
            totp_enabled=bool(legacy_secret),
        )
        request.state.operator = ctx
        return ctx

    raise HTTPException(status_code=401, detail="Unauthorized")
