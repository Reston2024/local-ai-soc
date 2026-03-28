---
phase: 14-llmops-evaluation-investigation-ai-copilot
plan: "01"
subsystem: testing
tags: [tdd, wave-0, test-stubs, contracts, eval-harness, investigation-api]
dependency_graph:
  requires: []
  provides:
    - tests/unit/test_eval_models.py
    - tests/unit/test_investigation_timeline.py
    - tests/unit/test_investigation_chat.py
  affects:
    - scripts/eval_models.py (plan 14-02)
    - backend/api/timeline.py (plan 14-03)
    - backend/api/chat.py (plan 14-04)
tech_stack:
  added: []
  patterns:
    - "Safe import pattern: try/except ImportError -> None -> AssertionError per test (Wave-0 TDD stub pattern)"
key_files:
  created:
    - tests/unit/test_eval_models.py
    - tests/unit/test_investigation_timeline.py
    - tests/unit/test_investigation_chat.py
  modified: []
decisions:
  - "Safe import pattern (try/except -> None -> assert not None) chosen over pytest.importorskip to keep tests RED (failing) rather than SKIPPED when modules are absent"
  - "merge_and_sort_timeline tested with 2-argument call to encode the backward-compatible default-parameter contract before implementation"
metrics:
  duration_minutes: 8
  completed_date: "2026-03-28"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 0
---

# Phase 14 Plan 01: Wave-0 Test Stubs — Eval + Investigation API Contracts Summary

Wave-0 TDD stubs for three Phase 14 modules: 8 red tests defining EvalResult/score_response() output contract, 3 red tests defining TimelineItem/merge_and_sort_timeline() API shape, and 3 red tests defining CHAT_MESSAGES_DDL/ChatMessage pydantic model — all using safe-import pattern to ensure AssertionError (not ImportError) before implementation.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Eval harness test stub (8 tests) | 9e6e9cb | tests/unit/test_eval_models.py |
| 2 | Timeline + chat test stubs (6 tests) | 0bdc5ff | tests/unit/test_investigation_timeline.py, tests/unit/test_investigation_chat.py |

## Verification Results

All 14 new tests fail with `AssertionError: <module> not implemented yet` — not ImportError or syntax errors. Pre-existing 556 unit tests continue to pass.

```
tests/unit/test_eval_models.py         - 8 FAILED (red)
tests/unit/test_investigation_timeline.py - 3 FAILED (red)
tests/unit/test_investigation_chat.py  - 3 FAILED (red)
existing suite                         - 556 passed, 1 skipped
```

## Contracts Established

### scripts/eval_models.py (plan 14-02 target)
- `EvalResult`: dataclass/TypedDict with fields `model`, `prompt_id`, `prompt_type`, `latency_ms` (int), `eval_count` (int), `keyword_recall` (float 0.0-1.0), `timestamp` (ISO-8601 str)
- `score_response(response_text, ground_truth_keywords) -> float`: case-insensitive keyword recall; empty keywords returns 1.0; all keywords present returns 1.0; no match returns 0.0

### backend/api/timeline.py (plan 14-03 target)
- `TimelineItem`: pydantic model with `item_id`, `item_type` (Literal event/detection/edge), `timestamp`, `title`, `severity` (Optional), `attack_technique` (Optional), `attack_tactic` (Optional), `entity_labels` (list[str]), `raw_id`
- `merge_and_sort_timeline(event_rows, detection_rows, ...)`: accepts 2 positional args (edge_rows/playbook_rows default), returns list sorted ascending by timestamp

### backend/api/chat.py (plan 14-04 target)
- `CHAT_MESSAGES_DDL`: string containing `CREATE TABLE IF NOT EXISTS chat_messages` with columns `id TEXT`, `investigation_id TEXT`, `role TEXT`, `content TEXT`, `created_at TEXT`
- `ChatMessage`: pydantic model with `investigation_id` (str), `role` (Literal user/assistant), `content` (str)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files created:
- FOUND: tests/unit/test_eval_models.py
- FOUND: tests/unit/test_investigation_timeline.py
- FOUND: tests/unit/test_investigation_chat.py

Commits verified:
- FOUND: 9e6e9cb (test(14-01): add failing test stub for scripts.eval_models)
- FOUND: 0bdc5ff (test(14-01): add failing test stubs for timeline and chat API contracts)
