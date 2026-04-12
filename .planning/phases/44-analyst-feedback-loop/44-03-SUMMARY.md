---
phase: 44
plan: 44-03
subsystem: metrics-layer, api-client
tags: [metrics, feedback, typescript, pydantic, kpi]
dependency_graph:
  requires: [44-02]
  provides: [KpiSnapshot-feedback-fields, api-feedback-interfaces]
  affects: [backend/services/metrics_service.py, backend/api/metrics.py, dashboard/src/lib/api.ts]
tech_stack:
  added: []
  patterns: [asyncio.to_thread for SQLite reads, optional app_state param for classifier access]
key_files:
  modified:
    - backend/services/metrics_service.py
    - backend/api/metrics.py
    - dashboard/src/lib/api.ts
decisions:
  - compute_all_kpis() gains optional app_state=None param so existing callers (daily snapshot scheduler, tests) need no changes
  - metrics.py scheduler switched from args= to kwargs= when passing app_state to _refresh_kpis
  - FeedbackClassifier stats read from app_state.feedback_classifier with full try/except guard
  - TypeScript FeedbackRequest/FeedbackResponse/SimilarCase interfaces placed after existing KpiSnapshot to keep Phase sections grouped
metrics:
  duration: "~10 minutes"
  completed: "2026-04-12"
  tasks_completed: 2
  files_modified: 3
---

# Phase 44 Plan 03: Wave 2 — KpiSnapshot extension + api.ts typed interfaces Summary

KpiSnapshot extended with 5 analyst feedback KPI fields (backend + frontend) and api.ts gains fully typed FeedbackRequest/FeedbackResponse/SimilarCase interfaces plus api.feedback.submit() and api.feedback.similar() methods.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 44-03-01 | Extend KpiSnapshot + compute_all_kpis() in metrics_service.py | af4e56e |
| 44-03-02 | Extend api.ts with feedback interfaces and api.feedback group | 9a18720 |

## What Was Built

### Task 1: metrics_service.py

Added 5 fields to `KpiSnapshot` Pydantic model (all with safe defaults, backward-compatible):
- `verdicts_given: int = 0`
- `tp_rate: float = 0.0`
- `fp_rate: float = 0.0`
- `classifier_accuracy: float | None = None`
- `training_samples: int = 0`

Extended `compute_all_kpis()` with `app_state=None` optional parameter:
- Calls `asyncio.to_thread(sqlite.get_feedback_stats)` for verdicts/rates — graceful try/except
- Reads `app_state.feedback_classifier.n_samples` and `.accuracy()` when app_state provided — graceful try/except

Updated `backend/api/metrics.py`:
- `_refresh_kpis()` gains `app_state=None` parameter, passes it to `compute_all_kpis()`
- APScheduler job switched from `args=[stores]` to `kwargs={"stores": stores, "app_state": app_state}`
- `get_kpis()` endpoint reads `app_state` from `request.app.state` and passes it down

### Task 2: api.ts

Extended `KpiSnapshot` interface with 5 optional feedback fields.

Added `verdict?: string | null` to `Detection` interface.

Added 4 new exported interfaces:
- `FeedbackRequest` — detection_id, verdict ('TP'|'FP'), optional rule_id/rule_name/severity
- `FeedbackResponse` — ok: boolean, verdict: string
- `SimilarCase` — detection_id, verdict, rule_name, similarity_pct, summary
- `SimilarCasesResponse` — cases: SimilarCase[]

Added `api.feedback` group:
- `submit(req: FeedbackRequest)` — POST /api/feedback
- `similar(detection_id, rule_id?, rule_name?)` — GET /api/feedback/similar with URLSearchParams

## Verification

- 1081 unit tests GREEN, 0 failures, 0 regressions
- TypeScript compiles with 0 errors (`npx tsc --noEmit`)
- `grep "verdicts_given" backend/services/metrics_service.py` shows field + computation
- `grep "api.feedback" dashboard/src/lib/api.ts` shows submit + similar methods

## Deviations from Plan

**1. [Rule 2 - Missing critical functionality] metrics.py updated alongside metrics_service.py**
- Found during: Task 1
- Issue: metrics.py `_refresh_kpis()` called `compute_all_kpis()` without passing `app_state`, so classifier accuracy would never be populated
- Fix: Updated `_refresh_kpis()` to accept `app_state`, updated APScheduler registration to use `kwargs=`, `get_kpis()` endpoint reads `request.app.state`
- Files modified: backend/api/metrics.py
- Commit: af4e56e

## Self-Check: PASSED

- `backend/services/metrics_service.py` — modified, committed in af4e56e
- `backend/api/metrics.py` — modified, committed in af4e56e
- `dashboard/src/lib/api.ts` — modified, committed in 9a18720
- Both commits present in git log
