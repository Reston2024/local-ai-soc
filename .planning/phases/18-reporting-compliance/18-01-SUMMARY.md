---
phase: 18-reporting-compliance
plan: "01"
subsystem: api
tags: [weasyprint, pdf, reports, sqlite, fastapi, pydantic]

# Dependency graph
requires:
  - phase: 17-playbooks-soar
    provides: SQLiteStore CRUD pattern, playbook_runs table, router pattern
  - phase: 14-ai-copilot
    provides: chat_messages table, get_chat_history method

provides:
  - reports SQLite table with DDL and 3 CRUD methods (insert_report, list_reports, get_report)
  - POST /api/reports/investigation/{id} — investigation report generation + PDF
  - POST /api/reports/executive — executive summary report generation + PDF
  - GET /api/reports — list reports (metadata only, no pdf_b64)
  - GET /api/reports/{id}/pdf — download PDF binary
  - Pydantic models: Report, InvestigationReportRequest, ExecutiveReportRequest

affects:
  - 18-reporting-compliance (remaining plans build on this reports table and router)
  - dashboard (future UI for listing/downloading reports)

# Tech tracking
tech-stack:
  added:
    - weasyprint==68.1 (HTML-to-PDF rendering, CPU-bound, lazy-imported)
    - brotli, cffi, cssselect2, fonttools, pillow, pydyf, pyphen, tinycss2, tinyhtml5, webencodings, zopfli (WeasyPrint dependencies)
  patterns:
    - "Lazy WeasyPrint import inside _render_pdf() to avoid startup DLL load cost"
    - "Separate asyncio.to_thread calls for DB fetch vs PDF render (different blocking characteristics)"
    - "pdf_b64 stored inside content_json blob; stripped from list endpoint responses"
    - "Graceful DuckDB KPI fallback — try/except around daily_kpi_snapshots query (table created in plan 03)"

key-files:
  created:
    - backend/models/report.py
    - backend/api/reports.py
    - tests/unit/test_report_store.py
  modified:
    - backend/stores/sqlite_store.py (reports DDL + 3 CRUD methods)
    - backend/main.py (reports_router registration)
    - pyproject.toml (weasyprint dependency)
    - uv.lock

key-decisions:
  - "WeasyPrint lazy-imported inside _render_pdf() — avoids GTK/Pango DLL load at server startup, only fails when first PDF is generated"
  - "pdf_b64 stored inside content_json TEXT blob rather than a separate column — keeps schema simple, strip on list endpoint"
  - "playbook_runs for investigation fetched via raw SQL on sqlite._conn (no dedicated method exists), following existing pattern"
  - "Graceful fallback for daily_kpi_snapshots DuckDB table (plan 18-03) — zeros used when table absent"
  - "reports_router registered via deferred try/except import pattern matching all other routers in main.py"

patterns-established:
  - "PDF generation pattern: fetch data -> build HTML f-string -> asyncio.to_thread(_render_pdf) -> base64 encode -> store in content_json"
  - "Report list strips large blobs (pdf_b64) — metadata-only list, full download via /pdf endpoint"

requirements-completed: [P18-T01]

# Metrics
duration: 17min
completed: 2026-03-31
---

# Phase 18 Plan 01: Report Generation API Summary

**SQLite reports table, WeasyPrint PDF generation, and 4 REST endpoints for investigation and executive reports stored as base64 PDFs in content_json**

## Performance

- **Duration:** 17 min
- **Started:** 2026-03-31T18:29:33Z
- **Completed:** 2026-03-31T18:47:28Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Reports table DDL added to SQLiteStore with 3 CRUD methods (insert_report, list_reports, get_report)
- WeasyPrint 68.1 installed and integrated with lazy import pattern to avoid startup cost
- 4 REST endpoints covering investigation report generation, executive summary, list, and PDF download
- Investigation reports fetch case + detections + optional chat history + playbook runs from SQLite
- Executive reports count events in period from SQLite and KPI metrics from DuckDB (with graceful fallback)
- PDF bytes base64-encoded and stored in content_json; stripped from list responses; served via /pdf endpoint
- 3 unit tests pass for SQLiteStore CRUD methods

## Task Commits

