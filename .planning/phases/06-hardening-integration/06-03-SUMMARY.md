---
phase: 06-hardening-integration
plan: "03"
subsystem: api
tags: [causality, mitre-attack, bfs, orchestrator, prompt-template, llm]

# Dependency graph
requires:
  - phase: 06-01
    provides: entity_resolver + attack_chain_builder (BFS with cycle detection)
  - phase: 06-02
    provides: mitre_mapper + scoring (TECHNIQUE_CATALOG, score_chain)
provides:
  - build_causality_sync: full causality orchestrator integrating chain builder, MITRE mapper, scorer, build_graph
  - CausalityResult dict with 9 keys: alert_id, nodes, edges, attack_paths, chain, techniques, score, first_event, last_event
  - investigation_summary.py: SYSTEM + TEMPLATE + format_prompt for AI-assisted investigation narratives
affects: [06-04, api-layer, dashboard-attack-chain]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Deferred import of build_graph via try/except — prevents causality module from crashing backend startup if graph builder absent
    - Empty-dict sentinel return for unknown alert_id (graceful, not 500)
    - Temporal bounds (first_event/last_event) computed from chain timestamps

key-files:
  created:
    - backend/causality/engine.py
    - prompts/investigation_summary.py
  modified: []

key-decisions:
  - "build_causality_sync is synchronous (CPU-bound) — caller wraps in asyncio.to_thread per CLAUDE.md convention"
  - "Deferred build_graph import mirrors Phase 5 deferred-import pattern; graceful fallback to empty nodes/edges/attack_paths"
  - "chain_events fallback includes triggering event when BFS returns nothing — avoids empty chain for singleton-event alerts"
  - "investigation_summary format_prompt caps nodes at 20 and events at 15 to avoid Ollama context overflow"

patterns-established:
  - "Orchestrator pattern: engine.py composes Wave 1 components via direct function calls, no class hierarchy needed"
  - "Prompt template pattern: SYSTEM constant + TEMPLATE string + format_prompt function — consistent with analyst_qa.py"

requirements-completed:
  - FR-6-causality-engine

# Metrics
duration: 15min
completed: 2026-03-16
---

# Phase 6 Plan 03: Causality Engine Orchestrator Summary

**build_causality_sync orchestrator composing BFS chain builder, MITRE mapper, scorer, and build_graph into a single 9-key CausalityResult dict; plus investigation_summary.py AI prompt template**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-16T22:35:00Z
- **Completed:** 2026-03-16T22:50:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Full causality engine orchestrator in engine.py: 9-step pipeline (find alert, find trigger event, BFS chain, correlated alerts, extract MITRE tags, map techniques, score, build_graph, temporal bounds)
- Returns empty dict for unknown alert_id — graceful sentinel, not 500
- investigation_summary.py prompt template with SYSTEM/TEMPLATE constants and format_prompt function following established analyst_qa.py pattern
- TestCausalityEngine XPASS; full suite: 41 passed, 38 xpassed, 5 xfailed, 0 regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement causality engine orchestrator** - `0145467` (feat)
2. **Task 2: Create investigation_summary.py prompt template** - `cae3786` (feat)

## Files Created/Modified
- `backend/causality/engine.py` - Full orchestrator replacing stub: build_causality_sync with 9-key CausalityResult dict
- `prompts/investigation_summary.py` - Investigation summary prompt template with SYSTEM, TEMPLATE, format_prompt

## Decisions Made
- build_causality_sync is synchronous — CPU-bound, no I/O; caller wraps in asyncio.to_thread per CLAUDE.md convention
- Deferred build_graph import via try/except mirrors Phase 5 deferred-import pattern so causality module doesn't crash startup if graph builder absent
- BFS fallback: when find_causal_chain returns empty, include the triggering event directly so chain is never empty for valid alerts
- format_prompt caps node list at 20 and event list at 15 to avoid Ollama qwen3:14b context window overflow

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- engine.py exports build_causality_sync (used by Plan 04 API routes)
- investigation_summary.py exports format_prompt (used by Plan 04 POST /investigate/{alert_id}/summary endpoint)
- All 9 CausalityResult keys documented and verified; Plan 04 can wire directly without changes
- 5 remaining xfail stubs (TestGraphEndpoint, TestEntityEndpoint, TestAttackChainEndpoint, TestQueryEndpoint, TestDashboardBuild) are Plan 04 targets

---
*Phase: 06-hardening-integration*
*Completed: 2026-03-16*
