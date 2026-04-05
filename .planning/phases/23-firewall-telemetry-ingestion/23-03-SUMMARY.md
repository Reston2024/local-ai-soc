---
phase: 23-firewall-telemetry-ingestion
plan: "03"
subsystem: ingestion
tags: [firewall, ipfire, suricata, syslog, eve-json, background-collector, heartbeat, sqlite-kv, settings]

# Dependency graph
requires:
  - phase: 23-01
    provides: IPFireSyslogParser.parse_line() — used by FirewallCollector for syslog ingestion
  - phase: 23-02
    provides: SuricataEveParser.parse_record() — used by FirewallCollector for EVE JSON ingestion
  - phase: 08
    provides: OsqueryCollector pattern — file-tail loop and lifespan wiring template
provides:
  - FirewallCollector background job (ingestion/jobs/firewall_collector.py) — file-tails IPFire syslog and Suricata EVE JSON, ingests via IngestionLoader
  - GET /api/firewall/status endpoint returning connected/degraded/offline state from heartbeat recency
  - FIREWALL_* settings fields in Settings class (all default-off)
  - Conditional lifespan wiring in backend/main.py for FirewallCollector + IngestionLoader
  - Heartbeat events normalised to NormalizedEvent(event_type='heartbeat') and stored in system_kv

affects: [23-04, phase-24, future-firewall-features]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - FirewallCollector file-tail loop with exponential backoff (capped at 300s)
    - Heartbeat emission pattern: system_kv set_kv + IngestionLoader.ingest_events([heartbeat_event])
    - Deferred try/except router mounting (firewall router follows established pattern)
    - IngestionLoader constructed inside lifespan and passed to collector (not shared with request handlers)

key-files:
  created:
    - ingestion/jobs/firewall_collector.py
    - backend/api/firewall.py
  modified:
    - backend/core/config.py
    - backend/main.py
    - tests/unit/test_firewall_collector.py

key-decisions:
  - "23-03: IngestionLoader constructed fresh in lifespan for FirewallCollector — not shared with request handlers to avoid store lifecycle conflicts"
  - "23-03: _ingest_new_data() returns True even when files are empty (heartbeat still emitted) — False only on unexpected exception"
  - "23-03: Firewall router mounted in deferred try/except block consistent with all other optional routers in main.py"
  - "23-03: FIREWALL_ENABLED=False default — app starts without firewall present, no file path validation at startup"

patterns-established:
  - "Background collector uses IngestionLoader.ingest_events() — NOT raw execute_write — for full dedup + Chroma + graph pipeline"
  - "Collector heartbeat: asyncio.to_thread(sqlite.set_kv, key, iso_str) then ingest NormalizedEvent(event_type='heartbeat')"
  - "Status endpoint reads heartbeat age from system_kv and maps to connected/degraded/offline thresholds from settings"

requirements-completed: [P23-T03, P23-T04]

# Metrics
duration: 10min
completed: 2026-04-05
---

# Phase 23 Plan 03: FirewallCollector and Status API Summary

**FirewallCollector background job tailing IPFire syslog and Suricata EVE JSON via IngestionLoader, with GET /api/firewall/status heartbeat-age status endpoint and conditional lifespan wiring**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-05T08:00:00Z
- **Completed:** 2026-04-05T08:08:05Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- FirewallCollector implemented with file-tail loop, exponential backoff (interval * 2^n capped at 300s), heartbeat emission to system_kv and IngestionLoader
- GET /api/firewall/status endpoint returns connected/degraded/offline derived from heartbeat recency stored in system_kv
- All FIREWALL_* settings fields added to Settings class with sensible defaults (FIREWALL_ENABLED=False)
- Conditional lifespan wiring in main.py: collector started only when FIREWALL_ENABLED=True, router always mounted via deferred try/except
- 5 pre-skipped unit tests activated and all passing; full suite 817 passed, 0 failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement FirewallCollector and Settings extension** - `ca5f62a` (feat)
2. **Task 2: Implement GET /api/firewall/status endpoint and wire into main.py** - `57763a6` (feat)
3. **Task 3: Activate test stubs and verify full suite** - `0e18114` (test)

## Files Created/Modified
- `ingestion/jobs/firewall_collector.py` - FirewallCollector class: file-tail, backoff, heartbeat, _read_new_lines, _ingest_new_data, _emit_heartbeat, run(), status()
- `backend/api/firewall.py` - GET /firewall/status endpoint reading system_kv heartbeat age
- `backend/core/config.py` - Added FIREWALL_ENABLED, FIREWALL_SYSLOG_PATH, FIREWALL_EVE_PATH, FIREWALL_SYSLOG_HOST, FIREWALL_SYSLOG_PORT, FIREWALL_HEARTBEAT_THRESHOLD_SECONDS, FIREWALL_OFFLINE_THRESHOLD_SECONDS, FIREWALL_POLL_INTERVAL, FIREWALL_CONSECUTIVE_FAILURE_LIMIT
- `backend/main.py` - Firewall collector lifespan block (8b) + router deferred mount + shutdown cancellation
- `tests/unit/test_firewall_collector.py` - Removed 5 @pytest.mark.skip decorators; pytestmark.skipif guard retained

## Decisions Made
- IngestionLoader constructed fresh inside the lifespan block to pass to FirewallCollector — avoids sharing a loader instance with per-request handlers and ensures proper store lifecycle
- `_ingest_new_data()` returns True even when both files are absent (heartbeat still emitted and stored in system_kv) — only returns False on unexpected exceptions
- Firewall router always mounted regardless of FIREWALL_ENABLED (consistent with telemetry router pattern); collector only started when enabled
- FIREWALL_ENABLED defaults to False so app starts without configuration when no IPFire host is present

## Deviations from Plan

None - plan executed exactly as written. The only minor interpretation was constructing an IngestionLoader inside the lifespan block, which the plan implied but did not specify the exact instantiation location.

## Issues Encountered

None - all implementations compiled and tested cleanly on first attempt.

## User Setup Required

To enable firewall collection, add to `.env`:
```
FIREWALL_ENABLED=True
FIREWALL_SYSLOG_PATH=/var/log/remote/ipfire/messages
FIREWALL_EVE_PATH=/var/log/remote/ipfire/suricata/eve.json
```

No code changes required. App starts successfully with all defaults (FIREWALL_ENABLED=False).

## Self-Check: PASSED

## Next Phase Readiness
- FirewallCollector fully implemented and tested; ready for Phase 23-04 (integration test + smoke-test script)
- GET /api/firewall/status provides live connectivity monitoring for dashboard integration
- Heartbeat pattern established for future collector health monitoring

---
*Phase: 23-firewall-telemetry-ingestion*
*Completed: 2026-04-05*
