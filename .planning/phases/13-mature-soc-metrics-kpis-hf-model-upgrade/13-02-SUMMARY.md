---
phase: 13-mature-soc-metrics-kpis-hf-model-upgrade
plan: "02"
subsystem: api
tags: [ollama, llm, cybersecurity, foundation-sec, model-routing, pydantic-settings]

# Dependency graph
requires:
  - phase: 13-01
    provides: ADR-020 decision selecting Foundation-Sec-8B as cybersec-specialised model
provides:
  - OLLAMA_CYBERSEC_MODEL env var in Settings (foundation-sec:8b default)
  - OllamaClient.cybersec_model attribute and use_cybersec_model routing flag
  - main.py passes cybersec_model from settings to OllamaClient at startup
affects:
  - backend/api/investigate
  - backend/api/query
  - backend/causality
  - prompts/

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Model routing: use_cybersec_model=True flag on generate()/stream_generate() selects cybersec model at call site"
    - "Fallback pattern: cybersec_model='' in __init__ defaults to self.model, ensuring zero-breaking change"

key-files:
  created:
    - tests/unit/test_config.py
  modified:
    - backend/core/config.py
    - backend/services/ollama_client.py
    - backend/main.py
    - tests/unit/test_ollama_client.py

key-decisions:
  - "cybersec_model falls back to self.model when not provided (empty string default), ensuring zero breaking changes to existing code"
  - "use_cybersec_model=False on generate()/stream_generate() as opt-in flag (not opt-out) so all existing callers are unaffected"
  - "_stream_model local variable introduced in stream_generate() to capture routing before building payload dict"

patterns-established:
  - "ADR-020 routing pattern: call generate(prompt, use_cybersec_model=True) for investigation/triage prompts"

requirements-completed:
  - P13-T02

# Metrics
duration: 8min
completed: 2026-03-27
---

# Phase 13 Plan 02: Cybersec Model Routing Summary

**OLLAMA_CYBERSEC_MODEL env var wired into Settings and OllamaClient with use_cybersec_model=True flag routing investigation/triage prompts to foundation-sec:8b while leaving qwen3:14b flows untouched**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-27T10:51:55Z
- **Completed:** 2026-03-27T10:59:50Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `OLLAMA_CYBERSEC_MODEL: str = "foundation-sec:8b"` to Settings with ADR-020 comment
- Added `cybersec_model` init parameter to OllamaClient with model fallback, and `use_cybersec_model=True` routing flag on `generate()` and `stream_generate()`
- Updated `main.py` to pass `cybersec_model=settings.OLLAMA_CYBERSEC_MODEL` at OllamaClient instantiation
- Created `tests/unit/test_config.py` (3 tests) and added 5 new tests to `test_ollama_client.py`; full suite: 555 passed, 0 regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add OLLAMA_CYBERSEC_MODEL to Settings** - `537f41b` (feat + test)
2. **Task 2: Add cybersec model routing to OllamaClient and update main.py** - `18e2ec0` (feat + test)

**Plan metadata:** (docs commit follows)

_Note: Both tasks used TDD — failing tests written first, then implementation to pass._

## Files Created/Modified

- `backend/core/config.py` - Added `OLLAMA_CYBERSEC_MODEL: str = "foundation-sec:8b"` field with ADR-020 comment
- `backend/services/ollama_client.py` - Added `cybersec_model` init param, `use_cybersec_model` flag on `generate()` and `stream_generate()`, updated log.info
- `backend/main.py` - Lifespan OllamaClient init now passes `cybersec_model=settings.OLLAMA_CYBERSEC_MODEL`
- `tests/unit/test_config.py` - New file: 3 tests for default, env override, and regression
- `tests/unit/test_ollama_client.py` - Added 5 tests for cybersec routing in `TestCybersecModelRouting` class

## Decisions Made

- `cybersec_model` defaults to empty string (`""`) in `__init__`, falling back to `self.model` — ensures all existing OllamaClient instantiations that omit the param are completely unaffected
- `use_cybersec_model=False` is an opt-in flag — callers must explicitly pass `True` to route to the cybersec model; no existing callsite is implicitly changed
- `_stream_model` local variable introduced in `stream_generate()` (mirrors `_effective_model` pattern in `generate()`) for clarity

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required for this plan.

Operators must pull the model before calling `use_cybersec_model=True`:
```bash
ollama pull foundation-sec:8b
```
(Documented in ADR-020; operational prerequisite, not a code issue.)

## Next Phase Readiness

- Cybersec model routing is now available to all call sites via `use_cybersec_model=True` on `generate()` / `stream_generate()`
- Plan 13-03 (or later) can update investigation/triage routes to pass `use_cybersec_model=True` for domain-specific prompts
- No blockers; full suite green

## Self-Check: PASSED

All files confirmed on disk. All task commits confirmed in git history.

---
*Phase: 13-mature-soc-metrics-kpis-hf-model-upgrade*
*Completed: 2026-03-27*
