---
phase: 31-malcolm-full-telemetry
plan: "02"
subsystem: infra
tags: [fastapi, uvicorn, gzip, sha256, systemd, ecs, suricata, syslog, ubuntu]

# Dependency graph
requires: []
provides:
  - "EvidenceArchiver class: write-once daily gzip archives with SHA256 checksums at rotation"
  - "Ubuntu FastAPI normalization server: /normalized/index, /normalized/latest, /normalized/{day}"
  - "NormalizationWriter background task: EVE/syslog ECS field mapping to NDJSON"
  - "systemd service units: soc-archiver.service, soc-normalizer.service"
affects:
  - 31-malcolm-full-telemetry
  - 32-malcolm-integration
  - 36-zeek-full-telemetry

# Tech tracking
tech-stack:
  added:
    - fastapi>=0.110.0
    - uvicorn[standard]>=0.29.0
    - httpx>=0.27.0
  patterns:
    - "Write-once gzip archives in append mode (forensic integrity, no partial write risk)"
    - "SHA256 computed at rotation (midnight seal), never retroactively"
    - "FastAPI lifespan for background task lifecycle management"
    - "Line-offset tracking for append-only gzip polling"

key-files:
  created:
    - ubuntu/__init__.py
    - ubuntu/evidence_archiver.py
    - ubuntu/normalization_server.py
    - ubuntu/requirements.txt
    - ubuntu/systemd/soc-archiver.service
    - ubuntu/systemd/soc-normalizer.service
    - tests/unit/test_evidence_archiver.py
  modified: []

key-decisions:
  - "gzip.open() in append mode (ab) — open/write/close per line for forensic integrity, no persistent handle"
  - "_rotate(closing_date) renames active files to closing_date before checksumming — allows forced rotation in tests"
  - "NormalizationWriter uses in-memory line offsets — resets on restart, idempotent re-ingestion acceptable"
  - "No auth on normalization server — LAN-only service on 192.168.1.22:8080"
  - "EVE and syslog processed in same NormalizationWriter poll cycle — single background task"

patterns-established:
  - "TDD RED/GREEN: test stubs committed before implementation"
  - "ECS field mapping: source.ip/destination.ip/observer.hostname pattern for EVE docs"
  - "Protocol sub-fields (dns, tls, http, file, alert) pass through intact in normalized output"

requirements-completed:
  - P31-T07
  - P31-T08

# Metrics
duration: 4min
completed: "2026-04-09"
---

# Phase 31 Plan 02: Ubuntu Evidence Archiver and ECS Normalization Server Summary

**Write-once daily gzip evidence archiver with SHA256 chain-of-custody + FastAPI ECS normalization server polling EVE/syslog for desktop Malcolm collector**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-09T00:49:25Z
- **Completed:** 2026-04-09T00:53:35Z
- **Tasks:** 3 (Task 0 RED, Task 1 GREEN, Task 2 server + systemd)
- **Files modified:** 7 created

## Accomplishments
- EvidenceArchiver class: forensic write-once gzip archives, SHA256 at midnight rotation, file rename on close
- Ubuntu FastAPI normalization server with 3 /normalized routes streaming gzip NDJSON
- NormalizationWriter background task: EVE JSON + syslog ECS mapping, 5-second poll, lifespan-managed
- systemd service units for Ubuntu deployment (soc-archiver + soc-normalizer)
- All 3 EvidenceArchiver unit tests pass; 876 unit tests total pass, no regressions

## Task Commits

Each task was committed atomically:

1. **Task 0: Write failing EvidenceArchiver test stubs (RED)** - `9448026` (test)
2. **Task 1: EvidenceArchiver class implementation (GREEN)** - `b0cebfe` (feat)
3. **Task 2: Ubuntu normalization server + systemd units** - `6e835a4` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `ubuntu/__init__.py` - Package marker for ubuntu module
- `ubuntu/evidence_archiver.py` - EvidenceArchiver: write_syslog_line(), write_eve_line(), _rotate(), rotate_if_needed()
- `ubuntu/normalization_server.py` - FastAPI app, NormalizationWriter, ECS mappers, lifespan, 3 routes
- `ubuntu/requirements.txt` - fastapi, uvicorn[standard], httpx
- `ubuntu/systemd/soc-archiver.service` - systemd unit for evidence archiver
- `ubuntu/systemd/soc-normalizer.service` - systemd unit for normalization server
- `tests/unit/test_evidence_archiver.py` - 3 unit tests: write_gzip, sha256_written, daily_rotation

## Decisions Made
- `gzip.open()` in "ab" append mode with open/close per write: slower but forensically safe (no partial writes on process kill)
- `_rotate(closing_date)` renames currently-open files to `closing_date` before checksumming, enabling forced rotation in tests and correct labeling at true midnight boundary
- NormalizationWriter stores in-memory line offsets; resets on restart — idempotent re-ingestion is acceptable for this forensic-only pipeline
- `/normalized/latest` returns 404 (not empty stream) when no data exists today — desktop caller handles 404 gracefully

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _rotate() to rename active files to closing_date before checksumming**
- **Found during:** Task 1 (EvidenceArchiver implementation — GREEN phase)
- **Issue:** Initial implementation checksummed files at `closing_date` path, but files were written to `_current_date` (today). test_sha256_written and test_daily_rotation both failed because the paths didn't match.
- **Fix:** Updated `_rotate(closing_date)` to rename `_current_date` files to `closing_date` before computing digests. This also correctly handles the real-world midnight rotation case where the UTC date changes between write and rotate.
- **Files modified:** ubuntu/evidence_archiver.py
- **Verification:** All 3 unit tests pass
- **Committed in:** b0cebfe (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in rotation path logic)
**Impact on plan:** Fix was necessary for correct forensic labeling. No scope creep.

## Issues Encountered
- Initial `_rotate()` implementation looked up files by `closing_date` but files are written under `_current_date`. Required two fix iterations (first fixed sha256 test, second fixed daily_rotation test) before settling on file-rename approach.

## User Setup Required
None - no external service configuration required for desktop build. Ubuntu deployment requires manual `systemctl` steps documented in the service files and plan comments.

## Self-Check

Checked created files exist:
- `ubuntu/evidence_archiver.py` — FOUND
- `ubuntu/normalization_server.py` — FOUND
- `ubuntu/requirements.txt` — FOUND
- `ubuntu/systemd/soc-archiver.service` — FOUND
- `ubuntu/systemd/soc-normalizer.service` — FOUND
- `tests/unit/test_evidence_archiver.py` — FOUND

Checked commits exist:
- 9448026 — test(31-02): add failing EvidenceArchiver test stubs (RED phase)
- b0cebfe — feat(31-02): implement EvidenceArchiver class (GREEN phase)
- 6e835a4 — feat(31-02): Ubuntu ECS normalization server + systemd units

## Self-Check: PASSED

## Next Phase Readiness
- ubuntu/ module ready for desktop Malcolm collector to poll GET /normalized/latest
- EvidenceArchiver ready for syslog/EVE byte streams from IPFire + Suricata
- systemd units ready for deployment on 192.168.1.22 after ubuntu Python venv setup
- Plan 31-03 (Malcolm collector integration) can reference ubuntu.normalization_server endpoints

---
*Phase: 31-malcolm-full-telemetry*
*Completed: 2026-04-09*
