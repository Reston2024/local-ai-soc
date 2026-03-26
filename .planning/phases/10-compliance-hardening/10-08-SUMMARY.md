---
phase: 10-compliance-hardening
plan: "08"
subsystem: infrastructure
tags: [docker, caddy, acl, hardening, compliance]
dependency_graph:
  requires: [10-05, 10-06]
  provides: [CADDY_ADMIN-hardened, data-acl-script, infra-compose-deprecated]
  affects: [docker-compose.yml, scripts/configure-acls.ps1, scripts/start.ps1]
tech_stack:
  added: []
  patterns: [icacls-acl-hardening, docker-image-pinning, powershell-preflight-check]
key_files:
  created: [scripts/configure-acls.ps1]
  modified: [docker-compose.yml, infra/docker-compose.yml, scripts/start.ps1]
decisions:
  - "Docker daemon was unavailable at execution time; Caddy digest pinning deferred via TODO comment (pin with: docker inspect caddy:2.9-alpine --format '{{index .RepoDigests 0}}')"
  - "ACL preflight in start.ps1 is non-blocking — emits Write-Warning only, never halts startup"
metrics:
  duration_minutes: 8
  tasks_completed: 2
  tasks_total: 2
  files_changed: 4
  completed_date: "2026-03-26"
requirements: [P10-T05, P10-T08]
---

# Phase 10 Plan 08: Docker/Caddy Hardening and Data ACL Script Summary

Hardened docker-compose.yml by fixing a critical CADDY_ADMIN binding exposure, added Caddy image digest pinning TODO, deprecated the Phase 2-3 infra/docker-compose.yml, created a Windows ACL hardening script for the data/ directory, and wired a non-blocking ACL preflight warning into start.ps1.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Harden docker-compose.yml — fix CADDY_ADMIN binding and pin image digest | 7adb6d3 | docker-compose.yml, infra/docker-compose.yml |
| 2 | Create scripts/configure-acls.ps1 and add ACL preflight to start.ps1 | a3cae86 | scripts/configure-acls.ps1, scripts/start.ps1 |

## What Was Done

### Task 1 — docker-compose.yml Hardening

**CADDY_ADMIN binding fix (CRITICAL audit finding):**
Changed `CADDY_ADMIN=0.0.0.0:2019` to `CADDY_ADMIN=127.0.0.1:2019`. The previous value exposed Caddy's management API to any Docker-reachable interface, allowing arbitrary Caddy config manipulation from within the Docker network.

**Caddy image digest pinning:**
Docker Desktop was not running at execution time, so the actual sha256 digest could not be fetched via `docker inspect`. Added a clearly-marked TODO comment above the image line directing whoever next runs Docker to pin it:
```
docker inspect caddy:2.9-alpine --format '{{index .RepoDigests 0}}'
```
The image tag remains `caddy:2.9-alpine` with `# UNPINNED` annotation until pinned.

**infra/docker-compose.yml deprecation:**
Prepended a four-line DEPRECATED header to `infra/docker-compose.yml` identifying it as Phase 2-3 only, pointing to the canonical root compose file, and noting ADR-019 schedules deletion in Phase 11.

### Task 2 — ACL Hardening Script and Preflight

**scripts/configure-acls.ps1 (new):**
PowerShell 5.1+ script implementing REQ-02 data directory access restriction:
- Requires Administrator elevation (exits with code 1 if not elevated)
- Resolves `data/` path relative to `$PSScriptRoot`
- Gracefully exits if `data/` does not yet exist
- `icacls` call: `/inheritance:d /grant:r "$DOMAIN\$USER:(OI)(CI)F" /remove "Everyone" /remove "Users" /T /Q`
- `-WhatIf` switch shows the command without executing it
- Exits 1 on `icacls` failure with clear error message

**scripts/start.ps1 ACL preflight (modified):**
Inserted non-blocking ACL preflight block after the startup banner but before the pre-flight checks section. Uses `Get-Acl` to check if `data/` grants Allow access to "Everyone". If so, emits two `Write-Warning` lines directing the user to run `configure-acls.ps1` as Administrator. Startup proceeds regardless.

## Deviations from Plan

### Docker Digest Unavailable (Rule 1 — handled per plan spec)

**Found during:** Task 1
**Issue:** Docker daemon (Docker Desktop) was not running during execution. `docker pull` and `docker inspect` both failed with `failed to connect to the docker API`.
**Fix:** Per plan instructions, added a TODO comment marking the image as UNPINNED rather than using the illustrative (invalid) fallback digest from the plan. The comment contains the exact command to resolve this when Docker is available.
**Files modified:** docker-compose.yml
**Commit:** 7adb6d3

## Success Criteria Verification

- [x] `docker-compose.yml`: `CADDY_ADMIN=127.0.0.1:2019`
- [x] `docker-compose.yml`: Caddy image has TODO comment for digest pinning (Docker unavailable at execution time)
- [x] `infra/docker-compose.yml`: DEPRECATED header present
- [x] `scripts/configure-acls.ps1`: exists with icacls, Admin elevation check, -WhatIf support
- [x] `scripts/start.ps1`: ACL preflight warning block present (non-blocking)

## Self-Check: PASSED

Files verified present:
- docker-compose.yml: CADDY_ADMIN=127.0.0.1:2019 confirmed
- scripts/configure-acls.ps1: 3 icacls occurrences (1 WhatIf display, 1 WhatIf display continued, 1 actual call)
- scripts/start.ps1: 2 matches for Get-Acl|ACL Preflight
- infra/docker-compose.yml: DEPRECATED header prepended

Commits verified: 7adb6d3, a3cae86
