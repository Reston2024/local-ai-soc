---
phase: 19-identity-rbac
plan: "03"
subsystem: auth
tags: [totp, mfa, auth, security, pyotp]
dependency_graph:
  requires: [19-01]
  provides: [totp-utils, totp-enforcement-in-verify-token]
  affects: [backend/core/auth.py, backend/core/totp_utils.py]
tech_stack:
  added: [pyotp, qrcode]
  patterns: [in-memory-replay-prevention, tdd-red-green]
key_files:
  created:
    - backend/core/totp_utils.py
  modified:
    - backend/core/auth.py
    - tests/unit/test_totp.py
decisions:
  - "Inline import of verify_totp inside verify_token branch avoids circular import at module level"
  - "Replay prevention uses process-local dict (_seen_totp); restart caveat documented in module docstring"
  - "totp_secret never stored on OperatorContext — only totp_enabled bool propagates to request state"
  - "valid_window=1 (±30 s clock skew) chosen; window=2 would double replay exposure"
metrics:
  duration: "130s"
  completed_date: "2026-04-01"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
---

# Phase 19 Plan 03: TOTP MFA Utilities and Enforcement Summary

**One-liner:** Per-operator TOTP MFA via pyotp with in-memory replay prevention and X-TOTP-Code header enforcement in verify_token.

## What Was Built

### Task 1: totp_utils.py (TDD — RED then GREEN)

`backend/core/totp_utils.py` implements four pure functions:

- `generate_totp_secret()` — returns a 32-char base32 secret via `pyotp.random_base32()`
- `verify_totp(secret, code, operator_id)` — validates TOTP code with `valid_window=1`, records accepted codes in `_seen_totp` dict for replay prevention
- `get_provisioning_uri(secret, username)` — returns `otpauth://totp/AI-SOC-Brain:<username>?...` URI
- `totp_qr_png_b64(uri)` — encodes QR code PNG as `data:image/png;base64,...` string using BytesIO (no temp files)

All 6 `TestTOTP*` tests pass.

### Task 2: TOTP enforcement in verify_token

`backend/core/auth.py` now enforces TOTP when an operator row has a `totp_secret`:

1. Build a partial `OperatorContext` with `totp_enabled=True, totp_verified=False`
2. Read `X-TOTP-Code` header — if missing, raise 401
3. Call `verify_totp()` — if False (wrong or replayed), raise 401
4. Set `ctx.totp_verified = True` and continue

Operators without `totp_secret` get `totp_enabled=False, totp_verified=True` (unchanged behaviour). Legacy `AUTH_TOKEN` path is unchanged. The `totp_utils` import is deferred inside the branch to avoid any circular import at module load.

`OperatorContext` in `backend/core/rbac.py` was confirmed correct — no `totp_secret` field, only `totp_enabled` bool.

## Test Results

```
tests/unit/test_totp.py  6 passed
tests/unit/test_auth.py  11 passed
Total: 17 passed
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `backend/core/totp_utils.py` exists and imports cleanly
- Commits `5fac58f` and `d90a7cb` verified in git log
- 17/17 tests pass
