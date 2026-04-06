---
phase: 25-receipt-ingestion-and-case-state-propagation
plan: "03"
subsystem: backend-api
tags: [receipts, notifications, case-state, api, fastapi]
dependency_graph:
  requires: [25-01, 25-02]
  provides: [POST /api/receipts, GET /api/notifications]
  affects: [backend/main.py, backend/api/]
tech_stack:
  added: []
  patterns: [audit-first-insert, deferred-try-except-router, asyncio.to_thread-sqlite]
key_files:
  created:
    - backend/api/receipts.py
    - backend/api/notifications.py
  modified:
    - backend/main.py
decisions:
  - "audit-first insert: receipt always stored in DuckDB before case state or notification steps"
  - "best-effort case state propagation: SQLite failure logs warning but does not roll back receipt"
  - "deferred try/except router registration matches Phase 24 recommendations_router pattern"
metrics:
  duration: "2 minutes"
  completed_date: "2026-04-06"
  tasks_completed: 3
  files_changed: 3
---

# Phase 25 Plan 03: Receipt API Routes and Router Registration Summary

POST /api/receipts with audit-first DuckDB storage, SQLite case-state propagation via asyncio.to_thread, and conditional notification emit; GET /api/notifications returning pending list; both routers registered in main.py via deferred try/except.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create backend/api/receipts.py | 3c661f6 | backend/api/receipts.py |
| 2 | Create backend/api/notifications.py | 8d194f6 | backend/api/notifications.py |
| 3 | Register both routers in backend/main.py | a4e1e99 | backend/main.py |

## What Was Built

### backend/api/receipts.py

`POST /api/receipts` route implementing the three-step ADR-032 protocol:

1. **Audit-first INSERT** into `execution_receipts` (DuckDB) — catches PRIMARY KEY violation to return 409
2. **Best-effort case state propagation** to `investigation_cases.case_status` (SQLite) via `asyncio.to_thread` — logs warning on failure, never rolls back the receipt
3. **Conditional notification emit** into `notifications` (DuckDB) only when `failure_taxonomy in NOTIFICATION_TRIGGERS`

Imports `CASE_STATE_MAP`, `NOTIFICATION_TRIGGERS`, `REQUIRED_ACTION_MAP`, and `ReceiptIngest` from `backend.models.receipt`.

### backend/api/notifications.py

`GET /api/notifications` route returning all rows from `notifications` where `status = 'pending'`, ordered by `created_at DESC`, as a flat JSON list.

### backend/main.py Registration

Two deferred `try/except ImportError` blocks appended immediately after the `recommendations_router` block (line ~555), following the identical Phase 24 pattern. Both routers include `verify_token` dependency.

## Verification Results

```
uv run python -c "from backend.api.receipts import router; print('receipts router OK, prefix:', router.prefix)"
# receipts router OK, prefix: /api/receipts

uv run python -c "from backend.api.notifications import router; print('notifications router OK, prefix:', router.prefix)"
# notifications router OK, prefix: /api/notifications

# create_app() route list shows:
# /api/receipts
# /api/notifications

# Stub tests: 17 skipped, 0 errors (stubs untouched — Wave 3 plan 04 activates them)
# Full suite: 898 passed, 19 skipped, 9 xfailed, 9 xpassed
```

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- backend/api/receipts.py: FOUND
- backend/api/notifications.py: FOUND
- Commit 3c661f6: FOUND
- Commit 8d194f6: FOUND
- Commit a4e1e99: FOUND
