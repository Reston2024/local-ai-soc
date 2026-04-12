---
phase: 44
plan: 44-01
subsystem: analyst-feedback-loop
title: "Wave 0 — TDD stubs for FeedbackStore and FeedbackClassifier"
tags: [tdd, wave-0, feedback, sqlite, river, stubs]
dependency_graph:
  requires: []
  provides: [test_feedback_store, test_feedback_classifier, FeedbackClassifier, feedback_sqlite_methods]
  affects: [plan-44-02]
tech_stack:
  added: [river>=0.21.0, scipy, pandas]
  patterns: [tdd-wave0, importorskip-stubs, pytest-mark-skip]
key_files:
  created:
    - tests/unit/test_feedback_store.py
    - tests/unit/test_feedback_classifier.py
    - backend/services/feedback/classifier.py
    - backend/services/feedback/__init__.py
  modified:
    - uv.lock
decisions:
  - importorskip pattern used for FeedbackClassifier stubs (survives linter rewrites of skip decorators)
  - background agent pre-implemented FeedbackClassifier and SQLiteStore feedback methods alongside Wave 0 stubs
  - river>=0.21.0 added to uv.lock by background agent (needed for LogisticRegression)
metrics:
  duration_minutes: 5
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 1
  completed_date: "2026-04-12"
requirements_closed: [P44-T01, P44-T02, P44-T03]
---

# Phase 44 Plan 01: Wave 0 TDD Stubs for FeedbackStore and FeedbackClassifier Summary

**One-liner:** Wave 0 TDD stubs created for SQLite FeedbackStore and River FeedbackClassifier using pytest.importorskip pattern; background agent pre-implemented both modules alongside stubs so all 1074 unit tests pass green.

## Tasks Completed

| Task | Description | Commit | Result |
|------|-------------|--------|--------|
| 44-01-01 | SQLite FeedbackStore stubs (7 tests) | 2257909 | 7 SKIP cleanly |
| 44-01-02 | FeedbackClassifier stubs + RED import test | 4d3a3b7 | 1 RED + 6 SKIP initially |
| 44-01-02 (final) | Refactor to importorskip + uv.lock | fad5616 | 7 GREEN (pre-implemented) |
| 44-01-03 | Full suite verification | fad5616 | 1074 passed, 0 failed |

## Verification

- tests/unit/test_feedback_store.py: 7 tests — initially 7 SKIP, then 7 GREEN after background agent implemented feedback methods
- tests/unit/test_feedback_classifier.py: 7 tests — initially 1 RED + 6 SKIP, then 7 GREEN after background agent created classifier.py
- Full suite: 1074 passed, 10 skipped, 0 failed — no regressions from 1067 baseline

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Auto-fix] Linter removed pytest.mark.skip decorators from FeedbackClassifier test stubs**
- **Found during:** Task 44-01-02
- **Issue:** Background linter removed `_skip` variable and all `@_skip` decorators, converting stubs to active tests
- **Fix:** Rewrote stubs using `pytest.importorskip()` inside each test function body — linter-proof pattern that skips when module is absent
- **Files modified:** tests/unit/test_feedback_classifier.py
- **Commit:** fad5616

### Pre-execution by Background Agent

**Background agent pre-implemented Plan 44-02 scope** — This is informational, not a deviation from 44-01:
- Created `backend/services/feedback/classifier.py` (River LogisticRegression FeedbackClassifier with learn_one, predict_proba_tp, accuracy, save/load)
- Added `backend/services/feedback/__init__.py`
- Added SQLiteStore feedback methods (upsert_feedback, get_verdict_for_detection, get_feedback_stats)
- Added `river>=0.21.0` to pyproject.toml and uv.lock
- Committed as `feat(44-02)` commits (d1ac1c3, f4b4f8c)

**Impact on Plan 44-02:** The implementation is already complete. Plan 44-02 should focus on integration wiring, API endpoints, and verifying the pre-implemented code meets all behavioral contracts.

## Self-Check: PASSED

- tests/unit/test_feedback_store.py: FOUND
- tests/unit/test_feedback_classifier.py: FOUND
- Commits 2257909, 4d3a3b7, fad5616: FOUND
