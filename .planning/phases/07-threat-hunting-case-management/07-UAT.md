---
status: resolved
phase: 07-threat-hunting-case-management
source: [07-01-SUMMARY.md, 07-02-SUMMARY.md, 07-03-SUMMARY.md, 07-04-SUMMARY.md, 07-05-SUMMARY.md]
started: 2026-03-17T20:00:00Z
updated: 2026-03-17T21:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running backend. Clear ephemeral state. Start the application from scratch with `.\scripts\start.ps1`. Server boots without errors and GET http://localhost:8000/health returns {"status":"ok"} (or similar live data).
result: issue
reported: "The script 'start.ps1' cannot be run because it contained a \"#requires\" statement for Windows PowerShell 7.0. The version of Windows PowerShell that is required by the script does not match the currently running version of Windows PowerShell 5.1."
severity: major

### 2. Create an Investigation Case via the API
expected: POST http://localhost:8000/api/cases with body `{"title":"Test Case","description":"UAT test"}` returns 200 with a `case_id` field, `case_status` of "open", and a `created_at` timestamp.
result: pass

### 3. List Investigation Cases
expected: GET http://localhost:8000/api/cases returns 200 with a JSON array. After creating a case in Test 2, the list contains at least one entry with `case_id`, `title`, and `case_status`.
result: pass

### 4. Get Case Detail
expected: GET http://localhost:8000/api/cases/{case_id} (using the id from Test 2) returns 200 with the full case object including `title`, `case_status`, `related_alerts`, `tags`, and `artifacts` fields.
result: issue
reported: "{\"detail\":\"Not found\",\"path\":\"/api/cases/{...full JSON from Test 3...}\"} — case created in Test 2 did not appear in Test 3 list (list was empty), so no case_id was available; GET 404 because wrong value was used as case_id. Root issue: case is not persisting or POST/GET use different stores."
severity: major

### 5. Update Case Status
expected: PATCH http://localhost:8000/api/cases/{case_id} with body `{"case_status":"investigating"}` returns 200. A subsequent GET to the same case shows `case_status` is now "investigating".
result: pass

### 6. List Threat Hunt Templates
expected: GET http://localhost:8000/api/hunt/templates returns 200 with a list of exactly 4 templates. Each template has a `name`, `description`, and `param_keys`. Templates include entries for suspicious IP communications, PowerShell children processes, unusual authentication, and IOC search.
result: pass

### 7. Execute a Threat Hunt Query
expected: POST http://localhost:8000/api/hunt with body `{"template_id":"suspicious_ip_comms","params":{"target_ip":"1.2.3.4"}}` returns 200 with a `results` array and `result_count` field. Results may be empty if no matching events exist — an empty array is a valid response.
result: issue
reported: "422 validation error: field 'template_id' not accepted — endpoint requires field named 'template', not 'template_id'. Request contract mismatch between implementation and documented API."
severity: major

### 8. View Case Timeline
expected: GET http://localhost:8000/api/cases/{case_id}/timeline returns 200 with a `timeline` array. Each entry (if any) has `timestamp`, `event_source`, `entity_references`, `related_alerts`, and `confidence_score`. An empty array is valid if no correlated events exist for the case.
result: skipped
reason: Blocked by case persistence bug (Test 4) — no valid case_id available to test against.

### 9. Upload a Forensic Artifact
expected: POST http://localhost:8000/api/cases/{case_id}/artifacts as multipart/form-data with a file field (any small file — e.g., a .txt) returns 200 with an `artifact_id` and `file_path`. A subsequent GET /api/cases/{case_id} shows the artifact referenced in the case.
result: skipped
reason: Blocked by case persistence bug (Test 4) — no valid case_id available to test against.

### 10. CasePanel dashboard component renders
expected: In the frontend/ directory, run `npm run dev` and open the dev server in a browser. Navigate to the Investigation or Cases tab/panel. A case list renders (empty or populated), a "New Case" input or create button is visible, and no JavaScript errors appear in the console.
result: issue
reported: "Dashboard loads and shows alerts, evidence panel, and event timeline. No Case list visible. No New Case input or create button. No Investigation/Cases panel or route visible. CasePanel component is not rendered or not accessible via the UI."
severity: major

