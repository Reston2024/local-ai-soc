---
phase: 22-ai-lifecycle-hardening
plan: "00"
subsystem: testing
tags: [pytest, eval, fixtures, ndjson, stubs, tdd-scaffold]

# Dependency graph
requires: []
provides:
  - tests/eval/ package skeleton with __init__.py and conftest.py
  - mock_ollama fixture (AsyncMock wrapping OllamaClient HTTP layer)
  - load_event_fixtures() helper for NDJSON fixture loading
  - 5 NDJSON fixture files with realistic event_id values for citation checks
  - 7 stub test files pre-skipped with correct module imports
affects:
  - 22-01-grounding
  - 22-02-confidence
  - 22-03-prompt-eval
  - 22-04-model-drift
  - 22-05-advisory

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "eval/ subdirectory under tests/ for AI lifecycle eval harness"
    - "NDJSON fixtures with event_id values matching MOCK_RESPONSE_TEXT citations"
    - "All stub tests decorated with @pytest.mark.skip(reason='stub — implemented in 22-NN')"

key-files:
  created:
    - tests/eval/__init__.py
    - tests/eval/conftest.py
    - tests/eval/fixtures/analyst_qa_events.ndjson
    - tests/eval/fixtures/triage_events_a.ndjson
    - tests/eval/fixtures/triage_events_b.ndjson
    - tests/eval/fixtures/threat_hunt_events_a.ndjson
    - tests/eval/fixtures/threat_hunt_events_b.ndjson
    - tests/eval/test_grounding.py
    - tests/eval/test_confidence.py
    - tests/eval/test_analyst_qa_eval.py
    - tests/eval/test_triage_eval.py
    - tests/eval/test_threat_hunt_eval.py
    - tests/eval/test_model_drift.py
    - tests/eval/test_advisory.py
  modified: []

key-decisions:
  - "NDJSON fixture event_ids (evt-001, evt-002, evt-003) match MOCK_RESPONSE_TEXT in conftest.py so citation-verify checks will pass when stubs are activated"
  - "mock_ollama fixture attaches _mock_post to OllamaClient instance rather than patching globally — per existing unit test pattern in tests/unit/test_ollama_client.py"
  - "All 7 test files import their target backend/prompts module at module level for fail-fast import error detection when skip decorators are removed"

patterns-established:
  - "Eval stub pattern: import target module at top, @pytest.mark.skip on each function, pass body"
  - "Fixture naming convention: {domain}_events_{variant}.ndjson"

requirements-completed: [P22-T01, P22-T02, P22-T03, P22-T04, P22-T05]

# Metrics
duration: 8min
completed: 2026-04-02
---

# Phase 22 Plan 00: AI Lifecycle Hardening — Eval Scaffold Summary

**tests/eval/ package skeleton with conftest mock_ollama fixture, 5 NDJSON event fixture files, and 18 pre-skipped stub tests spanning grounding, confidence, prompt eval, model drift, and advisory separation**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-02T16:09:02Z
- **Completed:** 2026-04-02T16:17:00Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments

- Created `tests/eval/` package with conftest.py providing `mock_ollama` fixture and `load_event_fixtures()` helper
- Created 5 NDJSON fixture files (analyst_qa: 3 events; triage_a/b: 2 each; threat_hunt_a/b: 2 each) with event_ids matching MOCK_RESPONSE_TEXT citations
- Created 7 stub test files covering all 5 P22 requirements — 18 tests, all skipped, `uv run pytest tests/eval/ -x -q` exits 0

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tests/eval/ package and fixtures** - `459cd3f` (feat)
2. **Task 2: Create all stub test files** - `3a16d1a` (test)

## Files Created/Modified

- `tests/eval/__init__.py` - Package marker
- `tests/eval/conftest.py` - mock_ollama fixture and load_event_fixtures() helper
- `tests/eval/fixtures/analyst_qa_events.ndjson` - 3 events (evt-001, evt-002, evt-003)
- `tests/eval/fixtures/triage_events_a.ndjson` - 2 sysmon events from domain controller
- `tests/eval/fixtures/triage_events_b.ndjson` - 2 events: malware detected + persistence via Run key
- `tests/eval/fixtures/threat_hunt_events_a.ndjson` - 2 events: xp_cmdshell + reverse shell
- `tests/eval/fixtures/threat_hunt_events_b.ndjson` - 2 events: scheduled task + file drop
- `tests/eval/test_grounding.py` - 3 stubs for P22-T01 (grounding threading)
- `tests/eval/test_confidence.py` - 4 stubs for P22-T02 (confidence scoring)
- `tests/eval/test_analyst_qa_eval.py` - 2 stubs for P22-T03 (analyst_qa prompts)
- `tests/eval/test_triage_eval.py` - 2 stubs for P22-T03 (triage prompts)
- `tests/eval/test_threat_hunt_eval.py` - 2 stubs for P22-T03 (threat_hunt prompts)
- `tests/eval/test_model_drift.py` - 3 stubs for P22-T04 (model drift detection)
- `tests/eval/test_advisory.py` - 2 stubs for P22-T05 (advisory separation)

## Decisions Made

- NDJSON fixture event_ids (evt-001, evt-002) match MOCK_RESPONSE_TEXT in conftest.py so citation-verify checks will pass when stubs are activated in later plans
- mock_ollama fixture attaches `_mock_post` to OllamaClient instance — follows existing pattern in `tests/unit/test_ollama_client.py` rather than global patching
- All test files import their target module at module level (e.g., `from backend.api import query`) so import errors surface immediately when skip decorators are removed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 0 Nyquist contract satisfied: `uv run pytest tests/eval/ -x -q` exits 0 with 18 skipped
- Plans 22-01 through 22-05 can now activate their stubs by removing `@pytest.mark.skip` decorators and filling in test logic
- All target module imports pre-validated — any missing module will surface as import error when stub is activated

---
*Phase: 22-ai-lifecycle-hardening*
*Completed: 2026-04-02*
