---
phase: 1
plan: 3
subsystem: infrastructure
tags: [docker, caddy, https, powershell, scripts, gitignore]
dependency_graph:
  requires: []
  provides: [docker-compose, caddy-tls, start-stop-scripts, smoke-tests]
  affects: [all-services]
tech_stack:
  added: [caddy:2.9-alpine, docker-compose]
  patterns: [localhost-tls, reverse-proxy, sse-flush, pid-file-process-management]
key_files:
  created:
    - docker-compose.yml
    - config/caddy/Caddyfile
    - scripts/start.ps1
    - scripts/stop.ps1
    - scripts/status.ps1
    - scripts/smoke-test-phase1.ps1
    - CLAUDE.md
  modified:
    - .gitignore
decisions:
  - Caddy local_certs + tls internal for zero-config localhost HTTPS
  - SSE streaming uses flush_interval -1 on /api/query/* to prevent buffering
  - PID file (.backend.pid) pattern for tracking native uvicorn process
  - Dashboard build integrated into start.ps1 as optional pre-step
metrics:
  duration: ~10 minutes
  completed: 2026-03-15
  tasks_completed: 8
  files_created: 7
  files_modified: 1
---

# Phase 1 Plan 3: Docker/Caddy Infrastructure and Scripts Summary

**One-liner:** Caddy 2.9 Docker reverse proxy with localhost TLS, SSE-aware config, and PowerShell start/stop/status/smoke-test scripts for managing the native Windows service stack.

## What Was Built

Docker Compose configuration with Caddy as the sole container, a Caddyfile with localhost TLS termination and SSE streaming support, four PowerShell 7 management scripts, and a CLAUDE.md conventions reference.

### docker-compose.yml
Single-service compose file running `caddy:2.9-alpine`. Mounts the Caddyfile read-only, persists TLS data via named volumes (`ai-soc-brain-caddy-data`, `ai-soc-brain-caddy-config`), mounts `dashboard/dist` as static file root, and uses `host.docker.internal:host-gateway` for proxying to native FastAPI on port 8000.

### config/caddy/Caddyfile
- `local_certs` + `tls internal` for auto-generated, auto-trusted localhost certificates
- `/api/*` proxied to `host.docker.internal:8000` with upstream health checks
- `/api/query/*` handler with `flush_interval -1` to prevent SSE buffering
- `/health` proxied to backend
- `/*` serves Svelte SPA with `try_files {path} /index.html` fallback

### scripts/start.ps1
Pre-flight checks (venv, Docker, Ollama non-fatal), optional `npm run build`, starts uvicorn via `Start-Process` with PID tracking, verifies `/health` responds, then starts Caddy via `docker compose up -d --wait`. Supports `-DevMode` (reload) and `-SkipBuild` flags.

### scripts/stop.ps1
Reads `.backend.pid` to stop uvicorn; falls back to `Get-NetTCPConnection -LocalPort 8000` scan if PID file missing. Runs `docker compose down` for Caddy.

### scripts/status.ps1
HTTP health checks against FastAPI and Ollama endpoints, Docker container status via `docker ps`, Ollama model list via `ollama.exe list`, and PID file display.

### scripts/smoke-test-phase1.ps1
12 test cases covering: `/health` structure, `/api/events` pagination, `/api/detections`, `/api/graph/entities`, `/api/ingest/jobs`, `/api/export/events.csv`, `/docs`, `/openapi.json`, `POST /api/query/ask`, and `/api/detections/rules`. Scored output with pass/fail and investigation hints on failure.

### CLAUDE.md
Project conventions reference covering Python 3.12/uv setup, full directory layout, DuckDB write queue pattern, Chroma native client rule, Svelte 5 runes pattern, testing config, and git commit format.

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| a1dcf2f | feat(infra): docker-compose.yml for Caddy HTTPS reverse proxy |
| 9a5c088 | feat(infra): Caddyfile with localhost TLS, API proxy, SSE support |
| 84b6ec6 | feat(scripts): start.ps1 — starts backend + Caddy with pre-flight checks |
| 3f22f31 | feat(scripts): stop.ps1 — graceful service shutdown |
| b14bcb5 | feat(scripts): status.ps1 — service health dashboard |
| 1dccfdf | feat(scripts): smoke-test-phase1.ps1 — comprehensive API smoke tests |
| 7595a09 | chore: update .gitignore for new dirs and runtime files |
| a0f079c | docs: CLAUDE.md project conventions for AI assistants |

## Self-Check: PASSED

All 8 files verified present on disk. All 8 commits verified in git log.
