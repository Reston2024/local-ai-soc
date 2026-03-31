---
phase: 17-soar-playbook-engine
plan: "01"
subsystem: backend
tags: [soar, playbooks, sqlite, pydantic, fastapi, nist-ir]
dependency_graph:
  requires: []
  provides:
    - backend/models/playbook.py exports PlaybookStep, Playbook, PlaybookRun, PlaybookCreate, PlaybookRunAdvance
    - backend/stores/sqlite_store.py playbooks + playbook_runs DDL and 7 CRUD methods
    - backend/api/playbooks.py REST endpoints and seed_builtin_playbooks()
    - backend/data/builtin_playbooks.py 5 NIST IR starter playbooks
  affects:
    - backend/main.py (playbooks_router registered, seed called in lifespan)
tech_stack:
  added: []
  patterns:
    - SQLite DDL extension via _DDL string (existing pattern)
    - Sync store methods wrapped in asyncio.to_thread() from route handlers
    - Idempotent startup seeding via is_builtin=1 sentinel check
    - TDD: RED tests written before GREEN implementation
key_files:
  created:
    - backend/models/playbook.py
    - backend/data/__init__.py
    - backend/data/builtin_playbooks.py
    - backend/api/playbooks.py
    - tests/unit/test_playbook_store.py
    - tests/unit/test_builtin_playbooks.py
  modified:
    - backend/stores/sqlite_store.py (DDL + 7 store methods + 2 parse helpers)
    - backend/main.py (router registration + lifespan seed call)
    - .gitignore (!backend/data/ exception added)
decisions:
  - "Placed BUILTIN_PLAYBOOKS in backend/data/ package (new) rather than backend/api/ to separate data concerns from routing"
  - "seed_builtin_playbooks() uses is_builtin=1 sentinel COUNT(*) check for idempotency — not playbook name matching"
  - "PlaybookRunAdvance included in Phase 17-01 models so Phase 17-02 (execution engine) can import without circular dependency"
  - "Added !backend/data/ exception to .gitignore — data/ pattern was blocking source package tracking"
metrics:
  duration_minutes: 5
  completed_date: "2026-03-31"
  tasks_completed: 2
  tasks_total: 2
  files_created: 6
  files_modified: 3
  tests_added: 36
---

# Phase 17 Plan 01: Playbook Data Model, Schema, and REST API Summary

**One-liner:** SQLite-backed playbook persistence with 5 NIST IR starter playbooks seeded at startup, Pydantic models, and 4 REST endpoints — foundation for Plan 02 execution engine.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Playbook data models and SQLite schema | a056a64 | backend/models/playbook.py, backend/stores/sqlite_store.py, tests/unit/test_playbook_store.py |
| 2 | Built-in playbook library and REST endpoints | d105563 | backend/data/builtin_playbooks.py, backend/api/playbooks.py, backend/main.py, tests/unit/test_builtin_playbooks.py |

## What Was Built

### Pydantic Models (`backend/models/playbook.py`)

- `PlaybookStep` — step_number, title, description, requires_approval (default True), evidence_prompt (Optional)
- `Playbook` — playbook_id, name, description, trigger_conditions, steps, version, created_at, is_builtin
- `PlaybookCreate` — POST body (no playbook_id or created_at)
- `PlaybookRun` — run_id, playbook_id, investigation_id, status (Literal), started_at, completed_at, steps_completed, analyst_notes
- `PlaybookRunAdvance` — step_number, notes, evidence_collected, approved (for Plan 02 PATCH endpoint)

### SQLite Schema (`backend/stores/sqlite_store.py`)

Two new tables added to `_DDL`:
- `playbooks` — playbook_id (PK), name, description, trigger_conditions (JSON), steps (JSON), version, is_builtin, created_at
- `playbook_runs` — run_id (PK), playbook_id (FK), investigation_id, status, started_at, completed_at, steps_completed (JSON), analyst_notes
- Three indexes: idx_playbook_runs_pb, idx_playbook_runs_inv, idx_playbooks_builtin

Seven CRUD methods added: `create_playbook`, `get_playbooks`, `get_playbook`, `create_playbook_run`, `get_playbook_run`, `get_playbook_runs`, `update_playbook_run`.

### Built-in Playbook Library (`backend/data/builtin_playbooks.py`)

Five NIST SP 800-61r3 IR phase-aligned playbooks:
1. **Phishing Initial Triage** — 6 steps, trigger: phishing/suspicious email/credential harvesting
2. **Lateral Movement Investigation** — 5 steps, trigger: lateral movement/pass-the-hash/T1021
3. **Privilege Escalation Response** — 5 steps, trigger: privilege escalation/UAC bypass/T1548
4. **Data Exfiltration Containment** — 6 steps, trigger: data exfiltration/large upload/T1041/T1048/C2
5. **Malware Isolation** — 6 steps, trigger: malware/ransomware/backdoor/T1059/T1105

### REST API (`backend/api/playbooks.py`)

- `GET  /api/playbooks` — returns `{"playbooks": [...], "total": int}`
- `POST /api/playbooks` — accepts PlaybookCreate body, returns 201
- `GET  /api/playbooks/{playbook_id}` — single playbook or 404
- `GET  /api/playbooks/{playbook_id}/runs` — returns `{"runs": [...], "total": int}` or 404

`seed_builtin_playbooks(sqlite_store)` checks `COUNT(*) WHERE is_builtin=1` before inserting — fully idempotent.

### main.py Integration

- Playbooks router registered in deferred-import block with `verify_token` dependency
- `seed_builtin_playbooks()` called in lifespan after SQLite store initialised, wrapped in try/except for graceful degradation

## Verification

```
uv run python -c "
from backend.models.playbook import Playbook, PlaybookRun, PlaybookStep, PlaybookCreate, PlaybookRunAdvance
from backend.data.builtin_playbooks import BUILTIN_PLAYBOOKS
from backend.api.playbooks import router
assert len(BUILTIN_PLAYBOOKS) == 5
print('All imports OK, 5 built-in playbooks defined')
"
# All imports OK, 5 built-in playbooks defined

uv run pytest tests/unit/test_playbook_store.py tests/unit/test_builtin_playbooks.py -q
# 36 passed in 0.82s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] .gitignore `data/` pattern blocked `backend/data/` package tracking**
- **Found during:** Task 2 commit
- **Issue:** The `.gitignore` `data/` pattern matched `backend/data/` recursively, preventing git from tracking the new source package
- **Fix:** Added `!backend/data/` exception line to `.gitignore`
- **Files modified:** `.gitignore`
- **Commit:** d105563

## Self-Check

Files exist:
- backend/models/playbook.py: FOUND
- backend/data/builtin_playbooks.py: FOUND
- backend/api/playbooks.py: FOUND
- tests/unit/test_playbook_store.py: FOUND
- tests/unit/test_builtin_playbooks.py: FOUND

Commits exist:
- a056a64: FOUND (feat(17-01): Playbook data models and SQLite schema)
- d105563: FOUND (feat(17-01): Built-in playbook library and REST endpoints)

## Self-Check: PASSED
