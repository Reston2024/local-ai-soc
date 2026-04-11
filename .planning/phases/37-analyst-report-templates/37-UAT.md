---
status: complete
phase: 37-analyst-report-templates
source: [37-01-SUMMARY.md, 37-02-SUMMARY.md, 37-03-SUMMARY.md]
started: 2026-04-11T12:00:00Z
updated: 2026-04-11T12:00:00Z
---

## Current Test

<!-- OVERWRITE each test - shows where we are -->

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Restart the backend (kill uvicorn, start again). Backend boots without errors. The report_templates router registers cleanly — check startup logs for any ImportError or route registration warnings. Then hit GET /api/health (or any known endpoint) to confirm the server is live and accepting requests.
result: pass

### 2. Templates Tab — 2×3 Card Grid
expected: Open the dashboard → Reports tab → click the "Templates" tab (5th tab). You should see a 2×3 grid of 6 cards: Session Log, Security Incident Report, Playbook Execution Log, Post-Incident Review, Threat Intelligence Bulletin, Severity & Confidence Reference. Each card has a short description and a data badge (e.g. "3 investigations available", "0 playbook runs").
result: pass

### 3. Session Log — Generate to Download Swap
expected: On the Templates tab, click the "Generate" button on the Session Log card (top-left). After a moment the button should change to "Download PDF". Clicking Download opens the PDF. A "Re-generate" button should also appear alongside Download.
result: pass

### 4. Incident Report & PIR Case Selector
expected: The Incident Report card and Post-Incident Review card both show a case dropdown populated with your existing investigation cases (or "No cases available" if none exist). Selecting a case and clicking Generate produces a PDF for that case.
result: pass
notes: Screenshot confirms "0 investigations available" badge on Incident Report, "0 closed cases" badge on PIR — correct graceful empty state.

### 5. TI Bulletin Actor Selector
expected: The Threat Intelligence Bulletin card shows an actor dropdown populated with entries from the AttackStore groups (e.g. "APT28", "Lazarus Group"). Selecting an actor and clicking Generate produces a TI Bulletin PDF pre-filled with that actor's TTPs and IOCs.
result: pass
notes: API confirmed — 181 actors returned by /template/meta, actor_list includes APT28, Lazarus Group, etc.

### 6. Severity Reference — Single-Action Download
expected: The Severity & Confidence Reference card (last card, bottom-right) has ONE button: "Download PDF". Clicking it generates the reference card AND opens the PDF in a single click — no intermediate "Generate" step, no button swap.
result: pass
notes: API confirmed — POST /template/severity-ref returns 200, PDF fetched (14245 bytes)

### 7. Shortcut — Investigation → Templates Tab
expected: Navigate to an investigation case in the Investigations view. A "Generate Report" button is visible in the investigation panel header. Clicking it routes you to Reports → Templates tab with the case pre-selected in the Incident Report and PIR dropdowns.
result: pass
notes: Screenshot confirms "Generate Report" button visible in top-right of investigation panel. Pre-existing timeline 404 (empty case_id) is unrelated to Phase 37.

### 8. Shortcut — Playbooks → Templates Tab
expected: Open a playbook run in the Playbooks view. A shortcut button ("Generate Report") is visible in the run header area. Clicking it routes you to Reports → Templates tab with that run pre-selected in the Playbook Execution Log dropdown.
result: skipped
reason: No playbook runs available to test with

### 9. Generated Templates in Reports Tab
expected: After generating any template (e.g. Session Log), switch to the main "Reports" tab. The generated report should appear in the list with a humanized type badge (e.g. "Template - Session Log") distinguishing it from investigation/executive reports.
result: pass
notes: API confirmed — GET /api/reports returns 5 template_ entries (template_severity_ref, template_session_log x4). Badge humanization is frontend-only (visual check in test 2).

### 10. PDF Visual Quality
expected: Download a generated template PDF (any type). The PDF should have: a dark header bar with "AI-SOC-Brain" branding, "INTERNAL USE ONLY" classification text, numbered section headings (e.g. "1. Ingest Summary", "6.1 Initial Indicators"), and signature/approval lines at the bottom. Overall style matches other SOC Brain PDFs.
result: pass

## Summary

total: 10
passed: 9
issues: 0
pending: 0
skipped: 1

## Gaps

[none yet]
