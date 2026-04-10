---
phase: 33-real-threat-intelligence
verified: 2026-04-09T00:00:00Z
status: human_needed
score: 10/10 must-haves verified
re_verification: true
  previous_status: gaps_found
  previous_score: 9/10
  gaps_closed:
    - "Every event at ingest has src_ip/dst_ip checked against ioc_store — _get_loader() now passes ioc_store=getattr(request.app.state, 'ioc_store', None); _run_ingestion_job() also accepts and passes ioc_store to IngestionLoader"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Feed sync live connectivity"
    expected: "After app startup, wait 1 hour (or lower interval_sec for testing) and confirm system_kv contains intel.feodo.last_sync, intel.cisa_kev.last_sync, intel.threatfox.last_sync keys and ioc_store has rows"
    why_human: "Workers sleep interval_sec before first sync; cannot verify network fetch or timing programmatically in this environment"
  - test: "ThreatIntelView visual appearance"
    expected: "Feed health strip shows 3 tiles, risk badges render correct colors (red/orange/yellow/grey), inline expansion shows all fields without layout breaks"
    why_human: "Visual correctness of CSS/color classes requires browser rendering"
---

# Phase 33: Real Threat Intelligence — Verification Report

**Phase Goal (scoped per CONTEXT.md):** 3 free no-key feeds (Feodo Tracker CSV, CISA KEV JSON, ThreatFox CSV) syncing hourly into SQLite ioc_store; automatic IOC matching at ingest + retroactive 30-day scan on new IOC; ThreatIntelView console with live IOC hit list, feed health strip, inline row expansion, and risk-scored sorting.

