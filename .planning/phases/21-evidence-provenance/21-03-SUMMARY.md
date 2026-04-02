---
phase: 21-evidence-provenance
plan: "03"
subsystem: provenance
tags: [sqlite, provenance, llm, audit, ollama]
dependency_graph:
  requires: ["21-01", "21-02"]
  provides: ["llm_audit_provenance table", "record_llm_provenance", "get_llm_provenance", "GET /api/provenance/llm/{audit_id}", "TEMPLATE_SHA256"]
  affects: ["backend/stores/sqlite_store.py", "backend/services/ollama_client.py", "backend/api/provenance.py", "prompts/analyst_qa.py"]
tech_stack:
  added: []
  patterns: ["TDD RED/GREEN", "INSERT OR IGNORE deduplication", "asyncio.to_thread for blocking SQLite writes", "non-fatal try/except for telemetry writes"]
key_files:
  created: []
  modified:
    - backend/stores/sqlite_store.py
    - backend/services/ollama_client.py
    - backend/api/provenance.py
    - prompts/analyst_qa.py
    - tests/unit/test_llm_provenance.py
decisions:
  - "Used INSERT OR IGNORE for provenance deduplication so duplicate audit_ids are silently discarded without errors"
  - "Made sqlite_store optional on OllamaClient (default None) to avoid breaking existing tests and callers that don't pass a store"
  - "Used asyncio.to_thread() for SQLite provenance writes inside async generate/stream_generate per CLAUDE.md conventions"
  - "Wrapped provenance writes in non-fatal try/except so a store failure never breaks an LLM call"
  - "API test uses minimal FastAPI app with just the provenance router (not full create_app()) to avoid DuckDB file-lock issues in unit tests"
metrics:
  duration_seconds: 336
  completed_date: "2026-04-02"
  tasks_completed: 2
  files_modified: 5
---

# Phase 21 Plan 03: LLM Audit Provenance Summary

**One-liner:** SQLite llm_audit_provenance table with record/get methods, audit_id threading through OllamaClient.generate/stream_generate, and GET /api/provenance/llm/{audit_id} endpoint.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | llm_audit_provenance DDL + record/get methods; TEMPLATE_SHA256 in analyst_qa.py | 5c4d628 | GREEN |
| 2 | audit_id threading in OllamaClient; provenance write at completion; LLM provenance API endpoint | 588ba03 | GREEN |

## What Was Built

### SQLiteStore additions (backend/stores/sqlite_store.py)

Added `llm_audit_provenance` table to the `_DDL` string with columns:
- `audit_id TEXT PRIMARY KEY` — unique per logical LLM call (UUID4)
- `model_id TEXT NOT NULL` — the Ollama model string used
- `prompt_template_name TEXT` — e.g. "analyst_qa"
- `prompt_template_sha256 TEXT` — 64-char hex SHA-256 of the template file
- `response_sha256 TEXT` — 64-char hex SHA-256 of the raw LLM response
- `operator_id TEXT` — calling operator (nullable)
- `grounding_event_ids TEXT NOT NULL DEFAULT '[]'` — JSON array of event IDs
- `created_at TEXT NOT NULL` — ISO-8601 UTC timestamp

Two new methods on `SQLiteStore`:
- `record_llm_provenance(audit_id, model_id, prompt_template_name, prompt_template_sha256, response_sha256, grounding_event_ids, operator_id=None)` — INSERT OR IGNORE
- `get_llm_provenance(audit_id)` — returns dict with grounding_event_ids as parsed list[str], or None

### OllamaClient updates (backend/services/ollama_client.py)

- Added `sqlite_store: Optional[SQLiteStore] = None` parameter to `__init__()`, stored as `self._sqlite`
- Added `uuid4` import at module top (was missing, already had `hashlib`)
- Added optional `prompt_template_name`, `prompt_template_sha256`, `grounding_event_ids` params to both `generate()` and `stream_generate()`
- `generate()`: creates `audit_id = str(uuid4())` at start, writes provenance row via `asyncio.to_thread()` after successful response, wrapped in non-fatal try/except
- `stream_generate()`: same pattern with `stream_audit_id`, writes provenance row only once at stream completion (after `_write_telemetry`), not on "start" or per-chunk

### Provenance API (backend/api/provenance.py)

Added `GET /api/provenance/llm/{audit_id}` endpoint returning `LlmProvenanceRecord` (404 if not found).

### Template fingerprinting (prompts/analyst_qa.py)

Appended at module bottom (capturing full source):
- `TEMPLATE_SHA256: str` — 64-char hex SHA-256 of the module's own source file, computed at import time
- `TEMPLATE_NAME: str = "analyst_qa"`

### main.py update

OllamaClient instantiation now passes `sqlite_store=sqlite_store` so live LLM calls write provenance rows.

## Test Results

```
tests/unit/test_llm_provenance.py::test_llm_provenance_table_exists PASSED
tests/unit/test_llm_provenance.py::test_llm_provenance_written PASSED
tests/unit/test_llm_provenance.py::test_llm_provenance_no_duplicate_rows PASSED
tests/unit/test_llm_provenance.py::test_llm_provenance_api PASSED

4 passed in 0.23s
```

Full unit suite: 82 failed (pre-existing), 657 passed — no regressions introduced.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test stubs used asyncio.get_event_loop() (deprecated in Python 3.12)**
- **Found during:** Task 2
- **Issue:** `asyncio.get_event_loop().run_until_complete()` raises DeprecationWarning in Python 3.12 test contexts
- **Fix:** Changed to `asyncio.run()` in both test helpers
- **Files modified:** tests/unit/test_llm_provenance.py

**2. [Rule 3 - Blocking] test_llm_provenance_api used create_app() which opened DuckDB causing IOException**
- **Found during:** Task 2
- **Issue:** Full app lifespan opens DuckDB on disk; the file was already locked by another process during test run
- **Fix:** Replaced with minimal FastAPI + just the provenance router + dependency_overrides, matching the pattern used in test_detection_provenance.py
- **Files modified:** tests/unit/test_llm_provenance.py

## Self-Check: PASSED