### 11. HuntPanel dashboard component renders
expected: In the frontend/ dashboard, navigate to the Hunt or Threat Hunting tab/panel. A template dropdown is visible with at least one option, dynamic parameter inputs appear when a template is selected, and a Run/Execute button is present.
result: skipped
reason: Blocked by Test 10 — panels not wired into app navigation; no Hunt tab visible either.

### 12. Pivot hunt result to case
expected: In the HuntPanel, select the suspicious_ip_comms template, enter a test IP, execute the hunt, and click "Open as Case" (or equivalent pivot button). A new case is created and either the CasePanel updates or a confirmation is shown.
result: skipped
reason: Blocked by Tests 10 and 11 — panels not wired into app navigation.

## Summary

total: 12
passed: 4
issues: 4
pending: 0
skipped: 4

## Gaps

- truth: "CasePanel and HuntPanel are accessible via the dashboard UI navigation"
  status: resolved
  reason: "User reported: dashboard shows alerts/evidence/event-timeline panels only; no Investigation, Cases, or Hunt tab/panel visible. CasePanel.svelte and HuntPanel.svelte were created but not wired into the app's navigation or tab system."
  severity: major
  test: 10
  root_cause: "App.svelte only imports ThreatGraph, EventTimeline, EvidencePanel (lines 3-5). CasePanel and HuntPanel are never imported or rendered anywhere in the codebase. No tab/nav system exists in App.svelte — it is a fixed three-panel layout with no mechanism to switch views. InvestigationPanel.svelte and AttackChain.svelte (Phase 6) have the identical problem."
  fix: "Plan 07-06 — rewrote App.svelte with 5-tab nav (Alerts/Cases/Hunt/Investigation/Attack Chain) using $state('alerts'). Added $lib alias to vite.config.ts. All 4 panels now imported and conditionally rendered. npm run build exits 0. Commits: 097eaec, 6fc9527."
  artifacts:
    - path: "frontend/src/App.svelte"
      issue: "Missing imports and tab navigation for CasePanel, HuntPanel, InvestigationPanel, AttackChain"
    - path: "frontend/src/components/panels/CasePanel.svelte"
      issue: "Exists but unreachable — zero references outside own file"
    - path: "frontend/src/components/panels/HuntPanel.svelte"
      issue: "Exists but unreachable — zero references outside own file"
  missing:
    - "Add tab/nav system to App.svelte with tabs for Cases, Hunt, Investigation, Attack Chain"
    - "Import and render CasePanel and HuntPanel in App.svelte"
  debug_session: ""

- truth: "POST /api/hunt accepts {\"template_id\": \"...\", \"params\": {...}} as documented"
  status: resolved
  reason: "User reported: 422 validation error — endpoint requires field named 'template', not 'template_id'. Request contract mismatch between implementation and CONTEXT.md spec."
  severity: major
  test: 7
  root_cause: "HuntRequest Pydantic model at investigation_routes.py:75-77 uses field name 'template', not 'template_id'. The implementation plan (07-04-PLAN.md:177) specified 'template' but CONTEXT.md and UAT expected 'template_id'. Frontend api.ts:369 sends { template, params } (matches backend, so frontend is unaffected). Fix scope: rename field in HuntRequest model + update 2 usages of body.template in route + update api.ts."
  fix: "Plan 07-07 — renamed HuntRequest.template → template_id in investigation_routes.py (4 locations: class def + 3 usages). Updated api.ts executeHunt to send { template_id: template, params }. Added integration test test_hunt_accepts_template_id confirming 200 + result_count. Commits: 130efd0, 700c23f, 01aa88e."
  artifacts:
    - path: "backend/investigation/investigation_routes.py"
      issue: "HuntRequest.template should be HuntRequest.template_id (lines 76, 258, 264)"
    - path: "frontend/src/lib/api.ts"
      issue: "executeHunt sends { template, params } — must send { template_id, params } after rename (line 369)"
  missing:
    - "Rename HuntRequest.template → HuntRequest.template_id in investigation_routes.py"
    - "Update api.ts executeHunt to send template_id"
  debug_session: ""

