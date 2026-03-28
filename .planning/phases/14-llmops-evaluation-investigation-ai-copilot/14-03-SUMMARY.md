---
phase: 14-llmops-evaluation-investigation-ai-copilot
plan: "03"
subsystem: llmops-monitoring
tags: [duckdb, ollama, telemetry, metrics, kpi]
dependency_graph:
  requires: [14-01]
  provides: [llm-call-telemetry, llm-kpi-aggregates]
  affects: [backend/stores/duckdb_store.py, backend/services/ollama_client.py, backend/services/metrics_service.py, backend/main.py]
tech_stack:
  added: []
  patterns:
    - "DuckDB write-queue pattern for llm_calls INSERT via execute_write()"
    - "Optional dependency injection — duckdb_store=None default preserves backward compat"
    - "monotonic_ns() timing → integer ms latency recording"
    - "TYPE_CHECKING guard for DuckDBStore import to avoid circular import"
key_files:
  created: []
  modified:
    - backend/stores/duckdb_store.py
    - backend/services/ollama_client.py
    - backend/services/metrics_service.py
    - backend/main.py
    - tests/unit/test_ollama_client.py
    - tests/unit/test_metrics_service.py
decisions:
  - "duckdb_store=None default in OllamaClient.__init__: zero breaking changes; existing callers unaffected"
  - "INSERT OR IGNORE used for llm_calls rows: idempotent on UUID PK collision (effectively impossible but safe)"
  - "TYPE_CHECKING guard for DuckDBStore: avoid circular import at runtime while preserving type hints"
  - "_compute_llm_kpis() catches all exceptions and returns defaults: metrics never crash KPI endpoint"
  - "stream_generate() telemetry written after full stream completes in success path, immediately in error paths"
metrics:
  duration_seconds: 266
  tasks_completed: 2
  tasks_total: 2
  files_modified: 6
  tests_added: 16
  completed_date: "2026-03-28"
---

# Phase 14 Plan 03: LLMOps Monitoring Layer Summary

**One-liner:** DuckDB llm_calls telemetry table with per-call timing/error recording in OllamaClient and LLMOps aggregate KPIs added to the metrics endpoint.

## What Was Built

### Task 1: DuckDB llm_calls DDL + OllamaClient telemetry hook

Added `_CREATE_LLM_CALLS_TABLE` DDL and two indexes to `duckdb_store.py`. The `initialise_schema()` method creates the table and indexes on every startup (idempotent `CREATE IF NOT EXISTS`).

Updated `OllamaClient.__init__` to accept `duckdb_store: Optional[DuckDBStore] = None` — existing callers passing no store continue to work unchanged. Added `_write_telemetry()` private async method that inserts one row into `llm_calls` with UUID call_id, UTC timestamp, model name, endpoint identifier, prompt/completion char counts, latency in ms, success flag, and error type.

Wrapped `generate()` with `time.monotonic_ns()` before the httpx call; telemetry is written on success return and in both error paths (HTTPStatusError and generic Exception). Wrapped `stream_generate()` similarly — telemetry is written after the full stream loop completes on success, and immediately in error paths.

Added `use_cybersec_model: bool = False` param to `stream_generate_iter()` for consistency with `generate()` and `stream_generate()`.

Updated `main.py` lifespan to pass `duckdb_store=duckdb_store` when constructing `OllamaClient`.

### Task 2: LLMOps KPI aggregates in metrics endpoint

Added three fields to `KpiSnapshot` in `metrics_service.py`:
- `avg_latency_ms_per_model: dict[str, float] = {}`
- `total_llm_calls: int = 0`
- `error_rate: float = 0.0`

Added `_compute_llm_kpis(duckdb_store)` async helper that queries `llm_calls GROUP BY model` to compute per-model average latency, total call count, and error rate. Catches all exceptions (including `CatalogException` if table doesn't exist yet) and returns empty defaults. Called from `compute_all_kpis()` alongside the existing 9 KPI compute coroutines.

## Test Results

- `tests/unit/test_ollama_client.py`: 36 passed (29 pre-existing + 7 new TDD tests)
- `tests/unit/test_metrics_service.py`: 29 passed (22 pre-existing + 7 new TDD tests)
- Full unit suite: 581 passed, 1 pre-existing failure (`test_investigation_chat.py` — `backend.api.chat` not yet implemented, out of scope)

## Commits

| Hash | Message |
| --- | --- |
| `7bacee3` | test(14-03): add failing tests for OllamaClient duckdb_store telemetry hook |
| `2f42d28` | feat(14-03): implement LLMOps telemetry — llm_calls DDL and OllamaClient hook |
| `24ffac6` | test(14-03): add failing tests for LLMOps KPI fields in KpiSnapshot |
| `8b8907f` | feat(14-03): extend KpiSnapshot with LLMOps aggregates from llm_calls table |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `backend/stores/duckdb_store.py` — modified, `_CREATE_LLM_CALLS_TABLE` present
- `backend/services/ollama_client.py` — modified, `_write_telemetry` present, `duckdb_store` param present
- `backend/services/metrics_service.py` — modified, `avg_latency_ms_per_model` field present, `_compute_llm_kpis` present
- `backend/main.py` — modified, `duckdb_store=duckdb_store` passed to OllamaClient
- All 4 task commits confirmed in git log
