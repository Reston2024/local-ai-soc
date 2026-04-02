---
phase: 22-ai-lifecycle-hardening
plan: "02"
subsystem: ai
tags: [sqlite, fastapi, svelte5, confidence-score, llm-audit, heuristic]

# Dependency graph
requires:
  - phase: 22-ai-lifecycle-hardening/22-00
    provides: phase setup and requirements
provides:
  - confidence_score REAL column in llm_audit_provenance (DDL + ALTER TABLE migration)
  - update_confidence_score() method on SQLiteStore
  - Heuristic 0.0-1.0 score computed in query.py after generate() returns
  - confidence_score field in JSONResponse from ask() and done SSE event from ask_stream()
  - Confidence badge in InvestigationView.svelte copilot panel (green/amber/red/grey)
  - confidence and audit_id added as optional fields to ChatHistoryMessage in api.ts
  - 4 passing tests in tests/eval/test_confidence.py
affects: [22-03, 22-04, query-api, investigation-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Heuristic confidence: 0.5 grounding + 0.3 citation_ok + 0.1 rich-context, clamped [0,1]"
    - "Non-fatal async score write via asyncio.to_thread() with warning-level logging"
    - "Idempotent ALTER TABLE migration in SQLiteStore.__init__() for backward compat"

key-files:
  created: []
  modified:
    - backend/stores/sqlite_store.py
    - backend/api/query.py
    - dashboard/src/lib/api.ts
    - dashboard/src/views/InvestigationView.svelte
    - tests/eval/test_confidence.py

key-decisions:
  - "Heuristic weights: 0.5 grounding + 0.3 citation_ok + 0.1 rich-context (>=5 ids) — no prompt_template_sha256 term in ask() since template SHA not passed in that scope"
  - "Score write is non-fatal: wrapped in try/except with log.warning to avoid breaking LLM response on DB failure"
  - "Both DDL and ALTER TABLE migration present: DDL covers fresh :memory: test databases, ALTER TABLE covers existing production data/graph.db"
  - "Confidence badge is non-dismissable by requirement — no close button added"

patterns-established:
  - "Backward-compat column migration: add to both _DDL string and as idempotent ALTER TABLE in __init__"
  - "Confidence badge CSS classes: .confidence-high/.medium/.low/.unknown with threshold 0.8/0.5"

requirements-completed: [P22-T02]

# Metrics
duration: 4min
completed: 2026-04-02
---

# Phase 22 Plan 02: Confidence Scoring Summary

**Heuristic LLM confidence score (0.0-1.0) stored in llm_audit_provenance and surfaced as a non-dismissable green/amber/red badge in the InvestigationView copilot panel**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-02T16:20:37Z
- **Completed:** 2026-04-02T16:24:50Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- confidence_score REAL column added to llm_audit_provenance DDL with backward-compat ALTER TABLE migration
- Heuristic score computed in ask() and ask_stream() — grounding context (+0.5), citation verification (+0.3), rich context (+0.1) — then persisted non-fatally via asyncio.to_thread()
- InvestigationView copilot panel now renders a confidence badge on every assistant message, with green (>=0.8), amber (>=0.5), red (<0.5) and grey (unknown) thresholds
- ChatHistoryMessage extended with confidence?, audit_id?, grounding_event_ids? optional fields
- All 4 test_confidence.py tests now pass (skip decorators removed, tests implemented)

## Task Commits

Each task was committed atomically:

1. **Task 1: SQLiteStore DDL + update_confidence_score()** - `0289350` (feat)
2. **Task 2: Heuristic computation and persistence in query.py** - `6b57cf3` (feat)
3. **Task 3: Confidence badge, api.ts extension, test activation** - `b7144de` (feat)

## Files Created/Modified
- `backend/stores/sqlite_store.py` - confidence_score REAL in DDL, idempotent ALTER TABLE migration, update_confidence_score() method
- `backend/api/query.py` - heuristic score computation in ask() and ask_stream(), update_confidence_score() call, confidence_score in JSONResponse
- `dashboard/src/lib/api.ts` - ChatHistoryMessage extended with confidence?, audit_id?, grounding_event_ids?
- `dashboard/src/views/InvestigationView.svelte` - confidenceLevel() helper, confidence badge on assistant messages, CSS for badge variants
- `tests/eval/test_confidence.py` - 4 tests implemented and passing

## Decisions Made
- Heuristic omits prompt_template_sha256 bonus in ask() because the SHA is not available in that scope (it is written by the Ollama service internally). The plan note acknowledges this variant.
- Score write is non-fatal — LLM response is never blocked by a DB failure.
- Both DDL and ALTER TABLE migration are present to handle both fresh (:memory:) and existing databases.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Confidence scoring infrastructure is complete; 22-03 and 22-04 can build on audit_id and confidence_score fields.
- ask() and ask_stream() both emit confidence_score; frontend badge is live.

---
*Phase: 22-ai-lifecycle-hardening*
*Completed: 2026-04-02*
