---
phase: 14-llmops-evaluation-investigation-ai-copilot
plan: "06"
subsystem: testing
tags: [eval, duckdb, dry-run, llm, pytest]

# Dependency graph
requires:
  - phase: 14-llmops-evaluation-investigation-ai-copilot
    provides: scripts/eval_models.py with EvalResult, score_response, _eval_one_row

provides:
  - DuckDB-free --dry-run mode in eval_models.py using synthetic placeholder rows
  - Unit tests for _eval_one_row dry-run behavior (triage and summarise)

affects:
  - Any CI/CD pipeline running eval_models.py --dry-run while backend is active

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bypass exclusive-lock resources (DuckDB) in dry-run paths — generate synthetic tuples instead of reading from DB"

key-files:
  created: []
  modified:
    - scripts/eval_models.py
    - tests/unit/test_eval_models.py

key-decisions:
  - "14-06: Synthetic placeholder rows instead of read_only DuckDB connection — read_only also fails when backend holds write lock"
  - "14-06: DRY_RUN_ROW tuple defined locally inside dry-run branch, not as module-level constant"

patterns-established:
  - "Eval dry-run: args.dry_run checked immediately after arg parse; DuckDB block in else branch"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-03-28
---

# Phase 14 Plan 06: Gap Closure — Eval Harness Dry-Run DuckDB Lock Summary

**eval_models.py --dry-run bypasses DuckDB entirely via synthetic placeholder rows, eliminating the IOException when backend holds the write lock**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-28T12:00:00Z
- **Completed:** 2026-03-28T12:05:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Fixed `duckdb.duckdb.IOException: IO Error: File is already open` in `--dry-run` mode
- DuckDB initialization now guarded by `if args.dry_run / else` branch — no lock acquired in dry-run path
- Generates `args.limit` synthetic `_DRY_RUN_ROW` tuples (realistic dummy data) for the eval loop
- Added 2 unit tests covering `_eval_one_row` dry-run mode for both `triage` and `summarise` prompt types
- All 10 unit tests green; `--dry-run --limit 5` produces 4-row markdown table + 20 JSONL entries

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix eval_models.py dry-run DuckDB bypass** - `b6e8452` (fix)

## Files Created/Modified

- `scripts/eval_models.py` — DuckDB init moved into `else` branch; dry-run path generates synthetic rows
- `tests/unit/test_eval_models.py` — Added `_eval_one_row` import and two dry-run unit tests

## Decisions Made

- Used synthetic placeholder tuples instead of `duckdb.connect(read_only=True)` — the read-only connection also fails while the backend holds an exclusive write lock (confirmed in plan notes)
- `_DRY_RUN_ROW` defined locally inside the `if args.dry_run` block — avoids polluting module namespace; consistent with plan pseudocode

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- UAT gap test 2 is now satisfied: `--dry-run --limit 5` works without errors while backend is running
- eval_models.py is fully functional for both dry-run and live modes

---
*Phase: 14-llmops-evaluation-investigation-ai-copilot*
*Completed: 2026-03-28*
