---
phase: 21-evidence-provenance
plan: "05"
subsystem: api
tags: [fastapi, svelte5, provenance, chain-of-custody, rbac, require_role]

# Dependency graph
requires:
  - phase: 21-03
    provides: SQLiteStore provenance tables and get_*_provenance methods
  - phase: 21-04
    provides: playbook_run_provenance table + record_playbook_provenance method
provides:
  - 4 authenticated GET endpoints at /api/provenance/{ingest,detection,llm,playbook}/{id}
  - require_role("analyst","admin") enforced on all provenance endpoints
  - ProvenanceView.svelte with Svelte 5 runes and 4-tab lookup UI
  - api.ts provenance namespace with 4 typed fetch methods
  - IngestProvenanceRecord, DetectionProvenanceRecord, LlmProvenanceRecord, PlaybookProvenanceRecord TypeScript interfaces
affects:
  - Future phases using provenance lookups from the dashboard
  - Any phase testing provenance endpoints (must override verify_token dependency)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - require_role("analyst","admin") on read-only provenance endpoints
    - Test files that include provenance router must override verify_token to bypass auth
    - api.ts typed namespace pattern extended with provenance domain

key-files:
  created:
    - backend/api/provenance.py
    - dashboard/src/views/ProvenanceView.svelte
  modified:
    - dashboard/src/lib/api.ts
    - dashboard/src/App.svelte
    - tests/unit/test_provenance_api.py
    - tests/unit/test_detection_provenance.py
    - tests/unit/test_llm_provenance.py
    - tests/unit/test_playbook_provenance.py

key-decisions:
  - "require_role added directly in provenance.py endpoints rather than relying solely on main.py router-level verify_token, enabling auth testing without the full app"
  - "Existing tests (test_detection/llm/playbook_provenance_api) updated to override verify_token with an analyst OperatorContext so they compile against the new auth-enforced endpoints"

patterns-established:
  - "Pattern: Test helpers for routers with require_role must override verify_token via app.dependency_overrides[verify_token] = lambda: OperatorContext(...)"

requirements-completed:
  - P21-T05

# Metrics
duration: 20min
completed: 2026-04-02
---

# Phase 21 Plan 05: Provenance API + Dashboard Summary

**Four authenticated FastAPI GET endpoints wiring SQLite provenance stores, plus ProvenanceView.svelte with tab-based chain-of-custody lookup for all artefact types**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-02T06:00:00Z
- **Completed:** 2026-04-02T06:20:00Z
- **Tasks:** 2 (+ checkpoint auto-approved)
- **Files modified:** 7

## Accomplishments

- All 4 provenance GET endpoints require `require_role("analyst","admin")` — unauthenticated requests return 401
- 16 provenance tests GREEN across 5 test files
- Dashboard ProvenanceView with Svelte 5 runes: 4 tabs (Ingest, Detection, AI Response, Playbook Run), hash copy-to-clipboard, 404 error display
- Dashboard builds cleanly — no TypeScript errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Create backend/api/provenance.py and register in main.py** - `763b6b9` (feat)
2. **Task 2: Create ProvenanceView.svelte, update api.ts and App.svelte** - `f46c25c` (feat)

## Files Created/Modified

- `backend/api/provenance.py` - 4 GET endpoints with require_role("analyst","admin") + asyncio.to_thread SQLite lookups
- `dashboard/src/views/ProvenanceView.svelte` - Svelte 5 runes tab-based provenance lookup UI
- `dashboard/src/lib/api.ts` - Added 4 TS interfaces + api.provenance namespace with 4 typed fetch methods
- `dashboard/src/App.svelte` - Added 'provenance' to View type, ProvenanceView import, nav item, view render block
- `tests/unit/test_provenance_api.py` - Implemented test_provenance_endpoints_require_auth (was pytest.fail stub)
- `tests/unit/test_detection_provenance.py` - Added verify_token override to test_detection_provenance_api
- `tests/unit/test_llm_provenance.py` - Added verify_token override to test_llm_provenance_api
- `tests/unit/test_playbook_provenance.py` - Added verify_token override to test_playbook_provenance_api

## Decisions Made

- Added `require_role` directly to `provenance.py` endpoints rather than relying solely on `main.py`'s `dependencies=[Depends(verify_token)]`. This makes the router self-contained and testable in isolation — a minimal FastAPI app including just the provenance router will enforce auth without needing the full application.
- The existing three API tests (detection/llm/playbook) each built a bare FastAPI app and overrode `get_stores` but did not override `verify_token`. Adding `require_role` caused them to 401. Fixed by adding `verify_token` override returning an analyst `OperatorContext`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed broken API tests after adding require_role to provenance endpoints**
- **Found during:** Task 1 (Create backend/api/provenance.py)
- **Issue:** `test_detection_provenance_api`, `test_llm_provenance_api`, and `test_playbook_provenance_api` all build a minimal FastAPI app with provenance router and override `get_stores` but not `verify_token`. Adding `require_role` made all 3 return 401 instead of 200.
- **Fix:** Added `app.dependency_overrides[verify_token] = lambda: OperatorContext(operator_id="test-op", username="analyst", role="analyst", totp_verified=True)` to each test.
- **Files modified:** tests/unit/test_detection_provenance.py, tests/unit/test_llm_provenance.py, tests/unit/test_playbook_provenance.py
- **Verification:** All 16 provenance tests GREEN
- **Committed in:** `763b6b9` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Required fix to make tests consistent with auth-enforced endpoints. No scope creep.

## Issues Encountered

None — `main.py` already had the provenance router registration block from a prior session; this plan completed the router implementation and wired up the dashboard.

## Next Phase Readiness

- Provenance chain-of-custody is now end-to-end: ingestion records → detection records → LLM audit records → playbook run records, all queryable via authenticated API and the dashboard UI
- No blockers for subsequent phases

---
*Phase: 21-evidence-provenance*
*Completed: 2026-04-02*
