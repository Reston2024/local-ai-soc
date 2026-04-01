---
phase: 19-identity-rbac
plan: "04"
subsystem: operator-management-api
tags: [fastapi, rbac, totp, svelte5, crud]
dependency_graph:
  requires:
    - 19-01  # SQLiteStore operator CRUD methods, OperatorContext, operator_utils
    - 19-02  # require_role() dependency factory
    - 19-03  # TOTP utilities (generate_totp_secret, get_provisioning_uri, totp_qr_png_b64)
  provides:
    - REST API: POST/GET/DELETE /api/operators, POST /api/operators/{id}/rotate-key
    - REST API: POST/DELETE /api/operators/{id}/totp
    - SettingsView.svelte with Operators tab
    - api.settings.operators TypeScript namespace
  affects:
    - backend/main.py  (operators_router registered)
    - backend/stores/sqlite_store.py  (set_totp_secret added)
tech_stack:
  added: []
  patterns:
    - require_role() dependency factory on write endpoints
    - asyncio.to_thread() for all SQLite blocking I/O
    - Svelte 5 $state/$effect/$derived — no writable() stores
    - One-time key display modal (never auto-dismisses)
key_files:
  created:
    - backend/api/operators.py
    - dashboard/src/views/SettingsView.svelte
  modified:
    - backend/stores/sqlite_store.py  (added set_totp_secret method)
    - backend/main.py  (registered operators_router)
    - dashboard/src/lib/api.ts  (added interfaces + api.settings.operators namespace)
    - tests/unit/test_operators_api.py  (replaced stubs with 6 real tests)
decisions:
  - "deactivate_operator endpoint accepts ctx from require_role() dependency directly (not request.state.operator) so TestClient dependency override propagates context correctly"
  - "set_totp_secret(operator_id, None) clears TOTP — single method handles both enable and disable"
  - "Operators router registered via deferred try/except in main.py for consistency with all other non-core routers"
metrics:
  duration: "~6 minutes"
  completed_date: "2026-03-31"
  tasks_completed: 2
  tasks_total: 3
  files_created: 2
  files_modified: 4
---

# Phase 19 Plan 04: Operator Management API and SettingsView Summary

**One-liner:** Named operator CRUD REST API with require_role RBAC, key rotation, TOTP provisioning, and Svelte 5 SettingsView Operators tab with one-time key modal.

## What Was Built

### Task 1: Operators API router and main.py registration (TDD)

`backend/api/operators.py` — 6 endpoints:

| Endpoint | Auth | Description |
|---|---|---|
| `POST /api/operators` | admin | Create operator; returns raw key once |
| `GET /api/operators` | admin+analyst | List operators (no secrets) |
| `DELETE /api/operators/{id}` | admin | Soft-delete (is_active=0); blocks self-delete |
| `POST /api/operators/{id}/rotate-key` | admin | New key; old key invalidated immediately |
| `POST /api/operators/{id}/totp/enable` | admin | Generate TOTP secret, return QR + URI |
| `DELETE /api/operators/{id}/totp` | admin | Clear TOTP secret |

`SQLiteStore.set_totp_secret(operator_id, secret)` added to sqlite_store.py.

`backend/main.py` — operators_router registered via deferred try/except at `/api`.

`tests/unit/test_operators_api.py` — 6 tests (all pass):
- `test_create_operator` — 201 with api_key, no hashed_key/totp_secret in response
- `test_list_no_secrets` — GET excludes hashed_key and totp_secret
- `test_deactivate_operator` — deactivate_operator() called, 200 returned
- `test_deactivate_self_returns_400` — self-delete guard raises 400
- `test_key_rotation` — new api_key returned, key_prefix matches
- `test_analyst_forbidden` — analyst token → 403

### Task 2: SettingsView.svelte and api.ts namespace

`dashboard/src/lib/api.ts` — added:
- Interfaces: `Operator`, `OperatorCreateResponse`, `OperatorRotateResponse`
- `api.settings.operators` namespace: list/create/deactivate/rotateKey/enableTotp/disableTotp

`dashboard/src/views/SettingsView.svelte` — Svelte 5 component:
- Two tabs: Operators (active by default) and System (placeholder)
- $effect auto-load pattern matching ReportsView
- Operator list table: username, role badge (admin=red, analyst=blue), status badge, created_at, last_seen_at, Actions
- Create form: username + role select + Create button
- One-time modal after create/rotate: copy-to-clipboard field, "I have saved this key" dismiss (never auto-dismisses)
- Rotate Key: window.confirm() + one-time modal
- Disable: window.confirm() + reload list
- Enable TOTP: QR code modal with provisioning URI
- `npm run build` exits 0, no TypeScript errors

### Task 3: Checkpoint (pending human verification)

Automated pre-check: 35/35 tests pass (operators + rbac + totp + auth + operator_store).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] deactivate_operator ctx source fixed for test compatibility**
- **Found during:** Task 1 test run
- **Issue:** `deactivate_operator` read `request.state.operator` for self-delete guard, but verify_token override in tests does not populate `request.state.operator` (that happens inside verify_token, which is bypassed)
- **Fix:** Changed `deactivate_operator` signature to accept `ctx: OperatorContext = Depends(require_role("admin"))` directly, removing the `dependencies=` list pattern and passing ctx as a named parameter
- **Files modified:** `backend/api/operators.py`
- **Commit:** 156e32e (included in original Task 1 commit)

## Test Results

```
tests/unit/test_operators_api.py   6/6 pass
tests/unit/test_rbac.py            3/3 pass
tests/unit/test_totp.py            6/6 pass
tests/unit/test_auth.py           11/11 pass
tests/unit/test_operator_store.py  9/9 pass
Total: 35/35 pass
```

`npm run build` exits 0 (1007 modules transformed, 2.18s build time).

## Self-Check: PASSED

| Item | Status |
|---|---|
| `backend/api/operators.py` | FOUND |
| `dashboard/src/views/SettingsView.svelte` | FOUND |
| commit 156e32e (Task 1) | FOUND |
| commit 6bc6ba4 (Task 2) | FOUND |
