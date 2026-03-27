---
phase: 12-api-hardening-parser-coverage
plan: 03
subsystem: testing
tags: [pytest, coverage, evtx, windows-event-log, unittest.mock, pyevtx-rs]

# Dependency graph
requires:
  - phase: 12-01
    provides: rate-limiting foundation and test infrastructure (TESTING=1 guard)
provides:
  - 50 pytest unit tests covering all evtx_parser.py code paths
  - evtx_parser.py coverage raised from 15% to 97%
  - Mock patterns for pyevtx-rs PyEvtxParser without binary fixture files
affects: [12-04, future-coverage-gates]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "unittest.mock.patch('ingestion.parsers.evtx_parser.evtx.PyEvtxParser') for mocking pyevtx-rs"
    - "Hand-crafted JSON record dicts matching pyevtx-rs output format"
    - "Module-level fixture constants (SYSMON_PROCESS_CREATE, SECURITY_LOGON, etc.) shared across test classes"

key-files:
  created:
    - tests/unit/test_evtx_parser.py
  modified: []

key-decisions:
  - "Used unittest.mock.patch on 'ingestion.parsers.evtx_parser.evtx.PyEvtxParser' (not the evtx module directly) to correctly intercept the class at the usage site"
  - "Hand-crafted JSON record dicts match the exact pyevtx-rs dict format: {event_record_id, timestamp, data} where data is a JSON string"
  - "No binary .evtx fixture files added — all test data is Python dicts / json.dumps strings"
  - "CI coverage gate uses --cov=backend --cov=ingestion --cov=detections scope (not total project), achieving 73.26% well above the 70% threshold"

patterns-established:
  - "EVTX mock pattern: MagicMock().records_json.return_value = [record_dict] with patch on PyEvtxParser"
  - "Module-level record constants reused across TestParseRecord and TestEvtxParserParse for consistency"

requirements-completed: [P12-T03, P12-T04]

# Metrics
duration: 7min
completed: 2026-03-27
---

# Phase 12 Plan 03: EVTX Parser Unit Tests Summary

**50 pytest unit tests raising evtx_parser.py coverage from 15% to 97% using hand-crafted dicts and unittest.mock — no binary .evtx files added; CI coverage gate holds at 73.26%**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-27T07:38:08Z
- **Completed:** 2026-03-27T07:45:00Z
- **Tasks:** 1 (TDD — implementation already existed, tests written to GREEN)
- **Files modified:** 1

## Accomplishments
- 50 tests across 7 classes covering every code path in evtx_parser.py
- evtx_parser.py coverage: 15% → 97% (4 uncovered lines remain — dead branches in EventID dict-node parsing)
- Full CI coverage suite passes at 73.26% (threshold 70%)
- Zero binary fixture files added — pure Python dict approach documented as a reusable pattern

## Task Commits

1. **Task 1: Write EVTX parser unit tests** - `1a3426a` (test)

**Plan metadata:** (pending docs commit)

## Files Created/Modified
- `tests/unit/test_evtx_parser.py` - 50 unit tests for all evtx_parser.py code paths: _parse_timestamp, _extract_field, _safe_int, _determine_event_type, _flatten_event_data, _parse_record, EvtxParser.parse()

## Decisions Made
- Patched at the usage site `ingestion.parsers.evtx_parser.evtx.PyEvtxParser` rather than the evtx module itself — ensures the mock intercepts the reference the module already holds
- The CORRUPT_DATA_RECORD test (invalid JSON) does NOT exercise the exception-skip path in parse() — the parser degrades gracefully to an empty event rather than raising. The `test_per_record_hard_exception_skips` test uses a non-JSON-serialisable object() to actually trigger the except branch in parse()
- CI coverage scope: `--cov=backend --cov=ingestion --cov=detections` (matches .github/workflows/ci.yml) gives 73.26% vs the incorrect `tests/` total which includes uncovered infrastructure

## Deviations from Plan

None — plan executed exactly as written. Target was 80%; achieved 97%.

## Issues Encountered
- Coverage invocation with `--cov=ingestion/parsers/evtx_parser` (slash notation) produced "module-not-imported" warning — must use dot notation `--cov=ingestion.parsers.evtx_parser` or the full `--cov=ingestion` scope. Resolved by using dot notation.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- evtx_parser.py is now regression-proof; field mapping changes (e.g., SubjectUserName → username) will immediately surface as test failures
- P12-T03 (EVTX coverage) and P12-T04 (70% gate) requirements both satisfied
- Ready to proceed to plan 12-04 (coverage gate enforcement / CI hardening)

---
*Phase: 12-api-hardening-parser-coverage*
*Completed: 2026-03-27*
