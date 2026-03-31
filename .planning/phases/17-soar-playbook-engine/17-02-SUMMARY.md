---
phase: 17-soar-playbook-engine
plan: "02"
subsystem: backend
tags: [soar, playbooks, execution-engine, fastapi, sse, sqlite, tdd]
dependency_graph:
  requires:
    - backend/models/playbook.py (PlaybookRunAdvance, PlaybookRun — from 17-01)
    - backend/stores/sqlite_store.py (create/get/update_playbook_run — from 17-01)
  provides:
    - backend/api/playbooks.py exports runs_router (POST /run, PATCH /step, PATCH /cancel, GET, GET /stream)
    - tests/unit/test_playbook_execution.py 18 unit tests covering all 5 endpoints
  affects:
    - backend/main.py (runs_router registered alongside playbooks_router)
    - backend/models/playbook.py (PlaybookRunAdvance updated to Plan 02 spec)
    - tests/unit/test_playbook_store.py (PlaybookRunAdvance model tests updated)
tech_stack:
  added: []
  patterns:
    - Separate APIRouter prefix /api/playbook-runs in same file as /api/playbooks
    - SSE snapshot pattern (yield run_state event + done event) mirrored from chat.py
    - asyncio.to_thread() for all SQLite store calls
    - 409 Conflict for terminal-state guard (completed/cancelled)
    - TDD: RED tests written before GREEN implementation
key_files:
  created:
    - tests/unit/test_playbook_execution.py
  modified:
    - backend/api/playbooks.py (runs_router + 5 endpoints + utcnow_iso helper)
    - backend/models/playbook.py (PlaybookRunAdvance: analyst_note + outcome fields)
    - backend/main.py (runs_router registered)
    - tests/unit/test_playbook_store.py (PlaybookRunAdvance tests updated)
decisions:
  - "Used separate APIRouter(prefix='/api/playbook-runs') in same file to avoid route conflict with /api/playbooks/* — keeps all playbook logic in one module"
  - "SSE /stream endpoint is a snapshot (not persistent connection) — emits run_state then done; frontend polls as needed"
  - "PlaybookRunAdvance model updated from Plan 01 placeholder (step_number/notes/evidence_collected/approved) to Plan 02 spec (analyst_note/outcome) — existing store tests updated to match"
metrics:
  duration_minutes: 5
  completed_date: "2026-03-31"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 4
  tests_added: 18
---

# Phase 17 Plan 02: Playbook Execution Engine Summary

**One-liner:** Five analyst-gated execution endpoints (start run, advance step, cancel, get, SSE snapshot) with full SQLite audit trail — every PATCH is analyst-initiated with no autonomous step execution.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Execution engine endpoints | 4b50b7c | backend/api/playbooks.py, backend/models/playbook.py, backend/main.py, tests/unit/test_playbook_execution.py, tests/unit/test_playbook_store.py |

## What Was Built

### Execution Endpoints (`backend/api/playbooks.py`)

**Playbooks router extension:**
- `POST /api/playbooks/{playbook_id}/run/{investigation_id}` — Creates run with `status="running"`, `steps_completed=[]`, returns 201; returns 404 if playbook not found

**New `runs_router` (prefix: `/api/playbook-runs`):**
- `GET /api/playbook-runs/{run_id}` — Returns single run or 404
- `PATCH /api/playbook-runs/{run_id}/step/{step_n}` — Analyst-gated step advance; appends `{step_number, outcome, analyst_note, completed_at}` to `steps_completed`; sets `status="completed"` when `step_n >= total_steps`; returns 404 if run not found; returns 409 if run already completed/cancelled
- `PATCH /api/playbook-runs/{run_id}/cancel` — Sets `status="cancelled"` and `completed_at`; returns 409 if already terminal
- `GET /api/playbook-runs/{run_id}/stream` — SSE snapshot: emits `{"event": "run_state", "run": {...}}` then `{"done": true}`

Helper: `utcnow_iso()` returns `datetime.now(timezone.utc).isoformat()`.

### Updated Model (`backend/models/playbook.py`)

`PlaybookRunAdvance` updated from Plan 01 placeholder to Plan 02 spec:
```python
class PlaybookRunAdvance(BaseModel):
    analyst_note: str = ""
    outcome: Literal["confirmed", "skipped"] = "confirmed"
```

### main.py Registration

`runs_router` imported and registered alongside `playbooks_router` with `verify_token` dependency in the same try/except block.

## Verification

```
uv run pytest tests/unit/test_playbook_execution.py tests/unit/test_playbook_store.py -v
# 43 passed in 0.85s

uv run python -c "
from backend.api.playbooks import router, runs_router
routes = [r.path for r in router.routes]
runs_routes = [r.path for r in runs_router.routes]
# Playbooks routes: [..., '/api/playbooks/{playbook_id}/run/{investigation_id}']
# Runs routes: ['/api/playbook-runs/{run_id}', '/api/playbook-runs/{run_id}/step/{step_n}', ...]
print('Execution endpoints OK')
"
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PlaybookRunAdvance model shape mismatch**
- **Found during:** Task 1 GREEN implementation
- **Issue:** Plan 01 created `PlaybookRunAdvance` with `step_number`, `notes`, `evidence_collected`, `approved` fields as a placeholder. Plan 02 requires `analyst_note` and `outcome: Literal["confirmed", "skipped"]` — the plan's interface spec was authoritative.
- **Fix:** Updated `PlaybookRunAdvance` in `backend/models/playbook.py` to use the Plan 02 field names; updated existing `test_playbook_store.py` test to match new shape (added 2 new model validation tests)
- **Files modified:** `backend/models/playbook.py`, `tests/unit/test_playbook_store.py`
- **Commit:** 4b50b7c

## Self-Check

### Files exist:
- backend/api/playbooks.py: FOUND
- backend/models/playbook.py: FOUND
- backend/main.py: FOUND
- tests/unit/test_playbook_execution.py: FOUND
- tests/unit/test_playbook_store.py: FOUND

### Commits exist:
- 4b50b7c: FOUND (feat(17-02): playbook execution engine — 5 analyst-gated endpoints)

## Self-Check: PASSED
