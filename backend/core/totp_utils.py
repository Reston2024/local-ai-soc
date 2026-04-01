"""
TOTP MFA utilities for per-operator two-factor authentication.

Uses pyotp (RFC 6238) with a 30 s time step and valid_window=1 (±30 s clock
skew tolerance). Replay prevention is in-memory (process-local); this is
sufficient for the single-uvicorn-worker, single-desktop deployment model.

Limitation: seen-codes dict is lost on restart. A captured code could be
replayed within the 30 s window immediately after a restart. Acceptable for
the air-gapped threat model — note for future hardening.
"""
import base64
import io

import pyotp
import qrcode

# ---------------------------------------------------------------------------
# In-memory replay prevention: operator_id -> last_used_code
# ---------------------------------------------------------------------------
_seen_totp: dict[str, str] = {}


def generate_totp_secret() -> str:
    """Generate a random base32 TOTP secret (160 bits = 32 base32 chars)."""
    return pyotp.random_base32()


def verify_totp(secret: str, code: str, operator_id: str) -> bool:
    """
    Verify a 6-digit TOTP code against the operator's secret.

    valid_window=1: accepts current step ± 1 (±30 s clock skew). Do NOT
    increase — window=2 doubles the replay window.

    Replay prevention: rejects a code equal to the last accepted code for
    this operator_id even if still within its window.
    """
    # Reject replay: same code used twice
    if _seen_totp.get(operator_id) == code:
        return False

    totp = pyotp.TOTP(secret)
    valid = totp.verify(code, valid_window=1)
    if valid:
        _seen_totp[operator_id] = code
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
