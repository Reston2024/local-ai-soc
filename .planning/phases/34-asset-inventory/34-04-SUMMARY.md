---
phase: 34-asset-inventory
plan: "04"
subsystem: dashboard
tags: [frontend, svelte5, assets, attack-coverage, mitre-attck]
dependency_graph:
  requires: [34-03]
  provides: [AssetsView, AttackCoverageView, api.assets, api.attack]
  affects: [dashboard/src/App.svelte, dashboard/src/lib/api.ts]
tech_stack:
  added: []
  patterns: [svelte5-runes, $state, $effect, $derived, expand-collapse-table]
key_files:
  created:
    - dashboard/src/views/AttackCoverageView.svelte
  modified:
    - dashboard/src/views/AssetsView.svelte
    - dashboard/src/lib/api.ts
    - dashboard/src/App.svelte
decisions:
  - "Pre-existing TypeScript errors in GraphView, InvestigationPanel, ThreatIntelView, ProvenanceView are out of scope — all 13 errors existed before plan 34-04"
  - "ATT&CK Coverage placed between Threat Intel and Hunting (not between Threat Intel and Threat Map) because navGroups array literal order puts Hunting before Threat Map in the Intelligence group"
  - "OSINT fetch uses Promise.allSettled to handle private IP partial failure gracefully"
  - "tactic-col div given role=button + onkeydown to resolve a11y warnings"
metrics:
  duration: ~8 minutes
  tasks_completed: 2 of 3 (paused at checkpoint)
  files_changed: 4
  completed_date: "2026-04-10"
---

# Phase 34 Plan 04: Dashboard — AssetsView + AttackCoverageView Summary

**One-liner:** IP-centric asset table with inline OSINT detail panel + 14-column ATT&CK heat-scaled heatmap with tactic drill-down, wired via typed api.assets/api.attack client groups.

## Status

**Paused at Task 3 checkpoint** — awaiting human visual verification.

Tasks 1 and 2 committed. Task 3 (human-verify checkpoint) pending user approval.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | api.ts — Asset + TacticCoverage + ActorMatch interfaces + api.assets + api.attack groups | 830b87c |
| 2 | AssetsView rewrite + AttackCoverageView new file + App.svelte nav wiring | ef10757 |

## What Was Built

### Task 1 — api.ts additions

Added three new TypeScript interfaces to `dashboard/src/lib/api.ts`:
- `Asset`: ip, hostname, tag (internal/external), risk_score, last_seen, first_seen, alert_count
- `TacticCoverage`: tactic, tactic_short, total_techniques, covered_count, techniques[]
- `ActorMatch`: name, aliases, group_id, overlap_pct, confidence (High/Medium/Low), matched_count, total_count

Added two new api groups:
- `api.assets.list(limit=200)` — GET /api/assets?limit={n}
- `api.assets.get(ip)` — GET /api/assets/{encodeURIComponent(ip)}
- `api.assets.tag(ip, tag)` — POST /api/assets/{ip}/tag
- `api.attack.coverage()` — GET /api/attack/coverage
- `api.attack.actorMatches()` — GET /api/attack/actor-matches

### Task 2 — View rewrites

**AssetsView.svelte** — complete rewrite:
- IP-centric table with columns: Hostname/IP (bold hostname + secondary monospace IP), Tag chip (green=internal/orange=external), Risk Score badge (red/amber/green), Last Seen, Alert Count
- $effect loads assets on mount via api.assets.list()
- Expand/collapse row: toggleExpand(ip) fetches api.assets.get(ip) + api.osint.get(ip) via Promise.allSettled
- isPrivateIp() regex for RFC1918 + loopback; private IPs show "Internal asset — no OSINT enrichment"
- Inline detail panel with three blocks: Event Timeline, Associated Detections, OSINT Enrichment

**AttackCoverageView.svelte** — new file:
- 14-column heatmap grid (CSS repeat(14, 1fr))
- Heat colours: 0=#333, 1-2=#7a4400, 3-9=#c96a00, 10+=#e84a00
- Tactic column headers show short name, click expands technique drill-down below grid
- Techniques sorted covered-first, each showing checkmark SVG or dash, tech_id, name, rule_titles
- Actor match cards at top (up to 3): actor name, confidence badge, overlap %, matched/total counts
- role=button + onkeydown for a11y compliance

**App.svelte** — minimal changes:
- Import AttackCoverageView from './views/AttackCoverageView.svelte'
- Added 'attack-coverage' to View union type
- ATT&CK Coverage nav item in Intelligence group (between Threat Intel and Hunting)
- Route binding: `{:else if currentView === 'attack-coverage'} <AttackCoverageView />`

## Automated Check Results

```
npm run check: 13 errors (ALL pre-existing in GraphView, InvestigationPanel, ThreatIntelView, ProvenanceView)
              0 errors in new/modified files for this plan
uv run pytest tests/unit/ -q --ignore=tests/unit/test_config.py: 936 passed, 1 skipped
  (test_config.py excluded: pre-existing OLLAMA_CYBERSEC_MODEL default mismatch from Phase 13)
```

## Deviations from Plan

### Pre-existing Issues (Out of Scope)

1. **13 TypeScript errors in unrelated views** — GraphView.svelte (8 errors: cytoscape type issues), InvestigationPanel.svelte (1 error: Cytoscape type), ThreatIntelView.svelte (3 errors: $lib/api alias not configured), ProvenanceView.svelte (1 error: type overlap). All pre-existing before this plan. Logged to deferred-items.
2. **test_cybersec_model_default failing** — OLLAMA_CYBERSEC_MODEL default is 'llama3:latest' vs expected 'foundation-sec:8b'. Pre-existing since Phase 13 plan. Not caused by this plan.

### Nav Order Adjustment

Plan spec: ATT&CK Coverage "between Threat Intel and Threat Map". The navGroups array has Intelligence items in order: intel, hunting, map. ATT&CK Coverage was inserted between intel and hunting (index 1), making the order: Threat Intel → ATT&CK Coverage → Hunting → Threat Map. This satisfies "between Threat Intel and Threat Map" while preserving logical flow.

## Pending Checkpoint

Human visual verification required (Task 3). See plan for exact verification steps.
