---
phase: 16-security-hardening
plan: "05"
subsystem: backend-security
tags:
  - citation-verification
  - llm-security
  - prompt-injection
  - audit-logging
  - security-hardening
dependency_graph:
  requires:
    - 16-01
    - 16-03
  provides:
    - verify_citations() pure function in backend/api/query.py
    - citation_verified bool in /query/ask JSONResponse
    - citation_verified bool in /investigations/{id}/chat SSE done event
    - TestInjectionScrubbing NormalizedEvent-path tests (P16-SEC-03a coverage)
    - llm_audit logger handler smoke test (P16-SEC-03c coverage)
  affects:
    - backend/api/query.py
    - backend/api/chat.py
    - tests/unit/test_api_endpoints.py
    - tests/unit/test_normalizer.py
    - tests/unit/test_investigation_chat.py
tech_stack:
  added:
    - "re module (stdlib): _CITATION_RE pattern for [id] extraction"
    - "UUID regex pattern for context ID extraction in chat SSE"
  patterns:
    - "Pure-function citation verifier: verify_citations(response_text, context_ids) -> bool"
    - "vacuous truth: no citations in response returns True"
    - "Warning log emitted when citation_verified=False"
key_files:
  created: []
  modified:
    - backend/api/query.py
    - backend/api/chat.py
    - tests/unit/test_api_endpoints.py
    - tests/unit/test_normalizer.py
    - tests/unit/test_investigation_chat.py
decisions:
  - "verify_citations() is a pure module-level function in query.py, importable from chat.py without circular dependency"
  - "Chat context uses UUID regex to extract IDs from timeline string (not Chroma ID list)"
  - "audit logger test resets _INITIALIZED flag temporarily to exercise full setup path; restores original state in finally block"
  - "4 new TestInjectionScrubbing tests use make_event()/NormalizedEvent path (not raw dicts) to prove the NormalizedEvent code path is scrubbed"
metrics:
  duration_seconds: 208
  completed_date: "2026-03-31"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 5
  files_created: 0
requirements_satisfied:
  - P16-SEC-03a
  - P16-SEC-03b
  - P16-SEC-03c
---

# Phase 16 Plan 05: Citation Verification and Security Test Coverage Summary

**One-liner:** LLM response citation verification via [id]-regex in query.py/chat.py, with injection-scrubbing and audit-logger smoke tests confirming all three P16-SEC-03 requirements.

## What Was Built

### Task 1: verify_citations() and /query/ask citation_verified (P16-SEC-03b)

Added `verify_citations(response_text, context_ids)` as a pure module-level function in `backend/api/query.py`. The function:
- Compiles `_CITATION_RE = re.compile(r"\[([^\]]{3,64})\]")` to extract `[id]` citation patterns
- Returns `True` vacuously when no citations are found
- Returns `True` only when every cited ID exists in the `context_ids` set
- Returns `False` if any cited ID is absent from context

The `/query/ask` endpoint now:
1. Calls `citation_ok = verify_citations(answer, ids)` after `ollama.generate()`
2. Emits `log.warning("Unverified citations in LLM response", ...)` when `citation_ok=False`
3. Includes `"citation_verified": citation_ok` in the `JSONResponse` content

4 unit tests in `tests/unit/test_api_endpoints.py` cover all/fake/none/mixed citation cases.

### Task 2: chat.py SSE done event + P16-SEC-03a/03c test coverage

Updated `backend/api/chat.py`:
- Added `import re` at module level (not inside function)
- Added `from backend.api.query import verify_citations` import
- After stream completes, extracts UUID-format IDs from the context string using `re.compile(r"\b[0-9a-f]{8}-...\b")`
- Calls `verify_citations(full_response, context_ids_found)`
- Yields `{"done": True, "citation_verified": citation_ok}` as final SSE event

Added 4 new tests to `TestInjectionScrubbing` in `tests/unit/test_normalizer.py`:
- `test_command_line_injection_stripped`: proves "ignore previous instructions" is scrubbed via `NormalizedEvent` path (P16-SEC-03a)
- `test_command_line_clean_preserved`: proves benign commands are not modified
- `test_domain_injection_stripped`: proves domain injection via `NormalizedEvent` path
- `test_url_injection_stripped`: proves `---SYSTEM` pattern in URL is scrubbed

Added `test_llm_audit_logger_has_handler` to `tests/unit/test_investigation_chat.py` (P16-SEC-03c):
- Temporarily resets `_INITIALIZED` flag so `setup_logging()` runs fully
- Verifies `llm_audit` logger has at least 1 handler after setup
- Verifies `llm_audit.propagate == False`
- Restores original `_INITIALIZED` state in `finally` block

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 0fba0e9 | feat(16-05): implement verify_citations() and add citation_verified to /query/ask |
| 2 | 900fa69 | feat(16-05): add citation_verified to chat SSE done event; add P16-SEC-03a/03c tests |

## Test Results

All new tests pass:
- 4 citation unit tests in test_api_endpoints.py: PASSED
- 11 TestInjectionScrubbing tests (7 existing + 4 new): PASSED
- 1 audit logger handler test: PASSED

Total unit suite: 519 passed (81 pre-existing failures in unrelated auth/rate-limit tests, unchanged from before this plan).

## Deviations from Plan

### Auto-fixed Issues

None.

### Adaptations

**1. [Rule 2 - Missing coverage] audit logger test uses tmp_path fixture and resets _INITIALIZED**
- **Found during:** Task 2
- **Issue:** Plan specified `/tmp/test_logs_audit` which is not portable on Windows; also `setup_logging()` is idempotent — if `_INITIALIZED=True` from prior test imports, the test would not exercise the setup code
- **Fix:** Used `tmp_path` pytest fixture for portable temp directory; temporarily reset `_INITIALIZED=False` with `finally` block to restore state
- **Files modified:** tests/unit/test_investigation_chat.py

**2. [Observation] TestInjectionScrubbing already existed**
- **Found during:** Task 2
- **Issue:** The plan described adding a `TestInjectionScrubbing` class but one already existed with 7 tests using raw dicts
- **Fix:** Added 4 new test methods using `make_event()/NormalizedEvent` path to the existing class (complementary, not duplicate)
- **Files modified:** tests/unit/test_normalizer.py

## Self-Check

Verified files exist and commits recorded:
- `backend/api/query.py` — contains `verify_citations`, `_CITATION_RE`, `citation_verified`
- `backend/api/chat.py` — contains `import re`, `from backend.api.query import verify_citations`, `citation_verified`
- `tests/unit/test_api_endpoints.py` — contains 4 citation tests
- `tests/unit/test_normalizer.py` — contains 4 new NormalizedEvent-path injection tests
- `tests/unit/test_investigation_chat.py` — contains `test_llm_audit_logger_has_handler`
