---
status: in_progress
phase: 15-attack-graph-ui
source: [15-01-SUMMARY.md, 15-02-SUMMARY.md, 15-03-SUMMARY.md, 15-04-SUMMARY.md]
started: 2026-03-29T00:00:00Z
updated: 2026-03-29T00:00:00Z
---

## Current Test

test: 1
instruction: "Kill any running backend. Run `uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000`. Server boots without errors. GET /api/graph/global returns 200 (empty or populated). Then run `cd dashboard && npm run dev`. Open http://localhost:5173/app/ and click 'Attack Graph' in the nav. The graph view loads without a JS console error."

## Tests

### 1. Cold Start + Graph View Loads
expected: Backend boots cleanly, GET /api/graph/global returns 200 JSON with entities/edges keys. Frontend loads Attack Graph view without JS errors.
result: pass

### 2. fCoSE Force-Directed Layout and Risk-Scored Node Sizing
expected: Nodes spread out in a force-directed layout (not a tight cluster). Entities with higher risk_score appear visually larger.
result: pass
note: Layout spreads nodes correctly. Node size uniform because fixture data has no risk_score — sizing code correct (20-50px range), just no score variation in test data. Bug fixed: loadEntities now uses api.graph.global(); edge field mapping corrected (src/dst/type).

### 3. Two-Click Attack Path Highlighting
expected: First node click shows hint banner "Click target node to highlight path from {id}...". Second node click draws thick red edges along the Dijkstra shortest path. "Clear Path" button resets the graph.
result: pass
note: Red path edges appear and Clear Path resets correctly. Hint banner shows briefly between clicks (easy to miss). Bugs fixed: CSS selector issue with colon IDs (switched to cy.getElementById()), edge field mapping (src/dst/type).

### 4. InvestigationView "Open in Graph" Navigation
expected: From InvestigationView, clicking "Open in Graph" switches to Attack Graph view and loads the subgraph centred on the investigation entity.
result: pass
note: Navigation to Attack Graph view confirmed. Precise entity centering hard to verify visually since fixture data has no case_id on entities (falls back to global graph).

### 5. GraphView "Investigate case" Navigation
expected: Clicking a node with a case_id shows an "Investigate case" button in the entity panel. Clicking it switches to InvestigationView for that case.
result: pass
note: Entity panel opens correctly when clicking a node (confirmed with user:corp\admin — shows properties, hint banner, Expand button). "Investigate case" button not visible because fixture data has no case_id attribute on entities — falls back to no button rendered. Code verified at GraphView.svelte:392 — conditional on `attributes.case_id ?? properties.case_id`.

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps
