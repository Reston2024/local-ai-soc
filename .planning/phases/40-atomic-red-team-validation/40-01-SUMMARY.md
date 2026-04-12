---
phase: 40-atomic-red-team-validation
plan: "01"
subsystem: testing
tags: [atomic-red-team, tdd, sqlite, pytest, yaml, github-api]

# Dependency graph
requires:
  - phase: 39-mitre-car-analytics-integration
    provides: CARStore pattern (sqlite3.Connection param, skipif-importerror guard, seed function)
provides:
  - 8 Wave 0 TDD stubs across 2 test files (SKIP until Plan 02 implements AtomicsStore)
  - backend/services/atomics/__init__.py empty module init
  - scripts/generate_atomics_bundle.py ART YAML catalog fetcher
  - backend/data/atomics.json pre-generated bundle (1773 atomic tests, 328 ATT&CK techniques)
affects:
  - 40-02 (AtomicsStore implementation — stubs define the full contract)
  - 40-03 (atomics API router — test_atomics_api.py stubs define endpoint contract)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 TDD stub pattern: skipif-importerror guard so stubs SKIP (not ERROR) before impl"
    - "ART YAML parsing: None-safe executor/deps access, #{variable} markers preserved"
    - "Bundle generator: urllib.request + retry, TECHNIQUE_PATTERN regex filter, 20-req throttle"

key-files:
  created:
    - tests/unit/test_atomics_store.py
    - tests/unit/test_atomics_api.py
    - backend/services/atomics/__init__.py
    - scripts/generate_atomics_bundle.py
    - backend/data/atomics.json
  modified: []

key-decisions:
  - "AtomicsStore TDD stubs use skipif-importerror guard — 8 stubs SKIP cleanly (not ERROR) until Plan 02 implements the class"
  - "#{variable} markers in ART command strings preserved as-is — substitution is runner responsibility, not bundle generator"
  - "prereq_command joins all get_prereq_command strings with newline---newline separator for multi-dep techniques"
  - "executor.get('command', '') or executor.get('steps', '') — manual executor tests use steps field not command"
  - "generate_bundle exits 0 with warning on empty bundle (network unavailable) — offline-safe"

patterns-established:
  - "ART YAML None-safe access: executor = test.get('executor', {}) or {} handles None executor"
  - "deps = test.get('dependencies') or [] handles None dependencies (not empty list)"

requirements-completed:
  - P40-T01
  - P40-T02
  - P40-T05
  - P40-T06

# Metrics
duration: 18min
completed: 2026-04-12
---

# Phase 40 Plan 01: Atomic Red Team Validation Summary

**Wave 0 TDD stubs (8 SKIP tests across AtomicsStore + atomics API) and pre-generated ART bundle of 1773 atomic tests spanning 328 ATT&CK techniques**

## Performance

- **Duration:** 18 min
- **Started:** 2026-04-12T00:00:00Z
- **Completed:** 2026-04-12T00:18:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created 8 Wave 0 TDD stubs that SKIP cleanly (0 ERROR) — defines AtomicsStore DDL/bulk_insert/idempotent/list_techniques/validation contracts and GET /api/atomics + POST /api/atomics/validate API contracts
- Generated 1773-entry atomics.json bundle from 328 ATT&CK technique YAML files (redcanaryco/atomic-red-team), with all 13 required fields per entry and #{variable} markers preserved
- Empty module init at backend/services/atomics/__init__.py ready for Plan 02 AtomicsStore
- 1020 existing unit tests remain green (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: TDD stubs — test_atomics_store.py, test_atomics_api.py, atomics/__init__.py** - `2e6c6f0` (test)
2. **Task 2: Generate atomics.json bundle** - `ce505bc` (feat)

## Files Created/Modified
- `tests/unit/test_atomics_store.py` - 5 TDD stubs for AtomicsStore (DDL, bulk_insert, idempotent, list_techniques, validation persistence)
- `tests/unit/test_atomics_api.py` - 3 TDD stubs for atomics API (GET /api/atomics, POST /api/atomics/validate pass/fail)
- `backend/services/atomics/__init__.py` - Empty module init for AtomicsStore package
- `scripts/generate_atomics_bundle.py` - One-time ART YAML catalog fetch and flatten to JSON bundle
- `backend/data/atomics.json` - Pre-generated ART catalog (1773 entries, one per atomic test)

## Decisions Made
- AtomicsStore TDD stubs use skipif-importerror guard — identical pattern to CARStore stubs in Plan 39-01
- #{variable} markers preserved as-is in command strings — substitution is the runner's responsibility at execution time
- `executor.get("command", "") or executor.get("steps", "")` handles manual executor tests that use `steps` instead of `command`
- `deps = test.get("dependencies") or []` handles YAML null value for dependencies field (Pitfall 7)
- `generate_bundle` exits 0 with warning when network unavailable — offline-safe for CI environments without GitHub access

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 40-02 can now implement AtomicsStore — all 5 test contract stubs are defined
- Plan 40-03 can implement atomics API router — all 3 API contract stubs are defined
- atomics.json bundle committed, no runtime GitHub dependency in Plans 02-04

---
*Phase: 40-atomic-red-team-validation*
*Completed: 2026-04-12*
