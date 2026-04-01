# Plan 18-05 Summary — ReportingView Four-Tab Frontend

**Status:** Complete
**Human checkpoint:** Approved by analyst

## What Was Built

Replaced the stub `ReportsView.svelte` with a fully functional four-tab reporting hub and extended `api.ts` with typed report/analytics methods.

### dashboard/src/lib/api.ts
- New exported interfaces: `Report`, `ReportsListResponse`, `MitreTechniqueEntry`, `MitreCoverageResponse`, `TrendDataPoint`, `TrendsResponse`
- New exported helper: `getDownloadUrl(path)` — appends `?token=<bearer>` for binary endpoints that the browser opens directly (PDF, ZIP)
- `api.reports` namespace: `list`, `generateInvestigation`, `generateExecutive`, `pdfUrl`, `complianceDownloadUrl`
- `api.analytics` namespace: `mitreCoverage`, `trends`

### dashboard/src/views/ReportsView.svelte
Four tabs, all connected to live backend APIs, Svelte 5 runes only:

| Tab | API | Feature |
|-----|-----|---------|
| Reports | `GET /api/reports`, `POST /api/reports/executive` | List reports, generate executive report, open PDF in new tab |
| ATT&CK Coverage | `GET /api/analytics/mitre-coverage` | Tactic-column/technique-cell heatmap colour-coded by status |
| Trends | `GET /api/analytics/trends` | D3.js SVG line chart (MTTD/MTTR/alert_volume); "no data" fallback |
| Compliance Export | `GET /api/reports/compliance` | Framework selector + ZIP download via `getDownloadUrl` |

### backend/core/auth.py (hotfix during verification)
Added `?token=` query param fallback to `verify_token` so browser-initiated binary downloads (PDF, ZIP) work without requiring custom headers.

## Bugs Fixed During Verification
1. **CORS port mismatch** — frontend dev server on 5174, backend only allowed 5173 (fixed in prior session)
2. **DuckDB column name** — executive report query used `alert_count`, column is `alert_volume` (fixed in prior session)
3. **PDF 401 Unauthorized** — `getDownloadUrl` appended `?token=` but `verify_token` only read `Authorization` header; added query param fallback

## Test Results
- 21 Phase 18 unit tests: all pass
- Full suite: 590 pass (81 pre-existing failures unrelated to Phase 18, confirmed by git stash check)
