---
phase: "19"
plan: "02"
subsystem: backend/core
tags: [rbac, auth, fastapi, dependency-injection, python]
dependency_graph:
  requires: ["19-01"]
  provides: ["require_role() factory", "RBAC primitive for all admin-only routes"]
  affects: ["backend/api/operators.py (19-04)", "any future admin-only endpoint"]
tech_stack:
  added: []
  patterns: ["FastAPI dependency factory", "deferred import to avoid circular dependency", "TDD red-green"]
key_files:
  created: []
  modified:
    - backend/core/rbac.py
    - tests/unit/test_rbac.py
decisions:
  - "Deferred import of verify_token inside require_role closure to avoid circular import (auth.py imports OperatorContext from rbac.py)"
  - "require_role returns the inner _dep coroutine directly; Depends() wraps it at call site so routes can use the OperatorContext return value"
  - "Tests pass ctx directly to inner dep (bypassing full auth stack) — cleaner unit isolation than mocking verify_token"
metrics:
  duration: "133s (~2m)"
  completed_date: "2026-04-01"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 2
---

# Phase 19 Plan 02: require_role() RBAC Dependency Factory Summary

**One-liner:** Closure-based `require_role(*roles)` FastAPI dependency factory that raises HTTP 403 for insufficient role, with deferred `verify_token` import to prevent circular imports.

## What Was Built

`require_role()` is a factory function in `backend/core/rbac.py` that returns a FastAPI dependency coroutine. The pattern:

```python
def require_role(*allowed_roles: str) -> Callable:
    from backend.core.auth import verify_token  # deferred — avoids circular import

    async def _dep(request: Request, ctx: OperatorContext = Depends(verify_token)) -> OperatorContext:
        if ctx.role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Forbidden: requires role in {list(allowed_roles)}, got '{ctx.role}'")
        return ctx

    return _dep
```

The 401 vs 403 distinction is preserved: `verify_token` (imported via `Depends`) raises 401 for missing/invalid tokens; `require_role` raises 403 only when the token is valid but the role is insufficient.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement require_role() + fill test stubs | 4337dd3 | backend/core/rbac.py, tests/unit/test_rbac.py |

## Test Results

- `test_require_role_pass`: PASSED — admin ctx returns through without raising
- `test_require_role_403`: PASSED — analyst ctx raises HTTPException(403), detail mentions role
- `test_require_role_multiple_allowed`: PASSED — analyst passes require_role("admin", "analyst")
- Full auth+rbac suite: 14/14 passed
- Full unit suite: 613 passed, 86 pre-existing failures (unchanged — no regressions)

## Deviations from Plan

None — plan executed exactly as written.

Pre-existing failures in `test_ingest_api`, `test_metrics_api`, `test_operators_api` were present before this plan and are out of scope (planned for later plans in Phase 19).

## Self-Check: PASSED

- `backend/core/rbac.py` — FOUND, contains `require_role` and `OperatorContext`
- `tests/unit/test_rbac.py` — FOUND, 3 tests all passing
- Commit `4337dd3` — FOUND
