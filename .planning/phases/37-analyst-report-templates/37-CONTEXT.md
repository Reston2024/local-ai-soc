# Phase 37: Analyst Report Templates - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Add six pre-populated analyst report templates to the Reports section of the SOC Brain dashboard. Each template pre-fills from live SOC Brain data and downloads as PDF. Templates live in a new "Templates" tab (5th tab) within the existing ReportsView. No new backend infrastructure — same WeasyPrint, same SQLite reports table, same API pattern as existing reports.

Templates:
1. Session Log — daily operational record
2. Security Incident Report (INC-YYYY-####) — formal IR record
3. Playbook Execution Log — per-run audit trail
4. Post-Incident Review (PIR) — retrospective
5. Threat Intelligence Bulletin (TI-YYYY-####) — TTP/IOC bulletin
6. Severity & Confidence Reference — static reference card

</domain>

<decisions>
## Implementation Decisions

### Pre-fill Depth
- Fill **everything computable** — not just structured/tabular fields, but also narrative-adjacent fields where data exists
- Triage result text pasted verbatim from latest `triage_results` record (model output, severity_summary)
- Investigation summary text from Ollama/investigation records where available
- Playbook step outputs pulled from `playbook_runs` table rows verbatim
- Analyst-narrative fields (root cause, override rationale, analytical findings) left blank with placeholder text — analyst writes these
- LLM Inference Audit Trail rows (required in 4 of 6 templates) pre-filled from `triage_results` table: model name, prompt version (from content_json), severity_summary, result_text; Confidence and Disposition columns left blank for analyst
- Session Log timespan: rolling 24h from now (consistent with Overview/telemetry summary)
- Severity & Confidence Reference: Known Open Gaps section hardcoded in HTML template (the 4 gaps are fixed; analyst updates reference version field)

### Case Selectors
- Templates tied to a case (Incident Report, PIR): both dropdown in Templates tab AND shortcut "Generate Report" button on each investigation record in InvestigationsView
- Playbook Log: both dropdown in Templates tab AND shortcut button on each playbook run record
- TI Bulletin: actor dropdown sourced from AttackStore group data; template pre-fills with that actor's TTPs, matched techniques, and TIP IOCs matching the actor_tag
- Session Log: no selector — one-click, always generates for rolling 24h
- No records exist for a template → generate blank template with placeholder text in all data-dependent sections (never block/disable)

### Templates Tab Layout
- 2×3 card grid (6 cards) — not list or sub-tabs
- Each card: template name, short description, inline selector (case dropdown / actor dropdown) where needed, Generate button
- Subtle data badge on each card: e.g. "3 investigations available", "0 playbook runs" — analyst sees data availability at a glance
- Severity & Confidence Reference: 6th card (same grid, last position), no selector, single "Download PDF" button
- After successful generation: card swaps Generate button for Download button (most recent generated); also appears in main Reports list
- Re-generate button available alongside Download to refresh with latest data

### Output & Persistence
- Generated templates stored in SQLite `reports` table with `type="template_session_log"`, `type="template_incident"`, etc.
- Appear in the main Reports tab list alongside executive/investigation reports — type badges distinguish them
- Generate → download immediately (no in-browser editing); analyst fills narrative fields in Word/Acrobat post-download
- Preserve formal signature/approval lines from the original docx templates (signature, date, closure lines)
- PDF header: match existing SOC Brain style (dark header, AI-SOC-Brain branding, same CSS variables as reports.py) — consistent with all other generated reports

### Claude's Discretion
- Exact CSS layout of template cards (spacing, badge position, selector placement)
- HTML structure of each template section (heading hierarchy, table styles)
- How to handle playbook_runs table absence (if no table exists, graceful fallback to blank)
- Column order and exact field names in pre-filled tables

</decisions>

<specifics>
## Specific Ideas

- The docx source templates use formal section numbering (1. Ingest Summary, 6.1 Initial Indicators, etc.) — preserve this numbering in the PDF output
- LLM Inference Audit Trail is marked "REQUIRED" in the docx and described as a Rule 5.3 governance record — treat it as a first-class section, not optional
- The TI Bulletin includes a pySigma YAML block (Section 7.1) and compiled DuckDB SQL block (Section 7.2) — these are analyst-filled; pre-fill only the ATT&CK TTP table and IOC rows
- "INTERNAL USE ONLY" and classification labels from the docx headers should appear in the PDF (as text, not watermarks)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/api/reports.py`: `_render_pdf()`, `_strip_pdf_b64()`, `_investigation_html()`, `_executive_html()` — direct patterns for all 6 template HTML builders
- `backend/stores/sqlite_store.py`: `insert_report()`, `list_reports()`, `get_report()` — reports table CRUD; templates use same table with new type values
- `backend/models/report.py`: `ExecutiveReportRequest`, `InvestigationReportRequest` — extend with new request models for each template
- `dashboard/src/views/ReportsView.svelte`: 4-tab pattern, `activeTab` state, `$effect` lazy load per tab — Templates is tab 5 using same pattern
- `dashboard/src/lib/api.ts`: `api.reports.*` group — extend with `api.reports.generateTemplate(type, params)` and `api.reports.templateMeta()` (for badge counts)

### Established Patterns
- WeasyPrint HTML→PDF: always called inside `asyncio.to_thread()` (CPU-bound)
- SQLite reports table: `id TEXT PK`, `type TEXT`, `title TEXT`, `subject_id TEXT`, `content_json TEXT` (JSON blob with `pdf_b64`), `created_at TEXT`
- API auth: all report generation endpoints use `verify_token` dependency
- Svelte 5 runes: `$state()` for all reactive state, `$effect()` for side effects — no stores

### Integration Points
- **Session Log**: DuckDB `normalized_events` (24h count + event_type breakdown + source_types) + SQLite `detections` (24h count) + `triage_results` (latest result) + `git rev-parse HEAD` (git hash)
- **Incident Report**: SQLite `investigation_cases` + `detections` + `ioc_store` (by actor_tag or case iocs) + `triage_results` + `attack_store` (techniques for matched detections)
- **Playbook Log**: SQLite `playbook_runs` (steps JSON, gate_results JSON) + `triage_results` (LLM calls during run)
- **PIR**: SQLite `investigation_cases` (closed cases) + `detections` + `attack_store` (detection_techniques) + `playbook_runs`
- **TI Bulletin**: `attack_store` (group + group_techniques) + `ioc_store` (filtered by actor_tag) + `asset_store` (exposure assessment)
- **Severity Reference**: No data queries — pure static HTML with hardcoded gap list
- **InvestigationsView shortcut buttons**: need "Generate Report" button → routes to ReportsView with pre-selected case

</code_context>

<deferred>
## Deferred Ideas

- In-browser template editing before PDF download — future phase
- Scheduled/automated template generation (e.g., auto-generate Session Log at end of day) — future phase
- Email/export of generated templates — future phase

</deferred>

---

*Phase: 37-analyst-report-templates*
*Context gathered: 2026-04-11*
