"""
TOTP MFA utilities for per-operator two-factor authentication.

Uses pyotp (RFC 6238) with a 30 s time step and valid_window=1 (±30 s clock
skew tolerance). Replay prevention uses SQLite system_kv as the authoritative
store (survives restarts) with an in-process dict as L1 cache.

Each accepted code is stored under a hashed key with a 90-second TTL
(30 s window x 3). On restart, the SQLite check catches codes that were
accepted before the restart, closing the replay window.
"""
import base64
import hashlib
import io
import time

import pyotp
import qrcode

# ---------------------------------------------------------------------------
# Replay prevention
# L1 cache: operator_id+code_hash -> expire_at (float unix timestamp)
# L2/authoritative: SQLite system_kv (persists across restarts)
# ---------------------------------------------------------------------------
_seen_totp: dict[str, float] = {}

_TOTP_TTL = 90.0  # seconds: 30 s window × 3 for safety margin


def _totp_cache_key(operator_id: str, code: str) -> str:
    """Return the system_kv key for a given operator+code pair."""
    raw = f"{operator_id}:{code}"
    return f"totp_seen_{hashlib.sha256(raw.encode()).hexdigest()}"


def _totp_already_seen(operator_id: str, code: str, sqlite_store=None) -> bool:
    """
    Check if this TOTP code was already accepted for the given operator.

    SQLite system_kv is authoritative (survives restarts). The in-process
    dict is used as a fast L1 cache to avoid SQLite I/O on every request.

    Returns True if the code was already seen (replay attempt), False otherwise.
    When False, the code is marked as seen in both stores before returning.
    """
    now = time.time()
    expire_at = now + _TOTP_TTL
    cache_key = _totp_cache_key(operator_id, code)

    # L1 cache fast path
    cached_expire = _seen_totp.get(cache_key)
    if cached_expire is not None:
        if cached_expire > now:
            return True
        # TTL expired — evict stale entry
        del _seen_totp[cache_key]

    # L2 authoritative check via SQLite system_kv
    if sqlite_store is not None:
        try:
            existing = sqlite_store.get_kv(cache_key)
            if existing is not None and float(existing) > now:
                _seen_totp[cache_key] = float(existing)  # warm L1 cache
                return True
            # Mark as seen in SQLite
            sqlite_store.set_kv(cache_key, str(expire_at))
        except Exception:
            pass  # non-fatal — fall through to in-memory only

    # Mark as seen in L1 cache
    _seen_totp[cache_key] = expire_at
    return False


def generate_totp_secret() -> str:
    """Generate a random base32 TOTP secret (160 bits = 32 base32 chars)."""
    return pyotp.random_base32()


def verify_totp(secret: str, code: str, operator_id: str, sqlite_store=None) -> bool:
    """
    Verify a 6-digit TOTP code against the operator's secret.

    valid_window=1: accepts current step ± 1 (±30 s clock skew). Do NOT
    increase — window=2 doubles the replay window.

    Replay prevention: rejects a code if it was already accepted for this
    operator within the last 90 seconds. SQLite system_kv is authoritative
    and survives process restarts.

    Args:
        secret:       Base32 TOTP secret for the operator.
        code:         6-digit code from the authenticator app.
        operator_id:  Operator identifier used to scope replay prevention.
        sqlite_store: Optional SQLiteStore instance for persistent replay
                      prevention. Falls back to in-process dict only if None.
    """
    # Reject replay: code already accepted (checks SQLite then L1 cache)
    if _totp_already_seen(operator_id, code, sqlite_store):
        return False

    totp = pyotp.TOTP(secret)
    valid = totp.verify(code, valid_window=1)
    # Note: if valid is False, _totp_already_seen has already marked the code
    # as "seen" in the stores — this is intentional: an invalid code that was
    # submitted should not be retried with the same value.
    return valid


def get_provisioning_uri(secret: str, username: str) -> str:
    """Return the otpauth:// URI for QR code encoding."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name="AI-SOC-Brain")


def totp_qr_png_b64(provisioning_uri: str) -> str:
    """
    Generate a QR code PNG for the provisioning URI and return as base64.

    Uses BytesIO to avoid temporary files on Windows. Returns a data URI
    string the frontend can embed directly: 'data:image/png;base64,...'
    """
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"
