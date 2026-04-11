---
status: complete
phase: 35-soc-completeness
source: 35-01-SUMMARY.md, 35-02-SUMMARY.md, 35-03-SUMMARY.md, 35-04-SUMMARY.md
started: 2026-04-10T20:00:00Z
updated: 2026-04-11T02:05:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running backend process. Start the backend fresh. It should boot without errors. Dashboard loads, lands on Overview, at least one successful API call (health dot green, or data appears).
result: pass

### 2. Overview is Default Landing Page
expected: When you open the dashboard, you land on the Overview view — not Detections. Overview is first item in Monitor group, highlighted as active.
result: pass

### 3. OverviewView Content Blocks
expected: Overview shows all 5 blocks: EVE type breakdown, Scorecard row (Total Events/Detections/IOC Matches/Assets), System Health dots, Latest AI Triage with expand/collapse, Top Detected Rules table.
result: pass

### 4. Intelligence Nav Badges Removed
expected: Threat Intel, ATT&CK Coverage, Hunting, Threat Map — no BETA badges. Only Playbooks and Recommendations retain beta badges.
result: pass

### 5. Zeek Protocol Chips Active
expected: In the Events view, the ZEEK chips (DNS, HTTP, SSL/TLS, Files, etc.) in the filter chip row should be fully interactive — not greyed out, not dashed border, not disabled. Clicking them should filter events.
result: pass

### 6. Triage Panel in DetectionsView
expected: The Detections view has a collapsible triage panel at the top (open by default). Shows latest triage summary and expandable full text. "Run Triage Now" button triggers a triage run (spinner, then result updates). Errors show inline, not as browser console errors.
result: pass

### 7. Auto-Triage Background Worker
expected: Without clicking "Run Triage Now", a triage result is present (from the background worker that runs at boot). Result has a timestamp from today.
result: pass

### 8. Timeline Playbook Rows
expected: If you open an Investigation timeline for any investigation with playbook runs, the timeline includes "Playbook: {name} — {status}" entries. (Skip if no investigations with playbook_runs in your data.)
result: skipped
reason: No investigations with playbook_runs in current data

## Summary

total: 8
passed: 6
issues: 0
pending: 0
skipped: 2

## Gaps

[none]