- truth: "Cases created via POST /api/cases are immediately visible in GET /api/cases list"
  status: resolved
  reason: "User reported: POST returned success in Test 2 but GET /api/cases returned empty list in Test 3; no case_id available for subsequent tests."
  severity: major
  test: 4
  root_cause: "Architecture is correct — both POST and GET use the same SQLiteStore instance via _get_stores(request). Store isolation hypothesis FALSIFIED by static analysis. Most likely cause: investigation_router is silently not mounted in the production backend/main.py (deferred try/except ImportError swallows errors), OR the production DB file (data/graph.db) was created before Phase 7 DDL ran and the tables were not created on the running instance. Needs a round-trip integration smoke test to confirm."
  fix: "Plan 07-07 — added integration test test_create_and_list_cases that performs POST /api/cases then GET /api/cases round-trip in a single test, confirming persistence works correctly. Architecture confirmed sound. User likely hit a stale DB or startup race during original UAT. Commit: 700c23f."
  artifacts:
    - path: "backend/main.py"
      issue: "Deferred import guard for investigation_router may be silently swallowing an ImportError, preventing route registration"
    - path: "backend/stores/sqlite_store.py"
      issue: "Verify _DDL runs CREATE TABLE IF NOT EXISTS investigation_cases on existing DB files"
  missing:
    - "Add startup log confirming investigation_router mounted successfully"
    - "Verify round-trip: POST /api/cases then GET /api/cases in a single test with real backend/main.py app"
  debug_session: ""

- truth: "start.ps1 starts the backend successfully when invoked from a terminal"
  status: resolved
  reason: "User reported: script cannot be run — #Requires -Version 7.0 not satisfied when invoking with `powershell` (PS 5.1). Must use `pwsh` (PS 7)."
  severity: major
  test: 1
  root_cause: "All 4 user-facing scripts (start.ps1, stop.ps1, status.ps1, smoke-test-phase1.ps1) have #Requires -Version 7.0 at line 1. PS 5.1 evaluates this at parse time and aborts before any code runs. REPRODUCIBILITY_RECEIPT.md Step 8 shows 'scripts\\start.ps1' with no mention of pwsh. docs/reproducibility.md line 16 lists PowerShell 7+ as a prerequisite but buries it. README.md has no mention of PS7 at all."
  fix: "Plan 07-08 — created scripts/start.cmd, stop.cmd, status.cmd wrappers that check for pwsh.exe with `where` and print clear error + winget install command if missing, then exec `pwsh -NoLogo -File scripts\\start.ps1`. Updated REPRODUCIBILITY_RECEIPT.md Step 8 to show .cmd wrapper as primary invocation. Rewrote README.md with bold PS7 prerequisite row and winget install command. Commits: c8839d2, 38cbce4, 5c3e32c."
  artifacts:
    - path: "scripts/start.ps1"
      issue: "#Requires -Version 7.0 blocks PS 5.1 with no helpful error or redirect"
    - path: "REPRODUCIBILITY_RECEIPT.md"
      issue: "Step 8 shows scripts\\start.ps1 with no pwsh instruction"
    - path: "docs/reproducibility.md"
      issue: "PS7+ prerequisite buried in bullet list, no install command"
  missing:
    - "Add scripts/*.cmd wrappers that check for pwsh and re-invoke, or replace #Requires with runtime version check + clear error"
    - "Update REPRODUCIBILITY_RECEIPT.md Step 8 to show: pwsh -File scripts\\start.ps1"
    - "Update README.md Prerequisites section to call out PS7 requirement with install command"
  debug_session: ""
