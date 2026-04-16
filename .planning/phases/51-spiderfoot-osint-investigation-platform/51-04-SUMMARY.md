---
plan: 51-04
status: complete
completed_at: "2026-04-16"
---

# Plan 51-04 Summary: Wave 2 — Frontend OSINT Tab

## What Was Done

Added the OSINT tab as the third tab (Summary | Agent | **OSINT**) in
`InvestigationView.svelte`, plus the four TypeScript interfaces and five
`api.osint` methods that back it.

### Task 1 — TypeScript interfaces + `api.osint` group (`api.ts`)

Added four exported interfaces:
- `OsintJob` — scan job status payload
- `OsintFinding` — single entity row with `misp_hit` flag
- `OsintInvestigationDetail` — extends `OsintJob` with `findings_by_type`,
  `findings_count`, and optional `dnstwist_findings`
- `DnsTwistLookalike` — typosquatting result row (supports both standalone
  `/dnstwist` and SQLite row field naming)

Extended the existing `api.osint` group with five new methods:
`startInvestigation`, `getInvestigation`, `listInvestigations`,
`cancelInvestigation`, `runDnsTwist`.

### Task 2 — Script section extension (`InvestigationView.svelte`)

- `activeTab` type widened to `'summary' | 'agent' | 'osint'`
- 13 OSINT `$state` variables added (seed, usecase, job, detail, running,
  error, timedOut, poll handle, expanded sets, graph toggle/data,
  EventSource ref)
- `onDestroy` cleanup — clears interval and closes EventSource on unmount
- `runOsintInvestigation()` — starts scan, opens SSE stream at
  `/api/osint/investigate/{job_id}/stream`, accumulates `finding` events live,
  handles terminal `status` event; 10 s safety-poll fallback; 32-min
  hard timeout guard
- Two `$effect` blocks for Cytoscape.js graph: one fetches node data when
  graph view opens, the second lazily imports `cytoscape` and renders

### Tasks 3-5 — HTML panel + CSS

- Third "OSINT" tab button wired with `onclick={() => activeTab = 'osint'}`
- Full OSINT panel: target input pre-populated from `detection.src_ip`,
  Quick/Full radio buttons (`passive`/`all`), Run button (disabled while
  running or seed empty), live status badge, yellow timeout warn-banner,
  red error-banner, entity list grouped by type with expand/collapse,
  MISP ⚠ badge on `misp_hit = 1` rows, DNSTwist lookalike expand section
  for `DOMAIN_NAME` entities, Cytoscape graph container
- 38 OSINT-specific CSS rules added in `<style>` section

## Verification

- `npx tsc --noEmit` — **0 TypeScript errors**
- `uv run pytest tests/unit/ -q` — **1162 passed**, 0 new failures
  (1 pre-existing test_metrics_api failure unrelated to this plan)

## Key Decisions

- `osintEventSource` declared at script scope (not inside `runOsintInvestigation`)
  so the `onDestroy` handler can reach it for cleanup
- Safety poll does NOT replace `osintDetail` findings while SSE is active —
  only updates `osintJob.status`; full `osintDetail` snapshot is fetched once
  on terminal state to capture `dnstwist_findings`
- Cytoscape lazily imported with dynamic `import('cytoscape')` to match the
  pattern already used in `GraphView.svelte`; nodes-only for now (edges require
  `/scanviz` endpoint, a Phase 51 stretch goal)
- OSINT panel uses `overflow-y: auto; flex: 1` so it scrolls independently
  within the copilot panel column
