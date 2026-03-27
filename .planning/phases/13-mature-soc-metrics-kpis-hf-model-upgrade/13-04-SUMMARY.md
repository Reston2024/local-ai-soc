---
phase: 13-mature-soc-metrics-kpis-hf-model-upgrade
plan: "04"
subsystem: backend-metrics
tags: [metrics, kpi, apscheduler, fastapi, pydantic, tdd]
dependency_graph:
  requires: ["13-02", "13-03"]
  provides: ["GET /api/metrics/kpis", "MetricsService", "KpiSnapshot", "KpiValue"]
  affects: ["backend/main.py", "backend/api/metrics.py", "backend/services/metrics_service.py"]
tech_stack:
  added: ["apscheduler>=3.10.0,<4.0"]
  patterns: ["APScheduler AsyncIOScheduler 60s background cache", "TDD red-green cycle", "asyncio.gather for concurrent KPI computation", "module-level cache pattern"]
key_files:
  created:
    - backend/services/metrics_service.py
    - backend/api/metrics.py
    - tests/unit/test_metrics_service.py
    - tests/unit/test_metrics_api.py
  modified:
    - backend/main.py
    - pyproject.toml
    - uv.lock
decisions:
  - "APScheduler module-level singleton pattern: _kpi_cache and _scheduler as module globals allow cache to survive across requests within the single uvicorn worker"
  - "Cold-start inline compute: first request computes KPIs synchronously rather than returning 503, trading latency on first call for reliability"
  - "FP rate proxy: count(low-severity, no case_id) / count(all) — true FP tracking deferred until analyst feedback UI is implemented"
  - "MTTC vs MTTR: MTTC uses status='closed' only; MTTR uses status != 'active' (broader — includes any non-active case)"
metrics:
  duration: "3m 24s"
  completed_date: "2026-03-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 3
  tests_added: 27
  tests_passing: 582
---

# Phase 13 Plan 04: SOC Metrics KPI Backend Summary

**One-liner:** Full KPI backend with MetricsService (9 functions, asyncio.gather), GET /api/metrics/kpis, and APScheduler 60s cache backed by DuckDB + SQLite stores.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | MetricsService with typed KPI models | b7319e1 | backend/services/metrics_service.py, tests/unit/test_metrics_service.py |
| 2 | GET /api/metrics/kpis + APScheduler + main.py | 42be0ad | backend/api/metrics.py, backend/main.py, pyproject.toml, uv.lock, tests/unit/test_metrics_api.py |

## What Was Built

### backend/services/metrics_service.py

Pydantic models `KpiValue` (label, value, unit, trend) and `KpiSnapshot` (9 KPI fields + computed_at).

`MetricsService` with 9 async methods:
- `compute_mttd()` — oldest detection vs oldest event timestamp gap (minutes)
- `compute_mttr()` — avg age of non-active cases (minutes)
- `compute_mttc()` — avg age of closed cases (minutes)
- `compute_false_positive_rate()` — low-severity no-case detections / total detections
- `compute_alert_volume()` — detection count in last 24h from SQLite
- `compute_active_rules()` — distinct rule_ids in detections table
- `compute_open_cases()` — cases with status='active'
- `compute_assets_monitored()` — distinct non-null hostnames from DuckDB
- `compute_log_sources()` — distinct non-null source_type from DuckDB

`compute_all_kpis()` runs all 9 concurrently via `asyncio.gather()`, returns `KpiSnapshot`. All methods catch `Exception` broadly and return zero `KpiValue` on failure.

### backend/api/metrics.py

`GET /api/metrics/kpis` FastAPI route:
- Module-level `_kpi_cache: Optional[KpiSnapshot]` shared across requests
- `AsyncIOScheduler` started on first request, runs `_refresh_kpis(stores)` every 60 seconds
- Cold cache: computes inline before returning
- Returns `JSONResponse(content=snapshot.model_dump(mode="json"))`
- Returns 503 only if compute fails after cold-start attempt

### backend/main.py

Deferred try/except mount added after `investigations_router`:
```python
try:
    from backend.api.metrics import router as metrics_router
    app.include_router(metrics_router, prefix="/api", dependencies=[Depends(verify_token)])
    log.info("metrics router mounted at /api/metrics")
except ImportError as exc:
    log.warning("metrics router not available: %s", exc)
```

### pyproject.toml

Added `"apscheduler>=3.10.0,<4.0"` dependency (resolved to 3.11.2).

## Test Results

- 27 new tests (22 service + 5 API)
- 582 total passing (up from 555 before Phase 13)
- 0 regressions

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED
