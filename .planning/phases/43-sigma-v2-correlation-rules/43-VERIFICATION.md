---
phase: 43-sigma-v2-correlation-rules
verified: 2026-04-12T20:00:00Z
status: passed
score: 6/6 must-haves verified
---

# Phase 43: Sigma v2 Correlation Rules — Verification Report

**Phase Goal:** Add multi-event correlation to the detection pipeline using DuckDB window queries. Detect port scans (N distinct dst_ports from one src_ip in window), brute force (N failed auths in window), and multi-stage chains (rules A+B+C for same entity within T seconds) without a separate correlation engine. Implement beaconing detection via DuckDB coefficient of variation query.

**Verified:** 2026-04-12T20:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Port scan detection exists and fires for 15+ distinct dst_ports/60s | VERIFIED | `_detect_port_scans()` in correlation_engine.py, DuckDB tumbling bucket query, test_port_scan_detection PASSED |
| 2 | Brute force detection exists and fires for 10+ failed auths/60s | VERIFIED | `_detect_brute_force()` in correlation_engine.py, filters by event_outcome/event_type/ssh_auth_success, test_brute_force_detection PASSED |
| 3 | Beaconing detection uses CV < 0.3 over 20+ connections | VERIFIED | `_detect_beaconing()` uses LAG() + STDDEV_POP/AVG in DuckDB, HAVING count >= 19, test_beaconing_cv_detection PASSED |
| 4 | Multi-stage chain correlation fires when rules co-trigger for same entity | VERIFIED | `_detect_chains()` + `_query_chain()` fully implemented, queries SQLite detections for entity_key matches, test_chain_detection PASSED |
| 5 | Correlation hits surface as DetectionRecord with correlated_event_ids | VERIFIED | All detection methods produce DetectionRecord with matched_event_ids, entity_key, rule_id prefixed with 'corr-'; save_detections() persists to SQLite |
| 6 | DetectionsView shows CORR filter chip and expand panel for corr-* rows | VERIFIED | typeFilter rune, displayDetections derived, corrBadgeLabel(), CORR/ANOMALY/SIGMA chips, corr-expand-panel branch on rule_id.startsWith('corr-') all present in DetectionsView.svelte |

**Score:** 6/6 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `detections/correlation_engine.py` | CorrelationEngine class with all detection methods | VERIFIED | 329 lines, fully implemented — port scan, brute force, beaconing, chains, load_chains, _query_chain, run(), save_detections(), _is_dedup_suppressed() |
| `detections/correlation_chains.yml` | Two pre-built chains (scan-bruteforce, recon-to-exploit) | VERIFIED | Both chains present with rule_ids, window_minutes=15, severity=critical |
| `backend/core/config.py` | CORRELATION_LOOKBACK_HOURS and CORRELATION_DEDUP_WINDOW_MINUTES | VERIFIED | Lines 116-117, values 2 and 60 |
| `backend/stores/sqlite_store.py` | entity_key column migration and insert_detection() support | VERIFIED | try/except ALTER TABLE at line 444-446; insert_detection() has entity_key kwarg at line 753, included in INSERT at line 783 |
| `backend/models/event.py` | DetectionRecord has entity_key field | VERIFIED | `entity_key: Optional[str] = None` at line 393 |
| `backend/main.py` | CorrelationEngine instantiated in lifespan, correlation_chains.yml loaded | VERIFIED | Lines 342-356, _chains_path check, load_chains() call, app.state._correlation_engine_for_ingester set |
| `backend/api/ingest.py` | _get_loader() passes correlation_engine to IngestionLoader | VERIFIED | Line 66: `correlation_engine=getattr(request.app.state, "_correlation_engine_for_ingester", None)` |
| `ingestion/loader.py` | correlation_engine parameter, engine.run() called after ingest | VERIFIED | Line 360 parameter, lines 527-531 and 609-613 call engine.run()/save_detections() |
| `dashboard/src/lib/api.ts` | Detection interface has correlation_type and matched_event_count | VERIFIED | Lines 103-104 |
| `dashboard/src/views/DetectionsView.svelte` | typeFilter, displayDetections, corrBadgeLabel, CORR chip, expand panel | VERIFIED | All present at expected locations; expand panel branches on d.rule_id?.startsWith('corr-') |
| `tests/unit/test_correlation_engine.py` | 9 tests, all passing | VERIFIED | 9 passed in 1.29s |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `CorrelationEngine` | DuckDB normalized_events | `stores.duckdb.fetch_all(sql)` | WIRED | All three detection methods call fetch_all with window queries |
| `CorrelationEngine` | SQLite detections table | `stores.sqlite._conn.execute` / `insert_detection()` | WIRED | _is_dedup_suppressed queries directly; save_detections calls insert_detection |
| `IngestionLoader.ingest_events` | `CorrelationEngine.run()` | `self._correlation_engine.run()` | WIRED | Step 5 block in ingest_events() at lines 527-531 and 609-613 |
| `backend/main.py` lifespan | `CorrelationEngine` | `_CorrelationEngine(stores=stores)` + `app.state` | WIRED | Lines 342-356 |
| `backend/api/ingest.py` `_get_loader` | `app.state._correlation_engine_for_ingester` | `getattr(request.app.state, ...)` | WIRED | Line 66 |
| `DetectionsView` | `corr-*` filter | `typeFilter === 'CORR'` + `d.rule_id?.startsWith('corr-')` | WIRED | displayDetections derived, each loop uses displayDetections |
| `DetectionsView` expand panel | matched_event_ids | `{#if d.rule_id?.startsWith('corr-')}` | WIRED | Panel branches on rule_id prefix, renders d.matched_event_ids as code pills |
| `correlation_chains.yml` | `_detect_chains()` | `load_chains()` called from main.py on startup | WIRED | main.py lines 348-350, _chains_path check, load_chains called |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| P43-T01 | 43-02 | Beaconing detection — CV < 0.3 over 20+ connections per (src_ip, dst_ip, dst_port) | SATISFIED | _detect_beaconing() uses STDDEV_POP/AVG CV, HAVING count >= 19 (= 20 connections), test_beaconing_cv_detection PASSED |
| P43-T02 | 43-02 | Port scan detection — N distinct dst_ports from one src_ip within window | SATISFIED | _detect_port_scans() counts DISTINCT dst_port per src_ip/60s bucket, threshold >= 15, test_port_scan_detection PASSED |
| P43-T03 | 43-02 | Brute force detection — N failed auth events for same target within window | SATISFIED | _detect_brute_force() filters auth failures, threshold >= 10/60s, test_brute_force_detection PASSED |
| P43-T04 | 43-03 | Multi-stage chain correlation | SATISFIED | _detect_chains() + _query_chain() implemented, YAML config with 2 chains, test_chain_detection PASSED |
| P43-T05 | 43-02/43-03 | Surface correlation hits as detections with correlated_event_ids evidence | SATISFIED | All detection methods populate matched_event_ids; save_detections() persists with entity_key; dedup prevents duplicates |
| P43-T06 | 43-04 | CorrelationView or correlation panel in DetectionsView | SATISFIED | CORR filter chip + type badge (PORT_SCAN/BRUTE_FORCE/BEACON/CHAIN) + expand panel showing matched_event_ids |

---

## Test Results

```
tests/unit/test_correlation_engine.py (9 tests)
  PASSED  test_correlation_engine_module_exists
  PASSED  test_port_scan_detection
  PASSED  test_brute_force_detection
  PASSED  test_beaconing_cv_detection
  PASSED  test_detection_record_created
  PASSED  test_dedup_suppresses_repeat
  PASSED  test_chain_detection
  PASSED  test_chain_yaml_loading
  PASSED  test_ingest_hook_calls_correlation

Full suite: 1067 passed, 3 skipped, 9 xfailed, 7 xpassed — zero regressions
```

---

## Anti-Patterns Found

None. No TODO/FIXME/placeholder comments found in phase artifacts. No stub return values (`return []` as stub) — `_detect_chains()` returns `[]` only when `self._chains` is empty (correct guard logic, not a stub). Implementation is substantive throughout.

---

## Notable Observations (Non-blocking)

The firewall collector (`_fw_loader`) and Malcolm collector (`_mc_loader`) in `backend/main.py` are instantiated without `correlation_engine=`. This means batches ingested through those background collectors will not trigger correlation analysis. However:

- These collectors are conditionally enabled via `FIREWALL_ENABLED` / `MALCOLM_ENABLED` settings
- The phase goal and all plan task descriptions only specify `ingestion/loader.py` (the general loader used by API routes) and the primary `_get_loader()` path in `ingest.py`
- The correlation engine runs independently on a lookback window — any events ingested by these collectors will be picked up during the next correlation run triggered by an API ingest call
- This is not a blocker for any of P43-T01 through P43-T06

---

## Human Verification Required

| Test | What to do | Expected | Why human |
|------|------------|----------|-----------|
| CORR chip visual | In DetectionsView with some corr-* detections loaded, click the CORR chip | Table filters to show only corr-* rows; chip highlights in red | Visual filter behavior requires browser |
| Correlation badge display | With a corr-portscan detection visible, observe the row | "PORT_SCAN" badge appears in red after rule_name | Visual rendering |
| Expand panel for corr-* row | Click a correlation detection row to expand | Shows "Matched Event IDs" header + event ID pills; no CAR analytics panel for corr-* rows | Expand/collapse UX |
| Expand panel for sigma row | Click a non-correlation row to expand | Shows existing CAR analytics panel unchanged | Regression check — corr branch must not break others |

---

## Verdict

Phase 43 goal is **achieved**. All six observable truths are verified in the codebase. All 9 unit tests pass. The full 1067-test suite shows no regressions. Every requirement (P43-T01 through P43-T06) has implementation evidence. The correlation engine is fully wired from lifespan initialization through the ingest API to SQLite persistence, with YAML-driven chain configuration and frontend surfacing via filter chips, type badges, and expand panels.

---

_Verified: 2026-04-12T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
