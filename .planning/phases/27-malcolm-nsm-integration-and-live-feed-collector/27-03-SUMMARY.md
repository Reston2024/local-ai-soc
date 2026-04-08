---
phase: 27-malcolm-nsm-integration-and-live-feed-collector
plan: "03"
subsystem: ingestion
tags: [malcolm, nsm, opensearch, normalization, suricata, syslog, ecs]

dependency_graph:
  requires:
    - phase: 27-02
      provides: "MalcolmCollector skeleton with _normalize_alert/_normalize_syslog stubs returning None"
  provides:
    - "_normalize_alert(): full ECS-aware field mapping for arkime_sessions3-* Suricata alerts → NormalizedEvent(source_type='suricata_eve')"
    - "_normalize_syslog(): full field mapping for malcolm_beats_syslog_* and plain syslog strings → NormalizedEvent(source_type='ipfire_syslog')"
    - "7 activated normalizer tests; full suite 862 passed, 0 failures"
  affects:
    - "27-04: dispatch endpoint — unrelated; no normalization dependency"
    - "27-06: end-to-end verification uses normalize pipeline; stubs now produce real NormalizedEvent objects"

tech-stack:
  added: []
  patterns:
    - "ECS-style field fallback chain: source.ip → src_ip → srcip (and destination equivalents)"
    - "severity coerced to lowercase string via str(severity).lower() — NormalizedEvent.severity is Optional[str]"
    - "raw_event = json.dumps(doc)[:8192] — 8KB hard truncation applied before NormalizedEvent construction"
    - "_normalize_syslog accepts str (plain syslog line) OR dict (OpenSearch _source) — union type dispatch on isinstance"
    - "Drop-on-missing-src_ip pattern for alerts only; syslog events never dropped"

key-files:
  created:
    - .planning/phases/27-malcolm-nsm-integration-and-live-feed-collector/27-03-SUMMARY.md
  modified:
    - ingestion/jobs/malcolm_collector.py
    - tests/unit/test_malcolm_normalizer.py

key-decisions:
  - "_normalize_syslog accepts str OR dict — test stub passed a raw syslog string; implementation handles both via isinstance check (Rule 1 auto-fix)"
  - "severity stored as str, not int — integer severity values (e.g. 3) coerced to '3' via str().lower(); tests corrected to assert event.severity == '3'"
  - "NormalizedEvent field names are src_ip/dst_ip (not source_ip/dest_ip) — test assertions corrected to match canonical model"

metrics:
  duration: 12min
  completed: "2026-04-08T04:09:43Z"
  tasks_completed: 1
  files_modified: 2
---

# Phase 27 Plan 03: Malcolm Field Normalization Summary

**ECS-aware normalization for Malcolm Suricata alerts and IPFire syslog events, producing NormalizedEvent objects with correct source_type, severity, detection_source, IP fields, and 8KB-truncated raw_event.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-08T03:57:00Z
- **Completed:** 2026-04-08T04:09:43Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Replaced `_normalize_alert()` stub with full ECS-aware implementation:
  - `source.ip` → `src_ip` → `srcip` fallback chain (and destination equivalent)
  - `source.port` → `src_port`, `destination.port` → `dst_port`
  - severity from `event.severity` → `alert.severity` → `"info"` default
  - detection_source from `rule.name` → `alert.signature` → `"malcolm_alert"`
  - hostname from `observer.hostname` → `agent.hostname` → `"malcolm"`
  - Drops (returns None) when src_ip is absent — incomplete alerts silently discarded
  - raw_event = `json.dumps(doc)[:8192]`
  - source_type = `"suricata_eve"`, event_type = `"alert"`

- Replaced `_normalize_syslog()` stub with full implementation:
  - Accepts dict (OpenSearch `_source`) or str (plain syslog line) via isinstance dispatch
  - hostname from `host.name` → `hostname` → `"ipfire"`
  - severity always `"info"`, detection_source always `"ipfire_syslog"`
  - syslog events never dropped for missing IPs
  - source_type = `"ipfire_syslog"`, event_type = `"syslog"`

- Set `_NORMALIZER_IMPLEMENTED = True` in `tests/unit/test_malcolm_normalizer.py`
- Fixed test field name references (`source_ip` → `src_ip`, `dest_ip` → `dst_ip`) to match NormalizedEvent model
- Fixed severity assertions (integer severity coerced to string `"3"`, not integer `3`)
- All 7 normalizer tests now PASSED (previously SKIPPED)
- 5 collector tests + 7 normalizer tests = 12 total PASSED
- Full unit suite: 862 passed, 6 skipped, 0 failures

## Task Commits

1. **Task 1: Implement _normalize_alert() and _normalize_syslog() + activate stubs** — `95499dd` (feat)

## Files Created/Modified

- `ingestion/jobs/malcolm_collector.py` — replaced two stub methods with full ECS-aware normalization implementations
- `tests/unit/test_malcolm_normalizer.py` — set `_NORMALIZER_IMPLEMENTED = True`; corrected field names and severity assertions; added dict-form syslog test

## Decisions Made

- `_normalize_syslog` accepts `str | dict` — the original test stub passed a raw syslog string, and supporting both forms is more robust for real-world use (plain syslog files vs OpenSearch structured documents)
- Integer severity values (e.g. `event.severity: 3`) coerced to string `"3"` via `str(severity).lower()` — NormalizedEvent.severity is `Optional[str]`; tests corrected to assert `event.severity == "3"` not `== 3`
- Test field corrections (`source_ip` → `src_ip`, `dest_ip` → `dst_ip`) applied as Rule 1 auto-fix — the stub tests referenced non-existent attribute names

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_malcolm_normalizer.py attribute names and severity type**
- **Found during:** Task 1 (analyzing tests before implementation)
- **Issue:** Test stubs used `event.source_ip` and `event.dest_ip` which do not exist on NormalizedEvent (canonical fields are `src_ip` and `dst_ip`). Also `assert event.severity == 3` expected integer but NormalizedEvent.severity is `Optional[str]`, so severity is stored as `"3"`.
- **Fix:** Corrected attribute references to `src_ip`/`dst_ip`; corrected severity assertions to `"3"`/`"2"`.
- **Files modified:** `tests/unit/test_malcolm_normalizer.py`
- **Commit:** `95499dd`

**2. [Rule 2 - Missing functionality] Added str input support to _normalize_syslog()**
- **Found during:** Task 1 (test_normalize_syslog_source_type passes a raw string)
- **Issue:** The plan specified `_normalize_syslog(doc: dict)` but the existing test stub calls `collector._normalize_syslog(raw_line)` where `raw_line` is a plain syslog string. Rejecting strings would fail a legitimate test use case.
- **Fix:** Added `isinstance(doc, str)` dispatch at the top of `_normalize_syslog()` — string input handled as a raw syslog line with no structured fields; dict input follows the ECS field mapping path.
- **Files modified:** `ingestion/jobs/malcolm_collector.py`
- **Commit:** `95499dd`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing functionality)
**Impact on plan:** Both fixes required to make 7 tests pass. No new dependencies introduced.

## Self-Check: PASSED

- `ingestion/jobs/malcolm_collector.py` — FOUND
- `tests/unit/test_malcolm_normalizer.py` — FOUND
- Commit `95499dd` — FOUND
- 7 normalizer tests PASSED, 12 collector+normalizer PASSED, 862 full suite PASSED
