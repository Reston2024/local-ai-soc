---
phase: 36-zeek-full-telemetry
plan: "02"
subsystem: ingestion/malcolm_collector
tags: [zeek, normalizers, ingestion, python]
dependency_graph:
  requires: [36-01]
  provides: [21 Zeek log type normalizers wired into poll loop]
  affects: [ingestion/jobs/malcolm_collector.py, tests/unit/test_zeek_normalizers.py]
tech_stack:
  added: []
  patterns:
    - Triple-fallback field access for all Zeek normalizers (nested dict -> dotted flat key -> Arkime flat key)
    - Single dispatch loop over (log_type, cursor_suffix, normalizer_fn, counter_attr) tuples
key_files:
  created: []
  modified:
    - ingestion/jobs/malcolm_collector.py
    - tests/unit/test_zeek_normalizers.py
    - tests/unit/test_malcolm_collector.py
decisions:
  - "36-02: dns_zeek uses cursor key 'malcolm.zeek_dns_zeek.last_timestamp' (not 'malcolm.zeek_dns.last_timestamp') to avoid collision with EVE DNS cursor"
  - "36-02: dispatch loop pattern (list of 4-tuples) is DRY — all 21 types share identical ingest+count logic, only normalizer fn and cursor suffix differ"
  - "36-02: test_poll_all_eve_types updated to assert 31 cursor keys (was 8) — Rule 1 auto-fix, assertion was stale post-implementation"
metrics:
  duration_minutes: 20
  completed_date: "2026-04-11"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
  tests_added: 0
  tests_total: 989
requirements: [P36-T04, P36-T05, P36-T06, P36-T07, P36-T08]
---

# Phase 36 Plan 02: Zeek Full Normalizers Summary

Implement all 21 remaining Zeek log type normalizers (http/ssl/x509/files/notice, kerberos/ntlm/ssh, smb_mapping/smb_files/rdp/dce_rpc, dhcp/dns_zeek/software/known_host/known_service, sip/ftp/smtp/socks/tunnel/pe) in MalcolmCollector and wire them into the poll loop.

## What Was Built

MalcolmCollector now covers 23 Zeek log types total (conn+weird from Plan 01 plus these 21). Every normalizer follows the triple-fallback field access pattern. The poll loop uses a single dispatch over 21 4-tuples — no copy-paste ingest blocks.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | P36-T04/T05 normalizers: HTTP/SSL/x509/files/notice + kerberos/ntlm/ssh | 020c87e | malcolm_collector.py |
| 2 | P36-T06/T07/T08 normalizers: smb/rdp/dce_rpc + dhcp/dns/software/known + sip/ftp/smtp/socks/tunnel/pe | 020c87e | malcolm_collector.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_poll_all_eve_types assertion was stale**
- **Found during:** Task 2 (full unit suite run)
- **Issue:** test_poll_all_eve_types asserted exactly 8 cursor keys and `call_count == 8`; after wiring 21 new normalizers the poll loop calls _fetch_index 31 times (8 original + 23 new log types)
- **Fix:** Updated expected_keys set to include all 31 cursor keys and changed `call_count == len(expected_keys)`
- **Files modified:** tests/unit/test_malcolm_collector.py
- **Commit:** 020c87e

## Verification

```
uv run pytest tests/unit/test_zeek_normalizers.py -v   # 16 passed
uv run pytest tests/unit/ -q                           # 989 passed, 0 failed
```

## Self-Check

- [x] 21 new normalizer methods in malcolm_collector.py
- [x] All 21 wired into _poll_and_ingest() via dispatch loop
- [x] All 16 test_zeek_normalizers tests GREEN
- [x] Full unit suite 989 passed, 0 failures
- [x] Commit 020c87e exists
