---
status: testing
phase: 49-chainsaw-windows-event-log-analysis
source: 49-01-SUMMARY.md, 49-02-SUMMARY.md, 49-03-SUMMARY.md
started: 2026-04-14T23:40:00Z
updated: 2026-04-14T23:40:00Z
---

## Current Test

number: 7
name: COMPLETE
awaiting: none

## Tests

### 1. Chainsaw health endpoint
expected: GET /health shows chainsaw status ok, binary C:\Tools\chainsaw\chainsaw.exe, detection_count 219
result: pass

### 2. EVTX ingest produces Chainsaw detections
expected: After ingesting an EVTX file, the loader log shows "Chainsaw scan complete" with findings > 0. GET /api/detections returns records with detection_source = "chainsaw".
result: pass — log shows "Chainsaw scan complete" findings=219; GET /api/detect returns detection_source="chainsaw" records (301 total)

### 3. SHA-256 dedup prevents re-scan
expected: Re-ingesting the same EVTX file a second time produces 0 new Chainsaw findings (already scanned). The loader log shows "Chainsaw scan skipped — already scanned" or similar dedup message.
result: pass — re-ingest of same EVTX produced 0 new detections (still 219 chainsaw). chainsaw_scanned_files has 1 row (INSERT OR IGNORE prevented duplicate). Loader log shows loaded=0 for re-ingest.

### 4. CHAINSAW chip in DetectionsView
expected: Navigate to /detections. A teal "CHAINSAW (219)" chip appears in the filter bar to the right of the HAYABUSA chip.
result: pass — teal CHAINSAW (100) chip visible to the right of HAYABUSA chip in filter bar. Count reflects current page load limit (100 fetched, all chainsaw-sourced).

### 5. CHAINSAW chip filters detections
expected: Click the CHAINSAW chip. The detection list filters to show only chainsaw-sourced detections. Each row shows a teal "CHAINSAW" badge. Click again to clear the filter.
result: pass — clicking CHAINSAW chip activates teal border, all rows show CHAINSAW badge. Clicking again returns to All view with mixed sources.

### 6. Chainsaw Findings tile in Overview
expected: Navigate to / (Overview). The scorecard row shows a teal "Chainsaw Findings" tile with the value 219 next to the amber "Hayabusa Findings" tile.
result: pass — CHAINSAW FINDINGS: 219 (teal #14b8a6) tile visible beside HAYABUSA FINDINGS: 58 (amber) in scorecard row.

### 7. Chainsaw health row in System Health
expected: The System Health card shows a Chainsaw row with a green dot and "219 findings" in teal text. Overall API Backend status shows "healthy" (not degraded).
result: pass — System Health shows Chainsaw: green dot, "219 Findings" in teal. API Backend: Healthy.

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
