"""
Operator API key utilities: bcrypt hashing, verification, generation.

Uses bcrypt directly (passlib 1.7.4 is incompatible with bcrypt >= 4.0).
All functions are synchronous (no I/O) and safe to call from any context.
"""
import secrets

import bcrypt as _bcrypt


def hash_api_key(raw: str) -> str:
    """Return a bcrypt hash of the raw API key."""
    salt = _bcrypt.gensalt()
    return _bcrypt.hashpw(raw.encode(), salt).decode()


def verify_api_key(raw: str, hashed: str) -> bool:
    """Return True iff raw matches the bcrypt hashed key."""
    try:
        return _bcrypt.checkpw(raw.encode(), hashed.encode())
    except Exception:
        return False


def generate_api_key() -> str:
    """Generate a cryptographically secure API key (URL-safe base64, 32 bytes)."""
    return secrets.token_urlsafe(32)


def key_prefix(raw: str) -> str:
    """Return the first 8 characters of the raw key for prefix-based lookup."""
    return raw[:8]


# Pre-computed dummy hash used for constant-time miss (prevents timing oracle).
# Computed lazily to avoid module-level bcrypt work on every import.
def _get_dummy_hash() -> str:
    return hash_api_key("__dummy__")


# Module-level constant for import-time access (computed once).
_dummy_hash: str = hash_api_key("__dummy__")
