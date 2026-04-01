"""
Role-based access control primitives.

Phase 19-01: OperatorContext dataclass only.
Phase 19-02 will add require_role() dependency.
"""
from dataclasses import dataclass


@dataclass
class OperatorContext:
    """Populated by verify_token and attached to request.state.operator."""

    operator_id: str
    username: str
    role: str           # "admin" | "analyst"
    totp_verified: bool = True   # Phase 19-03 will enforce; default True for now
    totp_enabled: bool = False
