---
status: complete
phase: 07-threat-hunting-case-management
source: [07-01-SUMMARY.md, 07-02-SUMMARY.md, 07-03-SUMMARY.md, 07-04-SUMMARY.md, 07-05-SUMMARY.md]
started: 2026-03-17T20:00:00Z
updated: 2026-03-17T20:00:00Z
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
  status: failed
  reason: "User reported: dashboard shows alerts/evidence/event-timeline panels only; no Investigation, Cases, or Hunt tab/panel visible. CasePanel.svelte and HuntPanel.svelte were created but not wired into the app's navigation or tab system."
  severity: major
  test: 10
  artifacts: []
  missing: []

- truth: "POST /api/hunt accepts {\"template_id\": \"...\", \"params\": {...}} as documented"
  status: failed
  reason: "User reported: 422 validation error — endpoint requires field named 'template', not 'template_id'. Request contract mismatch between implementation and CONTEXT.md spec."
  severity: major
  test: 7
  artifacts: []
  missing: []

- truth: "Cases created via POST /api/cases are immediately visible in GET /api/cases list"
  status: failed
  reason: "User reported: POST returned success in Test 2 but GET /api/cases returned empty list in Test 3; no case_id available for subsequent tests. POST and GET appear to use different SQLite store instances."
  severity: major
  test: 4
  artifacts: []
  missing: []

- truth: "start.ps1 starts the backend successfully when invoked from a terminal"
  status: failed
  reason: "User reported: script cannot be run — #Requires -Version 7.0 not satisfied when invoking with `powershell` (PS 5.1). Must use `pwsh` (PS 7)."
  severity: major
  test: 1
  artifacts: []
  missing: []
