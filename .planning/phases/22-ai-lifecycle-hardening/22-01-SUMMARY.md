---
phase: 22-ai-lifecycle-hardening
plan: "01"
subsystem: backend/api + backend/services
tags: [grounding, audit, traceability, llm, rag, streaming]
dependency_graph:
  requires: ["22-00"]
  provides:
    - out_context dict pattern in generate() and stream_generate()
    - audit_id, grounding_event_ids, is_grounded in /ask and /ask/stream responses
    - /ask/stream migrated from stream_generate_iter() to stream_generate()
    - test_grounding.py 3 passing tests for P22-T01
  affects:
    - backend/api/query.py
    - backend/services/ollama_client.py
    - tests/eval/test_grounding.py
tech_stack:
  added: []
  patterns:
    - out_context: dict side-channel for returning audit metadata without changing return type
    - on_token callback pattern for SSE streaming with provenance
key_files:
  created: []
  modified:
    - backend/services/ollama_client.py
    - backend/api/query.py
    - tests/eval/test_grounding.py
decisions:
  - "out_context dict pattern preserves str return type of generate()/stream_generate() while threading audit metadata to callers"
  - "operator_id resolved via getattr(request.state, 'operator_id', 'system') one-liner fallback per plan"
  - "ask_stream() migrated to stream_generate()+on_token; tokens buffered then yielded — works correctly since stream_generate() returns after completion"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-02"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
---

# Phase 22 Plan 01: AI Lifecycle Hardening — Grounding Thread-Through Summary

One-liner: Threaded `audit_id` and `grounding_event_ids` from `OllamaClient.generate()`/`stream_generate()` to `/ask` and `/ask/stream` API responses using a non-breaking `out_context` dict side-channel, with `is_grounded` flag and 3 new passing eval tests.

## Tasks Completed

| # | Task | Commit | Key Changes |
|---|------|--------|-------------|
| 1 | Add out_context to generate() and stream_generate() | a18b52c | Added `out_context: dict \| None = None` param to both methods; populates `audit_id` and `grounding_event_ids` after provenance write |
| 2 | Update /ask and /ask/stream + activate test_grounding.py | fbb0d62 | ask(): operator_id resolve, out_ctx, 3 new response fields; ask_stream(): migrated to stream_generate()+on_token; 3 eval tests implemented and passing |

## Verification

```
uv run pytest tests/eval/test_grounding.py -x -v
# 3 passed in 1.38s

uv run pytest tests/unit/ tests/eval/ tests/sigma_smoke/ -q
# 81 failed (pre-existing), 690 passed (+3 new vs baseline 687)
# No regressions introduced
```

## What Was Built

**`backend/services/ollama_client.py`**
- `generate()`: added `out_context: dict | None = None` as last parameter; after provenance write, writes `{"audit_id": audit_id, "grounding_event_ids": grounding_event_ids or []}` into it. Return type unchanged (`str`).
- `stream_generate()`: same pattern using `stream_audit_id`.

**`backend/api/query.py`**
- `ask()`: resolves `operator_id = getattr(request.state, "operator_id", "system")`; passes `grounding_event_ids=ids` and `out_context=out_ctx` to `ollama.generate()`; returns `audit_id`, `grounding_event_ids`, `is_grounded` in the JSONResponse.
- `ask_stream()`: migrated from deprecated `stream_generate_iter()` to `stream_generate()` with `on_token` callback; done-event now includes `audit_id` and `is_grounded`.

**`tests/eval/test_grounding.py`**
- Removed all 3 `@pytest.mark.skip` decorators.
- Implemented tests using FastAPI `TestClient` with patched `backend.core.auth.settings` and Bearer token headers (matching established project pattern).
- Mock `generate()` side_effect populates `out_context` to simulate real behaviour.
- Three tests: `test_grounding_event_ids_in_response`, `test_ungrounded_response`, `test_audit_id_is_uuid`.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- backend/services/ollama_client.py: FOUND
- backend/api/query.py: FOUND
- tests/eval/test_grounding.py: FOUND
- .planning/phases/22-ai-lifecycle-hardening/22-01-SUMMARY.md: FOUND
- Commit a18b52c (Task 1): FOUND
- Commit fbb0d62 (Task 2): FOUND
