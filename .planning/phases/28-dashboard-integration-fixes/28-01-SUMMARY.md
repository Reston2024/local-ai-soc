---
phase: 28-dashboard-integration-fixes
plan: "01"
subsystem: ingestion-api
tags: [ingest, api, dashboard, progress-tracking, tdd]
dependency_graph:
  requires: []
  provides: [ingest-status-compat-route, filename-job-tracking]
  affects: [dashboard-ingest-view, backend-api-ingest]
tech_stack:
  added: []
  patterns: [tdd-red-green, job-status-compat-shim]
key_files:
  created: []
  modified:
    - ingestion/loader.py
    - backend/api/ingest.py
    - tests/unit/test_ingest_api.py
decisions:
  - "Map result.loaded -> events_processed and result.parsed -> events_total to match dashboard IngestJobStatus TypeScript interface"
  - "Add /status/{job_id} as new alias route rather than modifying /jobs/{job_id} to avoid breaking existing consumers"
  - "Store filename in _JOBS dict at job creation time (upload) rather than at completion time"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-04-07"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
requirements:
  - P28-T04
---

# Phase 28 Plan 01: Ingest Job Status Compat Route Summary

**One-liner:** Added `/ingest/status/{job_id}` alias route returning dashboard-compatible IngestJobStatus shape with events_processed/events_total/filename mapping.

## What Was Built

The dashboard's IngestView polls `/api/ingest/status/{jobId}` for ingest progress, but only `/api/ingest/jobs/{job_id}` existed. Additionally, the internal job dict used `result.loaded`/`result.parsed` while the dashboard TypeScript interface expects `events_processed`/`events_total`. This caused silent 404s and the progress bar always showed 0%.

**Changes:**
1. `ingestion/loader.py` — `_set_job()` now accepts `filename: str = ""` kwarg and stores it in the `_JOBS` dict entry
2. `backend/api/ingest.py` — `upload_file()` passes `filename=filename` to `_set_job()` at job creation time; new `GET /status/{job_id}` route added that maps internal keys to the dashboard-expected shape
3. `tests/unit/test_ingest_api.py` — New `TestJobStatusCompat` class with two tests (404 for unknown job, 200 with full shape after upload)

## Verification

- `uv run pytest tests/unit/test_ingest_api.py -q` — 18 passed (16 existing + 2 new)
- `uv run pytest tests/unit/ -q` — 869 passed, 1 skipped, no regressions

## Deviations from Plan

None — plan executed exactly as written.

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add TestJobStatusCompat tests (RED) | 3a139a9 | tests/unit/test_ingest_api.py |
| 2 | Add filename to _set_job + /ingest/status/{id} route (GREEN) | 2a8b98e | ingestion/loader.py, backend/api/ingest.py |

## Self-Check: PASSED

- ingestion/loader.py modified: FOUND
- backend/api/ingest.py modified: FOUND
- tests/unit/test_ingest_api.py modified: FOUND
- Commit 3a139a9: FOUND
- Commit 2a8b98e: FOUND
- All 18 ingest tests pass: CONFIRMED
- Full unit suite (869) passes: CONFIRMED
