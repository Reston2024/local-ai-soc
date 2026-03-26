---
phase: 10-compliance-hardening
plan: 02
subsystem: ingestion
tags: [security, injection, normalizer, testing]
dependency_graph:
  requires: [10-01]
  provides: [injection-scrubbing]
  affects: [ingestion/normalizer.py, tests/unit/test_normalizer.py, tests/security/test_injection.py]
tech_stack:
  added: []
  patterns: [compiled-regex-scrubbing, dict-coercion-at-entry]
key_files:
  created: []
  modified:
    - ingestion/normalizer.py
    - tests/unit/test_normalizer.py
    - tests/security/test_injection.py
decisions:
  - "Scrubbing applied in step 7 after clean_str/truncation so it operates on already-sanitized values"
  - "normalize_event() extended to accept raw dicts (coerces to NormalizedEvent) to support security tests and future API use"
  - "String timestamp in dict input is parsed via fromisoformat to avoid AttributeError in _ensure_utc()"
metrics:
  duration: "~10 minutes"
  completed: "2026-03-26"
  tasks_completed: 2
  files_modified: 3
---

# Phase 10 Plan 02: Prompt Injection Scrubbing Summary

**One-liner:** Case-insensitive prompt injection scrubbing via compiled regex added to normalizer, stripping `ignore previous instructions`, `[INST]`, role tokens, `###`, and `---SYSTEM/INSTRUCTION` from five string fields before ChromaDB embedding.

## What Was Built

### Task 1: _INJECTION_PATTERNS and _scrub_injection in normalizer.py

Added to `ingestion/normalizer.py`:

- `_INJECTION_PATTERNS`: compiled `re.compile(r"(?i)(?:...)")` covering 7 injection pattern families
- `_scrub_injection(text: str) -> str`: pure helper that strips matches and strips whitespace
- Step 7 loop in `normalize_event()` applying scrubbing to `command_line`, `raw_event`, `domain`, `url`, `file_path` after the existing clean/truncate steps
- Dict coercion at function entry: `normalize_event()` now accepts `NormalizedEvent | dict`; string timestamps are parsed via `fromisoformat` before Pydantic construction

### Task 2: Tests

Added `TestInjectionScrubbing` class (7 tests) to `tests/unit/test_normalizer.py`:
- `test_ignore_previous_instructions_stripped`
- `test_inst_tokens_stripped`
- `test_system_role_token_stripped`
- `test_triple_hash_stripped`
- `test_normal_command_unchanged`
- `test_domain_field_scrubbed`
- `test_scrub_injection_standalone`

Rewrote `tests/security/test_injection.py`:
- Removed module-level `pytestmark = pytest.mark.xfail`
- `test_injection_patterns_stripped` is now a real (passing) test
- `test_sigma_sql_injection` and `test_path_traversal_rejected` retain per-test `@pytest.mark.xfail`

## Verification Results

Full suite: **97 passed, 13 xfailed, 7 xpassed, 0 failed** (target was 82+ passed, 0 failed).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] String timestamp handling in dict coercion**
- **Found during:** Task 2 test execution
- **Issue:** `_ensure_utc()` calls `.tzinfo` on the value but `NormalizedEvent.timestamp` is typed `Union[datetime, str]`; passing a string timestamp via dict caused `AttributeError: 'str' object has no attribute 'tzinfo'`
- **Fix:** Added explicit `fromisoformat` parsing for `timestamp` and `ingested_at` fields in the dict coercion block before constructing `NormalizedEvent`
- **Files modified:** `ingestion/normalizer.py`
- **Commit:** b04bb7e (included in test commit)

## Self-Check: PASSED

- `ingestion/normalizer.py` — modified, `_INJECTION_PATTERNS` and `_scrub_injection` present
- `tests/unit/test_normalizer.py` — `TestInjectionScrubbing` class with 7 tests present
- `tests/security/test_injection.py` — per-test xfail marks, `test_injection_patterns_stripped` is a real test
- Commits: c419da4 (normalizer), b04bb7e (tests)