Each task was committed atomically:

1. **Task 1: Reports DDL + CRUD + Pydantic models** - `5d5f317` (feat)
2. **Task 2: Reports router (investigation + executive + list + pdf)** - `2d4648e` (feat)

**Plan metadata:** `(to be added)` (docs: complete plan)

## Files Created/Modified

- `backend/models/report.py` — Pydantic models: Report, InvestigationReportRequest, ExecutiveReportRequest
- `backend/api/reports.py` — FastAPI router with 4 endpoints + HTML template helpers + PDF render helper
- `tests/unit/test_report_store.py` — 3 unit tests for SQLiteStore report CRUD
- `backend/stores/sqlite_store.py` — reports DDL (CREATE TABLE + 2 indexes) + 3 CRUD methods
- `backend/main.py` — reports_router deferred import registration
- `pyproject.toml` — weasyprint added to dependencies
- `uv.lock` — updated with weasyprint and all 14 of its transitive dependencies

## Decisions Made

- Used lazy import for WeasyPrint (`import weasyprint` inside `_render_pdf()`) — avoids loading GTK/Pango DLLs at server startup; only needed when a report is generated
- Stored pdf_b64 inside `content_json` TEXT blob rather than a separate column to keep schema minimal
- Executive report KPI fetch uses try/except around `daily_kpi_snapshots` DuckDB query — table is created in plan 18-03, zeros used when absent
- Playbook runs for an investigation fetched via raw SQL on `sqlite._conn` since no dedicated method existed; follows the same `_conn` connection pattern already used throughout SQLiteStore
- Router registered with deferred try/except pattern (matching all other routers in main.py)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLiteStore uses persistent self._conn, not _conn() context manager**
- **Found during:** Task 1 (reading existing code before writing)
- **Issue:** Plan interfaces section showed `with self._conn() as conn:` pattern, but SQLiteStore actually uses `self._conn` as a persistent connection object (not a factory method)
- **Fix:** Used `self._conn.execute(...)` and `self._conn.commit()` directly in all three new methods, matching the pattern of every other method in SQLiteStore
- **Files modified:** backend/stores/sqlite_store.py
- **Verification:** 3 unit tests pass
- **Committed in:** 5d5f317 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — wrong pattern from plan interfaces)
**Impact on plan:** Auto-fix was essential for correctness. No scope creep.

## Issues Encountered

**WeasyPrint requires GTK3 runtime on Windows — `import weasyprint` fails without system DLLs**

WeasyPrint depends on libgobject, libpango, libharfbuzz, libfontconfig, libpangoft2 (GTK3/Pango native libraries). These are not present on this Windows system. The package was installed successfully (`uv add weasyprint` succeeded). The lazy import pattern means the server starts and runs normally — WeasyPrint only loads its DLLs when `_render_pdf()` is called (i.e., when a report POST is made).

To enable PDF generation at runtime, install GTK3 for Windows:
- Download from: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
- Run: `gtk3-runtime-*-win64.exe /S` (requires admin, NSIS installer)
- Or via winget: `winget install tschoonj.GTKForWindows` (requires interactive session for UAC)

After GTK3 is installed, `import weasyprint` will succeed and PDF generation will work.

The plan's stated success criterion "WeasyPrint installed (uv add weasyprint succeeds)" is met. The system-level GTK dependency is documented here for operator action.

## User Setup Required

**WeasyPrint PDF rendering requires GTK3 runtime DLLs on Windows.**

To enable the `/api/reports/*/pdf` endpoints to actually render PDFs, install GTK3:

```
winget install tschoonj.GTKForWindows
```
Or download from: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases/latest

Verify with: `python -c "import weasyprint; print('ok')"`

## Next Phase Readiness

- Reports table and 4 endpoints are ready; the API skeleton is complete
- PDF generation will work once GTK3 runtime is installed (admin action)
- Plan 18-02 can build the Svelte report dashboard UI using GET /api/reports and GET /api/reports/{id}/pdf
- Plan 18-03 creates the daily_kpi_snapshots table; executive reports will then include real KPI data (currently falls back to zeros)

---
*Phase: 18-reporting-compliance*
*Completed: 2026-03-31*