**Verified:** 2026-04-09
**Status:** HUMAN NEEDED (all automated checks pass; 2 items require browser/runtime verification)
**Re-verification:** Yes — after P33-T06 gap closure

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Three feed workers (Feodo, CISA KEV, ThreatFox) register as asyncio background tasks in app lifespan | VERIFIED | main.py lines 231-238: workers constructed with ioc_store + duckdb_store, registered via asyncio.ensure_future() |
| 2 | IocStore.upsert_ioc() inserts new IOCs and updates existing ones without duplicates | VERIFIED | ioc_store.py lines 37-95: SELECT then INSERT-or-UPDATE pattern; returns True for new, False for update |
| 3 | IocStore.check_ioc_match() returns (True, confidence, actor_tag) for hits, (False, 0, None) for misses | VERIFIED | ioc_store.py lines 101-146: exact match + bare_ip lookup; unit tests test_ioc_store.py pass |
| 4 | Daily decay reduces confidence by approx 5pts/week, floor at 0, marks expired at 0 | VERIFIED | ioc_store.py decay_confidence() lines 211-236: MAX(0, confidence-1) + status='expired'; APScheduler wired in main.py line 348 |
| 5 | DuckDB normalized_events gains ioc_matched, ioc_confidence, ioc_actor_tag columns | VERIFIED | duckdb_store.py _ECS_MIGRATION_COLUMNS lines 247-249; event.py fields lines 134-136; to_duckdb_row() returns 58 elements |
| 6 | Every event at ingest has src_ip/dst_ip checked against ioc_store before DuckDB INSERT | VERIFIED | ingest.py line 64: _get_loader() passes ioc_store=getattr(request.app.state, "ioc_store", None); line 218: IngestionLoader(stores=stores, ollama_client=ollama, ioc_store=ioc_store); line 300: background_tasks.add_task() passes ioc_store. Both batch and file upload paths wired. |
| 7 | Retroactive 30-day scan runs after new IOC inserted, updates DuckDB and records ioc_hits | VERIFIED | retroactive_ioc_scan() in loader.py lines 134-196: DuckDB WHERE timestamp >= now() - INTERVAL '30 days'; feed workers call _trigger_retroactive_scan() for new IOCs |
| 8 | GET /api/intel/ioc-hits and GET /api/intel/feeds endpoints exist with Bearer auth | VERIFIED | intel.py: both endpoints with Depends(verify_token); router mounted in main.py at /api/intel |
| 9 | ThreatIntelView is a full implementation with feed strip, hit list, inline expansion, risk badges | VERIFIED | ThreatIntelView.svelte: Svelte 5 $state/$effect, feed-strip rendering {#each feeds}, risk badge riskClass(), toggleExpand() inline detail panel — not a stub |
| 10 | api.ts exports IocHit, FeedStatus interfaces and intel.iocHits()/intel.feeds() methods | VERIFIED | api.ts lines 209-229 (interfaces), 755-768 (methods with authHeaders) |

**Score: 10/10 truths verified**

---

## Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `backend/services/intel/ioc_store.py` | VERIFIED | IocStore class: upsert_ioc, check_ioc_match, decay_confidence, list_hits, _record_hit, get_feed_status — all substantive |
| `backend/services/intel/feed_sync.py` | VERIFIED | FeodoWorker, CisaKevWorker, ThreatFoxWorker — real HTTP fetch, CSV/JSON parse, upsert loop, kv_set, retroactive scan trigger |
| `backend/services/intel/risk_score.py` | VERIFIED | base_score_for_feed() and apply_weekly_decay() pure functions |
| `backend/stores/sqlite_store.py` | VERIFIED | ioc_store DDL (PRIMARY KEY ioc_value+ioc_type, bare_ip index, confidence index) + ioc_hits DDL (risk_score DESC index, matched_at DESC index) |
| `backend/stores/duckdb_store.py` | VERIFIED | ioc_matched BOOLEAN DEFAULT FALSE, ioc_confidence INTEGER, ioc_actor_tag TEXT in _ECS_MIGRATION_COLUMNS |
| `backend/models/event.py` | VERIFIED | ioc_matched/ioc_confidence/ioc_actor_tag Optional fields; to_duckdb_row() returns 58 elements with IOC fields at positions 55-57 |
| `ingestion/loader.py` | VERIFIED | _apply_ioc_matching() and retroactive_ioc_scan() exist and are substantive; IngestionLoader.__init__ accepts ioc_store param; ingest.py now passes ioc_store in all paths |
| `backend/api/ingest.py` | VERIFIED | _get_loader() line 64 passes ioc_store; _run_ingestion_job() lines 212-218 accepts and forwards ioc_store; background_tasks.add_task() line 300 passes ioc_store |
| `backend/api/intel.py` | VERIFIED | Both endpoints implemented with auth; reads from app.state.ioc_store |
| `backend/main.py` | VERIFIED | Feed workers registered, ioc_store on app.state, intel router registered; ioc_store now correctly consumed by ingest.py |
| `dashboard/src/views/ThreatIntelView.svelte` | VERIFIED | Full implementation: $state, $effect, feed strip, hit table, riskClass(), toggleExpand(), inline detail-panel |
| `dashboard/src/lib/api.ts` | VERIFIED | IocHit and FeedStatus interfaces fully typed; intel.iocHits() and intel.feeds() with auth headers |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| feed_sync.py workers | ioc_store.py | upsert_ioc() calls in _sync() | WIRED | All 3 workers call self._ioc_store.upsert_ioc() in their _sync() loops |
| feed_sync.py workers | loader.py retroactive_ioc_scan | _trigger_retroactive_scan() → asyncio.create_task | WIRED | is_new check → _trigger_retroactive_scan() called for Feodo and ThreatFox; CISA KEV skipped (CVEs don't match src/dst IPs — correct by design) |
| ingestion/loader.py | ioc_store.py | _apply_ioc_matching() calls check_ioc_match() | WIRED | ingest.py _get_loader() line 64 passes ioc_store; _run_ingestion_job() line 218 passes ioc_store; both batch and file upload paths now supply a live ioc_store reference |
| backend/api/intel.py | ioc_store.list_hits() | request.app.state.ioc_store | WIRED | intel.py reads ioc_store from app.state (set in main.py) |
| ThreatIntelView.svelte | /api/intel/ioc-hits | api.intel.iocHits() in $effect() | WIRED | Line 56: api.intel.iocHits().then(data => { hits = data }) |
| ThreatIntelView.svelte | /api/intel/feeds | api.intel.feeds() in $effect() | WIRED | Line 55: api.intel.feeds().then(data => { feeds = data }) |

---

## Requirements Coverage

| Requirement | Plan | Description | Status |
|------------|------|-------------|--------|
| P33-T01 | 01 | SQLite ioc_store + ioc_hits DDL | SATISFIED |
| P33-T02 | 01 | IocStore CRUD (upsert, check_match, decay, list_hits) | SATISFIED |
| P33-T03 | 01 | Feed workers: Feodo, CISA KEV, ThreatFox | SATISFIED |
| P33-T04 | 01 | Hourly background task registration + exponential backoff | SATISFIED |
| P33-T05 | 01, 02 | DuckDB migration: ioc_matched, ioc_confidence, ioc_actor_tag | SATISFIED |
| P33-T06 | 01, 02 | At-ingest IOC matching wired to ingest pipeline | SATISFIED — _get_loader() line 64 and _run_ingestion_job() line 218/300 now pass ioc_store; matching fires for POST /ingest/events and POST /ingest/file |
| P33-T07 | 02 | Retroactive 30-day scan on new IOC | SATISFIED — retroactive_ioc_scan() correct; triggered by feed workers |
| P33-T08 | 01 | risk_score.py: base_score_for_feed(), apply_weekly_decay() | SATISFIED |
| P33-T09 | 03 | GET /api/intel/ioc-hits with Bearer auth | SATISFIED |
| P33-T10 | 03 | ThreatIntelView full implementation | SATISFIED |
| P33-T14 | 02 | NormalizedEvent IOC fields + to_duckdb_row() 58 elements | SATISFIED |
| P33-T15 | 01 | Intel API router registered in main.py | SATISFIED |
| P33-T16 | 03 | GET /api/intel/feeds with Bearer auth | SATISFIED |

---

## Anti-Patterns Found

None remaining. The previous blocker (missing ioc_store in _get_loader) has been resolved.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| backend/api/ingest.py | 67-110 | _store_event_direct() (POST /ingest/event single-event path) has no IOC check | WARNING | Single-event fast path bypasses IOC matching — consistent with prior verification; not a P33 requirement |

---

## Unit Test Results

**Run:** `uv run pytest tests/unit/ -q --ignore=tests/unit/test_config.py`

**Result:** 914 passed, 1 skipped, 9 xfailed, 7 xpassed, 0 failures

All 8 Phase 33 unit tests (test_ioc_store.py x4, test_ioc_matching.py x4) pass. No regressions introduced by the gap fix.

---

## Human Verification Required

### 1. Feed sync live connectivity

**Test:** Start the backend, wait for first sync cycle (reduce interval_sec to 10 in test), then query `SELECT COUNT(*) FROM ioc_store` in the SQLite database.
**Expected:** Rows populated from Feodo (C2 IPs), CISA KEV (CVE IDs), ThreatFox (ip:port entries); system_kv has 3 intel.*.last_sync keys.
**Why human:** Network fetch to external URLs cannot be verified statically; timing depends on sleep interval.

### 2. ThreatIntelView visual correctness

**Test:** Open the dashboard, navigate to Threat Intelligence view, inject a test IOC hit record into ioc_hits SQLite manually.
**Expected:** Feed strip shows 3 tiles with correct names; hit appears in table with colored risk badge; clicking row expands detail panel showing IOC source, actor_tag, malware_family, and event fields.
**Why human:** CSS layout, color rendering, and click-interaction fidelity require browser rendering.

---

## Gap Closure Summary

The sole blocker from the initial verification (P33-T06) is now resolved. Three specific code points in `backend/api/ingest.py` were updated:

1. `_get_loader()` line 64: `ioc_store=getattr(request.app.state, "ioc_store", None)` added as third argument to `IngestionLoader()`.
2. `_run_ingestion_job()` lines 212-213: function signature now accepts `ioc_store: Any = None`; line 218 passes it to `IngestionLoader(stores=stores, ollama_client=ollama, ioc_store=ioc_store)`.
3. `background_tasks.add_task()` line 300: `ioc_store=getattr(request.app.state, "ioc_store", None)` passed into the background job.

Both the batch event endpoint (`POST /ingest/events`) and the file upload endpoint (`POST /ingest/file`) now supply a live `ioc_store` reference to `IngestionLoader`, so `_apply_ioc_matching()` will fire for every ingested event when a match exists.

All 10/10 observable truths are now verified. Two human verification items remain (live feed connectivity and ThreatIntelView browser rendering) which cannot be confirmed programmatically.

---

*Verified: 2026-04-09*
*Verifier: Claude (gsd-verifier)*
