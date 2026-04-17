---
phase: 53-network-privacy-monitoring
plan: "01"
subsystem: testing
tags: [tdd, wave-0, privacy, blocklist, detection, api]
dependency_graph:
  requires: []
  provides: [PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05, PRIV-06, PRIV-07, PRIV-08, PRIV-09, PRIV-10, PRIV-11]
  affects: [53-02, 53-03]
tech_stack:
  added: []
  patterns: [double-guard-skip, importorskip-module-level, wave-0-tdd-stubs]
key_files:
  created:
    - tests/unit/test_privacy_blocklist.py
    - tests/unit/test_privacy_detection.py
    - tests/unit/test_privacy_api.py
  modified: []
decisions:
  - "Module-level importorskip used for all 3 files — entire file skips atomically when implementation absent (consistent with Phases 48/49/51/52 pattern)"
  - "PRIV-11 normalizer stub placed in test_privacy_blocklist.py alongside PRIV-01..04 to minimize file count"
  - "test_privacy_detection.py and test_privacy_api.py both guard on backend.api.privacy — same source module, clean separation of scanner vs API concerns"
metrics:
  duration: "~5 minutes"
  completed_date: "2026-04-17"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 0
---

# Phase 53 Plan 01: Network Privacy Monitoring Wave-0 TDD Stubs Summary

**One-liner:** Wave-0 TDD stubs covering all 11 PRIV requirements across 3 test files, all atomically skipped via double-guard importorskip pattern.

## What Was Built

Three test files defining the behavioral contracts for Phase 53 network privacy monitoring. Plans 53-02 (blocklist implementation) and 53-03 (scanner + API) will turn these stubs GREEN.

### test_privacy_blocklist.py (6 stubs)
- **PRIV-01** `test_parse_easyprivacy_extracts_domains` — `_parse_easyprivacy()` strips comment/blank lines, returns only valid domains
- **PRIV-02** `test_parse_disconnect_extracts_all_categories` — `_parse_disconnect()` returns `(domain, category)` tuples for all Disconnect.me categories
- **PRIV-03** `test_store_upsert_and_lookup` — `PrivacyBlocklistStore.upsert_domain()` + `is_tracker()` with in-memory SQLite
- **PRIV-04** `test_worker_populates_store` — `PrivacyWorker._sync()` calls both parsers and upserts results
- **PRIV-04b** `test_feed_meta_updated_after_sync` — `store.get_feed_status()` returns list with `feed`/`last_sync`/`domain_count` keys
- **PRIV-11** `test_normalize_http_extended_fields` — `_normalize_http(doc)` maps zeek HTTP referrer/body lengths/mime types to NormalizedEvent

### test_privacy_detection.py (4 stubs)
- **PRIV-05** `test_cookie_exfil_detection_fires_on_large_body_to_tracker` — `run_privacy_scan()` fires `hit_type="cookie_exfil"` for large POST to tracker domain
- **PRIV-06** `test_tracking_pixel_detection_fires_on_tiny_image_from_tracker` — fires `hit_type="tracking_pixel"` for tiny GIF from tracker domain
- **PRIV-07** `test_no_false_positive_for_non_tracker_domain` — returns 0 detections when domain not in blocklist
- **PRIV-08** `test_detection_record_uses_privacy_source_tag` — detections have `detection_source="privacy"` and `rule_id` prefix `"privacy-"`

### test_privacy_api.py (2 stubs)
- **PRIV-09** `test_hits_endpoint_returns_list` — `GET /api/privacy/hits` returns 200 with `{"hits": [...]}`
- **PRIV-10** `test_feeds_endpoint_returns_status` — `GET /api/privacy/feeds` returns 200 with `{"feeds": [...]}` where each entry has `feed`/`last_sync`/`domain_count`

## Verification Results

```
collected 0 items / 3 skipped   (module-level importorskip fires atomically)
Full suite: 1259 passed, 9 skipped (3 new), 13 pre-existing failures unchanged
```

## Deviations from Plan

None — plan executed exactly as written.

## Key Decisions

1. **Module-level importorskip** — all 3 files use `pytest.importorskip()` at module level so the entire file skips atomically when the source module is absent. Consistent with Phases 48/49/51/52.
2. **PRIV-11 placement** — normalizer stub lives in `test_privacy_blocklist.py` alongside PRIV-01..04 as specified, using `@pytest.mark.skip` alone (separate module concern from blocklist).
3. **Shared importorskip for detection + API** — both `test_privacy_detection.py` and `test_privacy_api.py` guard on `backend.api.privacy` since both will be implemented together in Plan 53-03.

## Self-Check: PASSED

- tests/unit/test_privacy_blocklist.py: FOUND
- tests/unit/test_privacy_detection.py: FOUND
- tests/unit/test_privacy_api.py: FOUND
- Commit 35ee354: FOUND
