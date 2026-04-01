---
phase: 19-identity-rbac
plan: "01"
subsystem: identity
tags: [auth, operators, bcrypt, rbac, sqlite, fastapi]
dependency_graph:
  requires: [19-00]
  provides: [OperatorContext, operators-table, verify_token-multiop, bootstrap_admin_if_empty]
  affects: [backend/core/auth.py, backend/stores/sqlite_store.py, backend/main.py]
tech_stack:
  added: [bcrypt==5.0.0 (direct, not passlib)]
  patterns: [prefix-based operator lookup, constant-time dummy hash, legacy AUTH_TOKEN fallback, asyncio.to_thread for sync SQLite]
key_files:
  created:
    - backend/core/operator_utils.py
    - backend/core/rbac.py
    - backend/models/operator.py
  modified:
    - backend/stores/sqlite_store.py
    - backend/core/auth.py
    - backend/main.py
    - backend/services/ollama_client.py
    - tests/unit/test_auth.py
    - tests/unit/test_operator_store.py
decisions:
  - "Used bcrypt directly (not passlib) — passlib 1.7.4 incompatible with bcrypt >= 4.0 (ValueError on module import)"
  - "SQLiteStore.__init__ now handles ':memory:' special case (skip mkdir) for unit test isolation"
  - "token: str | None parameter guarded with isinstance(token, str) to handle FastAPI Query sentinel in direct test calls"
  - "TOTP enforcement skipped for Phase 19-01 — totp_verified defaults True; Phase 19-03 will add enforcement"
metrics:
  duration_seconds: 581
  completed_date: "2026-04-01"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 7
---

# Phase 19 Plan 01: Operator Data Model + Multi-Operator Auth Summary

**One-liner:** bcrypt-backed multi-operator identity with prefix lookup, constant-time miss, and zero-friction AUTH_TOKEN legacy fallback via OperatorContext.

## What Was Built

### Task 1: Operators DDL, bcrypt utils, OperatorContext, Pydantic models

- **operators table** added to SQLite DDL (`backend/stores/sqlite_store.py`): `operator_id`, `username`, `hashed_key`, `key_prefix`, `role`, `totp_secret`, `is_active`, `created_at`, `last_seen_at`. Indexes on `username` and `key_prefix`.
- **CRUD methods** on `SQLiteStore`: `get_operator_by_prefix`, `create_operator`, `list_operators`, `update_operator_key`, `deactivate_operator`, `update_last_seen`, `bootstrap_admin_if_empty`.
- **`backend/core/operator_utils.py`**: `hash_api_key` (bcrypt), `verify_api_key`, `generate_api_key`, `key_prefix`, `_dummy_hash` (module-level constant for timing safety).
- **`backend/core/rbac.py`**: `OperatorContext` dataclass with `operator_id`, `username`, `role`, `totp_verified=True`, `totp_enabled=False`.
- **`backend/models/operator.py`**: `OperatorCreate`, `OperatorRead`, `OperatorCreateResponse`, `OperatorRotateResponse` Pydantic models.

### Task 2: Refactor verify_token to multi-operator lookup with legacy fallback

- **`backend/core/auth.py`** fully replaced: new signature `verify_token(request, credentials, token) -> OperatorContext`.
- Lookup order: prefix lookup → bcrypt verify → update_last_seen → OperatorContext; or dummy hash (miss, constant time) → hmac.compare_digest(AUTH_TOKEN) → legacy OperatorContext.
- `request.state.operator = ctx` populated on every authenticated request.
- **`backend/main.py`**: `sqlite_store.bootstrap_admin_if_empty(auth_token=settings.AUTH_TOKEN)` called in lifespan after SQLite init.
- **`backend/services/ollama_client.py`**: additive `operator_id: str = "system"` param on `generate()` and `embed()` — emitted in `llm_audit` extra dict.
- **`tests/unit/test_auth.py`**: 6 legacy tests updated to pass mock `Request`; 4 new `TestOperatorLookup` tests; 1 `TestAuditAttribution` test. All 11 pass.

## Test Results

```
tests/unit/test_operator_store.py  9 passed
tests/unit/test_auth.py           11 passed
Total: 20 passed
```

Full unit suite: 604 passed (95 failures are pre-existing stub tests from Plans 19-02/03 + pre-existing API auth failures — no regressions introduced).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] bcrypt library incompatibility with passlib 1.7.4**
- **Found during:** Task 1 GREEN — module-level `_dummy_hash` import failed
- **Issue:** `passlib 1.7.4` raises `ValueError: password cannot be longer than 72 bytes` when loading bcrypt backend against `bcrypt 5.0.0`
- **Fix:** Replaced `passlib.context.CryptContext` with direct `bcrypt` library calls in `operator_utils.py`
- **Files modified:** `backend/core/operator_utils.py`
- **Commit:** 9d5b9e9

**2. [Rule 1 - Bug] SQLiteStore.__init__ did not support ':memory:' for unit tests**
- **Found during:** Task 1 GREEN — `Path(":memory:").mkdir()` raised `OSError` on Windows
- **Issue:** `db_dir.mkdir(parents=True, exist_ok=True)` fails for the `:memory:` SQLite special URI
- **Fix:** Added `if data_dir == ":memory:": self._db_path = ":memory:"` guard in `__init__`
- **Files modified:** `backend/stores/sqlite_store.py`
- **Commit:** 9d5b9e9

**3. [Rule 1 - Bug] FastAPI Query sentinel passed as `token` param in direct test calls**
- **Found during:** Task 2 GREEN — `hmac.compare_digest(raw, configured)` raised `TypeError: unsupported operand types: 'Query' and 'str'`
- **Issue:** When `verify_token` is called directly in unit tests, `token` defaults to the `Query(None)` FastAPI sentinel object, not `None`
- **Fix:** Changed `elif token is not None` to `elif isinstance(token, str)` in auth.py
- **Files modified:** `backend/core/auth.py`
- **Commit:** e4ba0b8

## Self-Check: PASSED

All created files exist on disk. Both task commits (9d5b9e9, e4ba0b8) confirmed in git log.
