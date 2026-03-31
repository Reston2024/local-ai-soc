---
phase: 16-security-hardening
plan: 03
subsystem: auth
tags: [typescript, svelte, fetch, bearer-token, vite, caddy]

# Dependency graph
requires:
  - phase: 16-01
    provides: Backend Bearer token enforcement (AUTH_TOKEN check on every route)
provides:
  - All frontend fetch() calls include Authorization: Bearer header
  - Upload route corrected to /api/ingest/file matching Caddy 100MB exception
  - dashboard/.env.example documenting VITE_API_TOKEN
  - src/vite-env.d.ts typing import.meta.env for TypeScript
affects: [16-security-hardening, dashboard, api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "getApiToken() reads localStorage 'api_token' with VITE_API_TOKEN env fallback"
    - "authHeaders() single source of truth for Authorization header across all fetch calls"
    - "Central request<T>() helper merges authHeaders() so all JSON API calls are covered"
    - "Direct fetch() calls (SSE, upload, Phase 4 graph) each explicitly spread authHeaders()"

key-files:
  created:
    - dashboard/.env.example
    - dashboard/src/vite-env.d.ts
  modified:
    - dashboard/src/lib/api.ts

key-decisions:
  - "Token source: localStorage 'api_token' with VITE_API_TOKEN env fallback (default 'changeme') — matches 16-CONTEXT.md locked decision"
  - "Do not set Content-Type on FormData upload — browser sets multipart boundary automatically"
  - "Caddyfile already correctly scoped: 100MB limit on /api/ingest/file, no edit needed"
  - "vite-env.d.ts created to fix import.meta.env TypeScript error introduced by getApiToken()"

patterns-established:
  - "authHeaders(): all new fetch() calls in api.ts must spread authHeaders() in headers"
  - "Upload route canonical path is /api/ingest/file — do not use /api/ingest/upload"

requirements-completed: [P16-SEC-01, P16-SEC-02]

# Metrics
duration: 3min
completed: 2026-03-31
---

# Phase 16 Plan 03: Frontend Bearer Token Wiring Summary

**Authorization: Bearer header injected into every fetch() call in api.ts via getApiToken()/authHeaders() helpers, upload route corrected to /api/ingest/file**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-31T13:15:45Z
- **Completed:** 2026-03-31T13:18:09Z
- **Tasks:** 1/1
- **Files modified:** 3 (api.ts, .env.example, vite-env.d.ts)

## Accomplishments
- Added `getApiToken()` reading localStorage `api_token` with `VITE_API_TOKEN` env fallback
- Added `authHeaders()` helper returning `{ Authorization: Bearer <token> }` as single source of truth
- Injected `authHeaders()` into central `request<T>()` helper covering all JSON API calls
- Patched all 8 direct `fetch()` calls (SSE streams, file upload, Phase 4 graph, Phase 9 intel functions) with auth headers
- Fixed upload route from `/api/ingest/upload` to `/api/ingest/file` to match Caddy 100MB exception
- Confirmed Caddyfile already correctly scopes `max_size 100MB` to `handle /api/ingest/file` — no edit needed
- Created `dashboard/.env.example` documenting `VITE_API_TOKEN=changeme`

## Task Commits

1. **Task 1: Add token helper and inject Bearer header into all fetch calls** - `32920fc` (feat)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified
- `dashboard/src/lib/api.ts` - getApiToken(), authHeaders(), all fetch() calls updated
- `dashboard/.env.example` - Vite env documentation for VITE_API_TOKEN
- `dashboard/src/vite-env.d.ts` - TypeScript ambient type for import.meta.env.VITE_API_TOKEN

## Decisions Made
- Token source is localStorage 'api_token' with VITE_API_TOKEN env fallback matching plan locked decisions
- FormData upload does not set Content-Type — browser sets multipart boundary automatically
- Caddyfile was already correct, verified by grep (no file edit required for P16-SEC-02)
- Created vite-env.d.ts as auto-fix for new TypeScript error from import.meta.env usage

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added vite-env.d.ts to type import.meta.env**
- **Found during:** Task 1 (verify step — npm run check)
- **Issue:** `import.meta.env.VITE_API_TOKEN` in `getApiToken()` caused TypeScript error "Property 'env' does not exist on type 'ImportMeta'" because the project had no `vite-env.d.ts` ambient declaration file
- **Fix:** Created `dashboard/src/vite-env.d.ts` with `/// <reference types="vite/client" />` and explicit `ImportMetaEnv` / `ImportMeta` interfaces
- **Files modified:** dashboard/src/vite-env.d.ts (created)
- **Verification:** npm run check error count returned to 9 pre-existing (import.meta.env error eliminated)
- **Committed in:** 32920fc (part of Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug)
**Impact on plan:** Fix required to satisfy TypeScript clean check. No scope creep; vite-env.d.ts is standard Vite project infrastructure.

## Issues Encountered
- Pre-existing 9 TypeScript errors in GraphView.svelte and InvestigationPanel.svelte (out of scope — not introduced by this plan, not fixed per scope boundary rule)

## User Setup Required
None - no external service configuration required. Copy `.env.example` to `.env.local` and set `VITE_API_TOKEN` to match `AUTH_TOKEN` in backend `.env`.

## Next Phase Readiness
- Frontend now correctly authenticates all API requests
- Backend (16-01) enforces auth; frontend (16-03) sends auth — the loop is closed
- Ready for 16-04 and remaining security hardening plans

---
*Phase: 16-security-hardening*
*Completed: 2026-03-31*
