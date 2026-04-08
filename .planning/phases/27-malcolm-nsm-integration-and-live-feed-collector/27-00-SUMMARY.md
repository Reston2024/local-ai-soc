---
phase: 27-malcolm-nsm-integration-and-live-feed-collector
plan: "00"
subsystem: testing
tags: [wave-0, stubs, tdd, malcolm, nsm, dispatch]
dependency_graph:
  requires: []
  provides:
    - tests/unit/test_malcolm_collector.py
    - tests/unit/test_malcolm_normalizer.py
    - tests/unit/test_dispatch_endpoint.py
  affects:
    - ingestion/jobs/malcolm_collector.py (activated in 27-02)
    - backend/api/recommendations.py (activated in 27-04)
tech_stack:
  added: []
  patterns:
    - try/except ImportError guard + pytestmark skipif for pre-implementation stubs
    - simple module-level pytestmark skip for stubs where module already exists
key_files:
  created:
    - tests/unit/test_malcolm_collector.py
    - tests/unit/test_malcolm_normalizer.py
    - tests/unit/test_dispatch_endpoint.py
  modified: []
decisions:
  - "27-00: try/except ImportError guard used for test_malcolm_collector.py and test_malcolm_normalizer.py — ingestion/jobs/malcolm_collector.py does not yet exist"
  - "27-00: simple module-level pytestmark skip used for test_dispatch_endpoint.py — backend/api/recommendations.py already exists, no import risk"
  - "27-00: 17 stubs across 3 files all report SKIPPED; full unit suite 850 passed, 0 failures"
metrics:
  duration_seconds: 106
  completed_date: "2026-04-07"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 0
requirements_covered:
  - P27-T02
  - P27-T04
---

# Phase 27 Plan 00: Wave-0 Test Stubs Summary

**One-liner:** Three pre-skipped stub files (17 tests) scaffold Malcolm collector and dispatch endpoint tests before any Phase 27 implementation starts.

## What Was Built

Wave-0 Nyquist-compliant test scaffolding for Phase 27. All stubs are pre-skipped so the full test suite continues passing. Executor plans 27-02, 27-03, and 27-04 will activate these stubs once the corresponding implementations are complete.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create test_malcolm_collector.py stubs | 0ebc40e | tests/unit/test_malcolm_collector.py |
| 2 | Create test_malcolm_normalizer.py stubs | 5be2eee | tests/unit/test_malcolm_normalizer.py |
| 3 | Create test_dispatch_endpoint.py stubs + verify full suite | 504ee12 | tests/unit/test_dispatch_endpoint.py |

## Stub Inventory

### test_malcolm_collector.py (5 stubs, activated in 27-02)
- test_malcolm_collector_init_sets_defaults
- test_malcolm_collector_status_shape
- test_malcolm_collector_run_cancels_cleanly
- test_malcolm_collector_backoff_on_failure
- test_malcolm_collector_heartbeat_updates_kv

### test_malcolm_normalizer.py (7 stubs, activated in 27-03)
- test_normalize_alert_extracts_src_ip
- test_normalize_alert_extracts_dst_ip
- test_normalize_alert_severity_mapping
- test_normalize_alert_detection_source
- test_normalize_syslog_source_type
- test_normalize_alert_raw_event_truncated
- test_normalize_alert_returns_none_on_missing_ip

### test_dispatch_endpoint.py (5 stubs, activated in 27-04)
- test_dispatch_approved_recommendation_returns_200
- test_dispatch_non_approved_returns_409
- test_dispatch_not_found_returns_404
- test_dispatch_schema_validation_failure_returns_422
- test_dispatch_does_not_make_http_call

## Verification Results

```
17 skipped in 0.06s  (all three stub files)
850 passed, 18 skipped, 9 xfailed, 7 xpassed, 7 warnings  (full unit suite)
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files created:
- FOUND: tests/unit/test_malcolm_collector.py
- FOUND: tests/unit/test_malcolm_normalizer.py
- FOUND: tests/unit/test_dispatch_endpoint.py

Commits verified:
- FOUND: 0ebc40e
- FOUND: 5be2eee
- FOUND: 504ee12
