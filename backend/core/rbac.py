"""
Role-based access control primitives.

Phase 19-01: OperatorContext dataclass only.
Phase 19-02: require_role() dependency factory added.
"""
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, Request


@dataclass
class OperatorContext:
    """Populated by verify_token and attached to request.state.operator."""

    operator_id: str
    username: str
    role: str           # "admin" | "analyst"
    totp_verified: bool = True   # Phase 19-03 will enforce; default True for now
    totp_enabled: bool = False


def require_role(*allowed_roles: str) -> Callable:
    """FastAPI dependency factory enforcing role-based access.

    Usage::

        @router.post("/api/operators", dependencies=[Depends(require_role("admin"))])
        async def create_operator(...): ...

    Returns the OperatorContext so routes can use it directly::

        @router.get("/api/operators")
        async def list_operators(ctx: OperatorContext = Depends(require_role("admin", "analyst"))): ...

    Raises:
        HTTPException(401): propagated from verify_token (no valid token present)
        HTTPException(403): valid token but role not in allowed_roles
    """
    # Deferred import to avoid circular dependency:
    # auth.py imports OperatorContext from rbac.py; rbac.py must not import
    # from auth.py at module level.
    from backend.core.auth import verify_token  # noqa: PLC0415

    async def _dep(
        request: Request,
        ctx: OperatorContext = Depends(verify_token),
    ) -> OperatorContext:
        if ctx.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: requires role in {list(allowed_roles)}, got '{ctx.role}'",
            )
        return ctx

    return _dep
