---
phase: 12
plan: 02
subsystem: caddy-proxy
tags: [security, request-size, caddy, proxy]
dependency_graph:
  requires: [12-01]
  provides: [caddy-body-size-limits]
  affects: [config/caddy/Caddyfile]
tech_stack:
  added: []
  patterns: [caddy-request_body-directive, proxy-layer-enforcement]
key_files:
  created: []
  modified:
    - config/caddy/Caddyfile
decisions:
  - "Caddy-only approach: proxy-layer enforcement blocks oversized requests before Python allocates memory — FastAPI middleware would fire after body is already buffered, defeating the purpose"
  - "/api/ingest/file handler added as specific match before /api/* (Caddy first-match-wins) with 100MB limit; /api/* gets 10MB fallback"
  - "SSE /api/query/* handler intentionally excluded from request_body limits — query payloads are small JSON and the streaming response requires flush_interval -1 uninterrupted"
metrics:
  duration: "56 seconds"
  completed_date: "2026-03-27"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 12 Plan 02: Caddy Request Body Size Limits Summary

Two-tier Caddy `request_body` size limits blocking oversized evidence uploads at the proxy layer before FastAPI allocates memory — 100MB for file uploads, 10MB for all other API requests.

## Objective

Add `request_body` max_size directives to Caddyfile to guard against accidental multi-GB uploads exhausting FastAPI process memory. Caddy returns HTTP 413 for oversized requests without ever proxying them to Python.

## Tasks Completed

| Task | Name | Commit | Files Modified |
|------|------|--------|----------------|
| 1 | Add request_body size limits to Caddyfile | 825536c | config/caddy/Caddyfile |

## What Was Built

Updated `config/caddy/Caddyfile` with:

1. **New `/api/ingest/file` handler** (inserted between `/api/query/*` and `/api/*`):
   - `request_body { max_size 100MB }` — allows large evidence file uploads
   - Same reverse_proxy config as `/api/*` but without health check directives
   - Positioned before `/api/*` to satisfy Caddy's first-match-wins routing

2. **Updated `/api/*` handler**:
   - Added `request_body { max_size 10MB }` before the `reverse_proxy` block
   - All existing config retained (headers, health_uri, health_interval, health_timeout)

3. **Unchanged `/api/query/*` handler**:
   - No `request_body` directive added — query JSON payloads are small
   - `flush_interval -1` retained for SSE streaming

Caddy binary validation (`caddy validate`) confirms the configuration is syntactically valid.

## Verification

```
grep -c "request_body" config/caddy/Caddyfile  => 3 (2 directive blocks + 1 comment)
grep -c "^        request_body" config/caddy/Caddyfile  => 2 (exactly 2 directive blocks)
caddy validate  => "Valid configuration"
```

Handler order in file:
- Line 26: `handle /api/query/*` — `flush_interval -1`, no request_body
- Line 38: `handle /api/ingest/file` — `max_size 100MB`
- Line 52: `handle /api/*` — `max_size 10MB`

## Decisions Made

1. **Caddy-only, no FastAPI middleware**: Research (12-RESEARCH.md) confirmed that proxy-layer enforcement is superior — Caddy rejects the request before streaming the body to Python. A FastAPI `ContentLengthLimit` middleware would fire after the body is already buffered in memory, which is the opposite of the desired behavior.

2. **Two-tier limits**: 100MB for `/api/ingest/file` (evidence files), 10MB for all other API calls. This allows realistic log/EVTX uploads while blocking accidental oversized payloads on query/detect/graph endpoints.

3. **SSE handler excluded**: `/api/query/*` does not need a body size limit (query payloads are tiny JSON) and adding one would risk interfering with the `flush_interval -1` streaming behavior.

## Deviations from Plan

None — plan executed exactly as written. `caddy validate` passed with the local Caddy binary (v2.11.1). Docker was not running, so container validation was skipped (per plan's documented fallback).

## Self-Check: PASSED

- `config/caddy/Caddyfile` exists and contains 2 request_body directive blocks
- Commit 825536c exists in git log
- Handler order: `/api/query/*` → `/api/ingest/file` → `/api/*` → `/health` → `/app/*` → `/`
- `caddy validate` returned "Valid configuration"
