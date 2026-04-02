---
phase: 22-ai-lifecycle-hardening
plan: "03"
subsystem: testing
tags: [pytest, eval-harness, ollama, mock, prompt-templates, analyst-qa, triage, threat-hunt]

# Dependency graph
requires:
  - phase: 22-ai-lifecycle-hardening
    provides: eval harness infrastructure (conftest.py, NDJSON fixtures, mock_ollama fixture)
provides:
  - 6 passing eval tests across analyst_qa, triage, threat_hunt prompt templates
  - analyst_qa eval: response event ID reference check + citation hallucination check
  - triage eval: fixture A severity check + fixture B completion check
  - threat_hunt eval: fixture A hypothesis test + fixture B completion check
affects:
  - 22-ai-lifecycle-hardening
  - future prompt template additions

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mock Ollama via patch.object(_client.post) — no live server required"
    - "load_event_fixtures() imports NDJSON fixture dicts, json.dumps each for context_events"
    - "Vacuous-truth citation pass: triage/threat_hunt IDs absent from MOCK_RESPONSE_TEXT — verify_citations returns True"

key-files:
  created: []
  modified:
    - tests/eval/test_analyst_qa_eval.py
    - tests/eval/test_triage_eval.py
    - tests/eval/test_threat_hunt_eval.py

key-decisions:
  - "Used load_event_fixtures() as plain function import (not pytest fixture) — conftest.py exposes it both ways"
  - "Triage and threat_hunt tests rely on vacuous-truth citation pass since fixture IDs do not appear in MOCK_RESPONSE_TEXT"
  - "analyst_qa test asserts evt-001/evt-002 in result because MOCK_RESPONSE_TEXT explicitly cites those IDs"

patterns-established:
  - "Eval test pattern: load_event_fixtures -> json.dumps each -> build_prompt -> patch.object -> generate -> assert"

requirements-completed: [P22-T03]

# Metrics
duration: 8min
completed: 2026-04-02
---

# Phase 22 Plan 03: Prompt Template Eval Tests Summary

**6 passing eval tests for analyst_qa, triage, and threat_hunt prompt templates — mocked HTTP layer, no live Ollama required**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-02T16:25:00Z
- **Completed:** 2026-04-02T16:33:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Implemented 2 passing tests for analyst_qa eval: event ID reference check and verify_citations hallucination guard
- Implemented 2 passing tests for triage eval: fixture A keyword check and fixture B completion/exact-match
- Implemented 2 passing tests for threat_hunt eval: fixture A hypothesis build + fixture B exact-match
- All 6 tests use mocked httpx HTTP layer via `patch.object(mock_ollama._client, "post", new=mock_ollama._mock_post)` — no live Ollama

## Task Commits

Each task was committed atomically:

1. **Task 1: analyst_qa eval tests** - `5a11f07` (test)
2. **Task 2: triage and threat_hunt eval tests** - `7ed2a15` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `tests/eval/test_analyst_qa_eval.py` - Removed @pytest.mark.skip stubs, implemented 2 real tests using analyst_qa fixtures and verify_citations
- `tests/eval/test_triage_eval.py` - Removed @pytest.mark.skip stubs, implemented 2 real tests using triage_events_a/b.ndjson
- `tests/eval/test_threat_hunt_eval.py` - Removed @pytest.mark.skip stubs, implemented 2 real tests using threat_hunt_events_a/b.ndjson

## Decisions Made
- Confirmed `threat_hunt.build_prompt` takes `hypothesis` and `context_events` (not `events`) before writing tests
- Used `load_event_fixtures` as a plain function import from conftest, not as a pytest fixture parameter — the conftest exposes it both ways, but direct import is cleaner for these tests
- Triage and threat_hunt citation checks rely on vacuous truth: MOCK_RESPONSE_TEXT cites `[evt-001]`/`[evt-002]` which are not in triage/threat_hunt fixture IDs, but test_triage_response_fixture_b/test_threat_hunt_hypothesis_fixture_b assert `result == MOCK_RESPONSE_TEXT` (exact match) rather than verify_citations

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing unit test failure (`test_list_detections_returns_200` returning 401) confirmed to be unrelated to this plan — was failing before any changes in this plan. Logged as out-of-scope.

## Next Phase Readiness
- Eval harness fully functional with 6 passing tests
- eval/ test directory ready for additional prompt templates as they are added
- No blockers

---
*Phase: 22-ai-lifecycle-hardening*
*Completed: 2026-04-02*
