---
phase: 33-real-threat-intelligence
plan: 03
subsystem: threat-intelligence-api-frontend
tags: [fastapi, svelte5, intel-api, ioc-hits, feed-status, typescript]
dependency_graph:
  requires: [33-01]
  provides: [GET /api/intel/ioc-hits, GET /api/intel/feeds, ThreatIntelView UI]
  affects: [dashboard/src/views/ThreatIntelView.svelte, dashboard/src/lib/api.ts]
tech_stack:
  added: []
  patterns: [asyncio.to_thread for blocking IocStore calls, Svelte 5 $state/$effect runes, expandRow inline panel pattern]
key_files:
  created:
    - backend/api/intel.py
  modified:
    - dashboard/src/lib/api.ts
    - dashboard/src/views/ThreatIntelView.svelte
decisions:
  - "verify_token is in backend.core.auth (not backend.core.deps) — corrected plan pseudocode import"
  - "Svelte 5 $state/$effect used throughout; no writable() or onMount"
  - "Feed strip always visible even in empty state"
  - "expandedId toggling follows HuntingView pattern exactly"
requirements-completed:
  - P33-T09
  - P33-T10
  - P33-T16
metrics:
  duration: "~35 minutes"
  completed_date: "2026-04-10"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 2
---

# Phase 33 Plan 03: Threat Intelligence API + ThreatIntelView Summary

One-liner: Authenticated intel API (ioc-hits + feeds) and full ThreatIntelView rewrite with Svelte 5 runes — feed strip, risk-badged hit list, inline row expansion, and empty state.

## Files Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `backend/api/intel.py` | Created | FastAPI router: GET /api/intel/ioc-hits + GET /api/intel/feeds |
| `dashboard/src/lib/api.ts` | Modified | Added IocHit/FeedStatus interfaces + api.intel.iocHits()/feeds() methods |
| `dashboard/src/views/ThreatIntelView.svelte` | Modified | Full rewrite — feed strip, hit table, inline expand, empty/loading state |

## API Endpoints

### GET /api/intel/ioc-hits
- Auth: Bearer token required (403 without)
- Query param: `limit` (default 200)
- Returns: `list[dict]` — ioc_hits sorted by risk_score DESC
- Response shape: `[{id, event_timestamp, hostname, src_ip, dst_ip, ioc_value, ioc_type, ioc_source, risk_score, actor_tag, malware_family, matched_at}, ...]`

### GET /api/intel/feeds
- Auth: Bearer token required (403 without)
- Returns: `list[dict]` — 3 feed health objects
- Response shape: `[{feed, last_sync, ioc_count, status}, ...]` — feeds: feodo, cisa_kev, threatfox

## ThreatIntelView Component Structure

- Top: compact horizontal feed-strip (3 tiles: Feodo Tracker, CISA KEV, ThreatFox)
  - Each tile: name | ioc_count | last_sync (relative) | status (colour-coded)
  - ok=green-400, stale=yellow-400, error=red-400, never=zinc-500
- Below: IOC hit list table (7 columns: Risk | Timestamp | Hostname | Src IP | Dst IP | IOC | Actor)
  - Risk badge: colour pill — red>=75, orange>=50, yellow>=25, zinc<25
  - Row click: toggles inline detail panel (ioc fields + event fields)
- Empty state: "No IOC matches yet — feeds syncing hourly." (feed strip still shows)
- Loading state: "Loading..." while hits === null

## Decisions Made

1. **verify_token import location**: Plan pseudocode said `from backend.core.deps import verify_token` but `verify_token` lives in `backend.core.auth`. Fixed immediately (Rule 1 auto-fix — caused ImportError that prevented tests running).
2. **Svelte 5 runes**: Used `$state<IocHit[] | null>(null)` initial value to distinguish loading vs empty.
3. **Feed strip always visible**: Shown even when hits.length === 0 per plan requirement.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong import path for verify_token**
- **Found during:** Task 1 — import test after creating backend/api/intel.py
- **Issue:** Plan pseudocode specified `from backend.core.deps import verify_token` but `verify_token` is in `backend.core.auth`
- **Fix:** Changed import to `from backend.core.auth import verify_token`
- **Files modified:** `backend/api/intel.py`
- **Commit:** 5c03102

## Pre-existing Test Failures (Out of Scope)

These were failing before this plan ran and are not caused by my changes:
- `tests/unit/test_config.py::test_cybersec_model_default` — OLLAMA_CYBERSEC_MODEL set in .env overrides default
- `tests/unit/test_normalized_event.py::test_new_fields_in_duckdb_row` — expects 55 fields, Plan 33-02 added 3 more (now 58)
- `tests/unit/test_normalized_event_ecs.py::test_to_duckdb_row_includes_new_fields` — same root cause

## Human Checkpoint

**Status:** APPROVED — User confirmed automated tests passed (3/3 unit tests green, TypeScript compiles clean). ThreatIntelView visual verification accepted.

## Verification Results

- `uv run pytest tests/unit/test_api_intel.py -x -q` — 3/3 PASSED
- `npx tsc --noEmit` — exits 0 (no TypeScript errors)
- Pre-existing unit failures: 3 (out of scope, unchanged by this plan)

## Next Phase Readiness

- Plan 33-03 is the final code plan for Phase 33. The intel API surface (ioc-hits, feeds) is live and verified.
- Phase 33 VERIFICATION.md checklist can now be executed to formally close Phase 33.
- Phase 34 (full commercial TIP: MISP/TAXII, OTX, PassiveDNS, hash/URI matching, entity_risk_scores) may extend this API surface — intel.py router is the extension point.

## Self-Check: PASSED

- `backend/api/intel.py` — FOUND
- `dashboard/src/lib/api.ts` — FOUND (with IocHit, FeedStatus, api.intel methods)
- `dashboard/src/views/ThreatIntelView.svelte` — FOUND (rewritten)
- Commits: 5c03102 (Task 1), 8e3a4bc (Task 2) — FOUND
- Human checkpoint: APPROVED
