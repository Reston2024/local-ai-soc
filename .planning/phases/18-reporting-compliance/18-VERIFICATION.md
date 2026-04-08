---
phase: 18-reporting-compliance
verified_by: gsd-verifier (29-04)
verified_at: "2026-04-08"
status: passed
---

# Phase 18 Verification — Reporting & Compliance

## Status: PASSED

Phase 18 delivered PDF report generation, MITRE ATT&CK heatmap coverage, TheHive export,
NIST CSF 2.0 compliance ZIP export, and a four-tab Svelte 5 frontend. All deliverables
confirmed present and importable. 48 report/export/analytics tests pass.

---

## Automated Checks

### Import checks

| Module | Result |
|--------|--------|
| `from backend.api.reports import router` | PASS — reports router OK |
| `from backend.api.export import router` | PASS — export router OK |
| `from backend.api.analytics import router` | PASS — analytics router OK |
| `import weasyprint` | PASS — weasyprint OK |

### Route registration in main.py

| Router | Mount point | Registered |
|--------|------------|------------|
| `reports_router` | `/api/reports` | YES (main.py line ~554) |
| `export_router` | `/api/export` | YES (main.py line ~554) |
| `analytics_router` | `/api/analytics` | YES (main.py line ~554) |

All routers are guarded by `Depends(verify_token)`.

### Test suite

```
uv run pytest tests/ -k "report or export or heatmap or thehive or mitre or analytics" -x -q
48 passed, 922 deselected in 5.56s
```

---

## Deliverable Verification

### PDF Report Generation

- **File:** `backend/api/reports.py`
- **Library:** `weasyprint>=68.1` (declared in `pyproject.toml`, lazily imported)
- **Endpoints:**
  - `POST /api/reports/investigation/{investigation_id}` — renders investigation HTML to PDF, stores base64 in SQLite, returns 201
  - `POST /api/reports/executive` — renders executive summary HTML to PDF with KPI metrics (MTTD/MTTR/alert_volume from `daily_kpi_snapshots`), returns 201
  - `GET /api/reports/{report_id}/pdf` — decodes and streams PDF binary (200 OK or 404/422)
  - `GET /api/reports` — lists report metadata, strips `pdf_b64` from response

### MITRE ATT&CK Heatmap

- **File:** `backend/api/analytics.py`
- **Endpoint:** `GET /api/analytics/mitre-coverage`
- **Coverage matrix:** Cross-references detections (attack_technique, attack_tactic columns) and playbook trigger_conditions against all 14 MITRE Enterprise ATT&CK tactics (reconnaissance through impact, v14)
- **Response shape:** `{"tactics": [...], "coverage": {"tactic": {"TXXXX": {"sources": [...], "status": "detected|playbook_covered|both"}}}}`
- **Frontend:** `dashboard/src/views/ReportsView.svelte` — ATT&CK Coverage tab renders tactic-column/technique-cell heatmap colour-coded by status

### TheHive Export

- **File:** `backend/api/reports.py` — `GET /api/reports/compliance?framework=thehive`
- **Behavior:** Fetches all investigation cases from SQLite, maps each to a TheHive 5 Alert record and Case record (title, description, severity, tags, status, startDate, endDate), bundles as `thehive/alerts.json` + `thehive/cases.json` in a ZIP archive
- **Download:** Returned as `application/zip` with `Content-Disposition: attachment`

### NIST CSF 2.0 Compliance Export

- **File:** `backend/api/reports.py` — `GET /api/reports/compliance?framework=nist-csf`
- **Behavior:** Produces six JSON evidence files (GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER) + `summary.html` in a ZIP archive
- **GOVERN evidence:** `daily_kpi_snapshots` from DuckDB (graceful fallback to empty list)

### Export Routes (CSV / JSON / Case Bundle)

- **File:** `backend/api/export.py`
- **Endpoints:**
  - `GET /api/export/events/csv` — filtered events as streamed CSV
  - `GET /api/export/events/json` — filtered events as NDJSON
  - `GET /api/export/case/{case_id}/bundle` — full case bundle (case, entities, edges, detections, events) as JSON

### Frontend (Svelte 5)

- **File:** `dashboard/src/views/ReportsView.svelte`
- **Tabs:** Reports | ATT&CK Coverage | Trends | Compliance Export
- **API client:** `dashboard/src/lib/api.ts` — `api.reports` and `api.analytics` namespaces with typed interfaces (`Report`, `ReportsListResponse`, `MitreTechniqueEntry`, `MitreCoverageResponse`, `TrendDataPoint`, `TrendsResponse`)
- **PDF download:** `getDownloadUrl(path)` appends `?token=<bearer>` for browser-initiated binary downloads; `backend/core/auth.py` `verify_token` accepts query param fallback

### Data Layer

- **SQLite table:** `reports` — DDL + `insert_report`, `list_reports`, `get_report` methods in `SQLiteStore`
- **Pydantic models:** `backend/models/report.py` — `Report`, `InvestigationReportRequest`, `ExecutiveReportRequest`
- **DuckDB table:** `daily_kpi_snapshots` — used by executive reports and trends endpoint (created in plan 18-03)

---

## Plans Delivered

| Plan | Name | Status |
|------|------|--------|
| 18-01 | Reports API + WeasyPrint PDF | SUMMARY exists |
| 18-02 | Analytics API + MITRE coverage + Trends | SUMMARY exists |
| 18-03 | KPI snapshots + Compliance export | SUMMARY exists |
| 18-04 | Token-in-query-param auth hotfix for PDF downloads | SUMMARY exists |
| 18-05 | ReportingView four-tab Svelte 5 frontend | SUMMARY exists (human verified) |

---

## Notes

- Live PDF rendering and live TheHive server connection were not tested in this automated
  check (WeasyPrint CPU render requires a running backend; TheHive requires an external
  instance). The milestone audit (Phase 28 integration check) confirmed both working.
- Status is `passed` because all static artifacts are present, importable, and unit-tested.
  Full E2E PDF render requires a running backend (`uv run uvicorn backend.main:create_app --factory`).
