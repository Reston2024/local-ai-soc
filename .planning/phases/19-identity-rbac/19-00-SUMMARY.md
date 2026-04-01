---
phase: 19-identity-rbac
plan: "00"
subsystem: testing
tags: [tdd, rbac, auth, totp, operators, passlib, pyotp, qrcode]
dependency_graph:
  requires: []
  provides:
    - tests/unit/test_operator_store.py
    - tests/unit/test_auth.py (extended)
    - tests/unit/test_rbac.py
    - tests/unit/test_totp.py
    - tests/unit/test_operators_api.py
  affects:
    - backend.stores.sqlite_store (SQLiteStore — operators DDL)
    - backend.core.auth (operator lookup, legacy fallback)
    - backend.core.rbac (require_role dependency)
    - backend.core.totp (generate, verify, provisioning)
    - backend.api.operators (CRUD, key rotation, RBAC enforcement)
tech_stack:
  added:
    - passlib==1.7.4 (bcrypt password hashing)
    - pyotp==2.9.0 (TOTP generation and verification)
    - qrcode==8.2 (QR code PNG generation for TOTP provisioning)
  patterns:
    - TDD RED phase: pytest.fail("NOT IMPLEMENTED") stubs
    - pytest-asyncio auto mode with @pytest.mark.asyncio decorators
key_files:
  created:
    - tests/unit/test_operator_store.py
    - tests/unit/test_rbac.py
    - tests/unit/test_totp.py
    - tests/unit/test_operators_api.py
  modified:
    - tests/unit/test_auth.py (appended TestOperatorLookup + TestAuditAttribution)
    - pyproject.toml (three new runtime dependencies)
    - uv.lock (updated)
decisions:
  - "Stub async test methods decorated with @pytest.mark.asyncio at method level (pytest-asyncio auto mode still requires explicit marks on class methods)"
  - "All five test files use pytest.fail('NOT IMPLEMENTED') pattern — ensures FAILED not ERROR or SKIP"
metrics:
  duration: "1m"
  completed_date: "2026-04-01"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 3
---

# Phase 19 Plan 00: Wave 0 TDD Stubs — Identity & RBAC Summary

Wave 0 RED phase stubs for Phase 19 identity/RBAC system — passlib/pyotp/qrcode installed, 26 failing stubs across 5 test files covering operator DDL, bcrypt hashing, auth token lookup, RBAC enforcement, TOTP, and operator CRUD API.

## What Was Built

Five test stub files that define the complete TDD contract for Phase 19:

- `test_operator_store.py` — 7 stubs: operators table DDL, key-prefix index, bcrypt hashing, verification, bootstrap admin seeding
- `test_auth.py` (extended) — 5 new stubs: operator lookup, legacy AUTH_TOKEN fallback, request.state injection, 401 on no token, audit attribution
- `test_rbac.py` — 3 stubs: require_role pass, 403, and multi-role variants
- `test_totp.py` — 6 stubs: secret generation, code verification, replay prevention, provisioning URI, QR PNG base64
- `test_operators_api.py` — 5 stubs: CRUD create/list/deactivate, key rotation, analyst 403

Three runtime packages installed: `passlib[bcrypt]`, `pyotp`, `qrcode[pil]`.

## Verification Results

```
26 failed, 6 passed in 0.31s
```

All 26 new stubs: FAILED (not ERROR). All 6 pre-existing auth tests: still passing. Zero import failures. `import passlib, pyotp, qrcode` prints OK.

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Install deps + operator-store + auth stubs | 61e4809 | test_operator_store.py, test_auth.py, pyproject.toml, uv.lock |
| 2 | RBAC, TOTP, operators-API stubs | 15c3a84 | test_rbac.py, test_totp.py, test_operators_api.py |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- tests/unit/test_operator_store.py: FOUND
- tests/unit/test_auth.py: FOUND (extended)
- tests/unit/test_rbac.py: FOUND
- tests/unit/test_totp.py: FOUND
- tests/unit/test_operators_api.py: FOUND
- Commit 61e4809: FOUND
- Commit 15c3a84: FOUND
- pytest result: 26 failed, 6 passed, 0 errors

## Notes

An external tool modified test_operator_store.py mid-execution to import from implementation modules that do not yet exist (backend.stores.sqlite_store operators DDL, backend.core.operator_utils, backend.core.rbac). This caused a collection ERROR. The file was restored to the correct RED-phase stub form (pytest.fail stubs only) to maintain the plan contract: FAILED not ERROR.
