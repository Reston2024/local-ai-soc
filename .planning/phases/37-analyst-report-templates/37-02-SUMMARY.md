---
phase: 37-analyst-report-templates
plan: "02"
subsystem: reports
tags: [reports, pdf, templates, pir, ti-bulletin, severity-ref, att&ck, ioc]
dependency_graph:
  requires:
    - backend/api/report_templates.py (Plan 37-01 — 3 builders + 3 endpoints already present)
    - backend/stores/sqlite_store.py (get_investigation_case, get_latest_triage, insert_report)
    - backend/api/reports.py (_render_pdf)
  provides:
    - POST /api/reports/template/pir/{case_id}
    - POST /api/reports/template/ti-bulletin
    - POST /api/reports/template/severity-ref
    - _pir_html, _ti_bulletin_html, _severity_ref_html (already implemented by Plan 37-01)
  affects:
    - backend/api/report_templates.py
tech_stack:
  added:
    - pydantic.BaseModel (_TiBulletinRequest for TI bulletin request body)
  patterns:
    - asyncio.to_thread for all SQLite reads (per project convention)
    - _fetch_ti_data() sync helper: actor fuzzy match + techniques JOIN + IOC LIKE query in one thread
    - Graceful degradation: all endpoints produce partial PDF on missing data, never raise HTTPException
key_files:
  created: []
  modified:
    - backend/api/report_templates.py
decisions:
  - "TI bulletin accepts actor_name via JSON body with empty default — blank bulletin when omitted"
  - "_TiBulletinRequest Pydantic model used as default body parameter for optional JSON"
  - "PIR fetches detection techniques via detection_techniques JOIN attack_techniques filtered by investigation_id subquery"
  - "Severity reference is pure static HTML — no parameters, no data queries"
  - "pydantic.BaseModel import added (omitted by Plan 37-01 since no POST bodies in that plan)"
metrics:
  duration_seconds: 441
  completed_date: "2026-04-11"
  tasks_completed: 2
  files_modified: 1
---

# Phase 37 Plan 02: PIR + TI Bulletin + Severity Reference POST Endpoints Summary

Three POST endpoints added to backend/api/report_templates.py completing all 6 analyst report template endpoints: PIR fetches case/detections/ATT&CK techniques/playbook_runs from SQLite, TI Bulletin uses fuzzy actor_tag matching for IOCs and group techniques via STIX join, and Severity Reference generates a fully static PDF reference card — all with graceful degradation.

## What Was Built

### Task 1: HTML Builder Functions

All 6 HTML builders (_pir_html, _ti_bulletin_html, _severity_ref_html) were found already implemented by Plan 37-01 (which ran in parallel before this plan). The test scaffold confirmed all 7 unit tests pass immediately.

### Task 2: POST Endpoints for PIR, TI Bulletin, and Severity Reference

Three new POST endpoints appended to backend/api/report_templates.py:

**POST /api/reports/template/pir/{case_id}**
- Fetches investigation case via `get_investigation_case(case_id)`
- Fetches detections filtered by `investigation_id`
- Fetches ATT&CK techniques via `detection_techniques JOIN attack_techniques` with detection_id subquery
- Fetches playbook_runs ordered by `started_at DESC`
- Fetches latest_triage; builds PDF; stores type='template_pir'

**POST /api/reports/template/ti-bulletin**
- Request body: `{"actor_name": "APT28"}` (optional — blank bulletin if omitted)
- `_fetch_ti_data()` sync helper: exact actor name match → fuzzy LIKE fallback → techniques via `attack_group_techniques JOIN attack_techniques WHERE stix_group_id = ?` → IOCs via `LOWER(actor_tag) LIKE LOWER(?)||'%' AND ioc_status = 'active'` → top-20 assets by risk_score
- Stores type='template_ti_bulletin'

**POST /api/reports/template/severity-ref**
- No request body, no data queries
- Pure static HTML via `_severity_ref_html()`
- Stores type='template_severity_ref' with date-stamped title

### pydantic.BaseModel Import Fix

Plan 37-01 omitted the `from pydantic import BaseModel` import (none of its endpoints needed request bodies). Added alongside the `_TiBulletinRequest` model for TI bulletin.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added missing pydantic.BaseModel import**
- **Found during:** Task 2 (adding _TiBulletinRequest)
- **Issue:** Plan 37-01 created the file without pydantic import; TI bulletin needed it for request body model
- **Fix:** Added `from pydantic import BaseModel` to imports block
- **Files modified:** backend/api/report_templates.py
- **Commit:** 3012295

**2. [Rule 3 - Blocking] Plan 37-01 ran in parallel and created all 6 builders already**
- **Found during:** Task 1 start
- **Issue:** Plan note warned 37-01 might not be complete; it was actually fully done when 37-02 started
- **Fix:** Skipped redundant builder re-implementation; proceeded directly to adding 3 POST endpoints
- **Impact:** None — faster execution, cleaner file

## Self-Check: PASSED

- backend/api/report_templates.py: FOUND
- tests/unit/test_report_templates.py: FOUND
- .planning/phases/37-analyst-report-templates/37-02-SUMMARY.md: FOUND
- commit 3012295: FOUND
- 7/7 test_report_templates.py tests pass
- 996 total unit tests pass
