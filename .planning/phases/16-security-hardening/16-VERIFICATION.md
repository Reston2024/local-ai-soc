---
phase: 16-security-hardening
verified: 2026-03-31T14:00:00Z
status: passed
score: 12/12 must-haves verified
re_verification: false
---

# Phase 16: Security Hardening Verification Report

**Phase Goal:** Close the 5 highest-priority security and operational gaps identified in the external security critique (B/83 grade). Deliver: (1) auth coherent end-to-end with frontend Bearer token propagation and secure-by-default posture, (2) upload route unified and Caddy limits confirmed, (3) security claims converted to demonstrable code controls (injection scrubbing tested, citation verification implemented, LLM audit logging tested), (4) frontend validation added to CI pipeline, (5) pyproject.toml dev/runtime deps separated.
**Verified:** 2026-03-31T14:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | AUTH_TOKEN defaults to 'changeme' so auth is ON in all environments | VERIFIED | `config.py` line 52: `AUTH_TOKEN: str = "changeme"` with comment confirming non-empty default |
| 2 | An empty string AUTH_TOKEN causes verify_token to return 401 for all requests | VERIFIED | `auth.py` lines 29-33: `configured = settings.AUTH_TOKEN.strip()` + guard raises 401 when empty |
| 3 | A request with the correct token passes; missing or wrong token returns 401 | VERIFIED | `test_auth.py` has 6 tests covering valid/missing/wrong/empty/changeme/whitespace — all assertions match |
| 4 | Every fetch() call in api.ts includes Authorization: Bearer header | VERIFIED | 10 fetch() calls found; 11 authHeaders() usages (definition + 10 call sites). All 10 fetch calls covered |
| 5 | Token reads from localStorage with fallback to VITE_API_TOKEN env | VERIFIED | `api.ts` lines 123-129: `getApiToken()` checks localStorage first, falls back to `import.meta.env.VITE_API_TOKEN ?? 'changeme'` |
| 6 | File upload posts to /api/ingest/file (not /api/ingest/upload) | VERIFIED | `api.ts` line 256: `fetch('/api/ingest/file', ...)` — no reference to old /api/ingest/upload |
| 7 | Caddy body_size_limit 100MB scoped to /api/ingest/file | VERIFIED | `Caddyfile` lines 38-48: `handle /api/ingest/file { request_body { max_size 100MB } }` appears before the generic `/api/*` 10MB block |
| 8 | dashboard/.env.example documents VITE_API_TOKEN=changeme | VERIFIED | File exists with content `VITE_API_TOKEN=changeme` |
| 9 | pytest/ruff/pytest-asyncio/pytest-cov are in [dependency-groups] dev, not main [dependencies] | VERIFIED | `pyproject.toml` lines 37-43: `[dependency-groups] dev = [...]` contains all four; main `[dependencies]` has none of them |
| 10 | httpx remains in main [dependencies] | VERIFIED | `pyproject.toml` line 17: `"httpx==0.28.1"` in main `[dependencies]` |
| 11 | CI runs npm ci + build + check in a parallel frontend job | VERIFIED | `ci.yml` lines 57-75: `frontend:` job with Node 20, `npm ci`, `npm run build`, `npm run check` — no `needs:` (parallel) |
| 12 | Security claims are demonstrable: citation verification + injection tests + audit logger test | VERIFIED | `verify_citations()` in query.py; `citation_verified` in both /query/ask JSON and /investigations/chat SSE done event; 11 injection scrubbing tests in TestInjectionScrubbing; audit logger handler test in test_investigation_chat.py |

**Score:** 12/12 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/core/config.py` | AUTH_TOKEN default = "changeme" | VERIFIED | Line 52: `AUTH_TOKEN: str = "changeme"` with accurate comment |
| `backend/core/auth.py` | Rejects empty-string token as misconfiguration | VERIFIED | Uses `.strip()` guard, raises HTTP 401 when empty/whitespace |
| `tests/unit/test_auth.py` | 6 tests: empty/whitespace/changeme/valid/missing/wrong | VERIFIED | All 6 tests present: `test_empty_token_raises_401`, `test_changeme_default_enforces_auth`, `test_whitespace_only_token_raises_401`, `test_valid_token_passes`, `test_missing_token_returns_401`, `test_wrong_token_returns_401` |
| `dashboard/src/lib/api.ts` | All fetch calls include Authorization header, upload uses /api/ingest/file | VERIFIED | `authHeaders()` function defined; spread into all 10 fetch call sites; upload route is `/api/ingest/file` |
| `dashboard/.env.example` | VITE_API_TOKEN=changeme | VERIFIED | File exists, 3 lines, correct content |
| `pyproject.toml` | [dependency-groups] dev section; no pytest/ruff in main deps | VERIFIED | `[dependency-groups]` section with pytest, pytest-asyncio, pytest-cov, ruff; absent from main `[dependencies]` |
| `.github/workflows/ci.yml` | `uv sync --group dev` in lint/test/dependency-audit; frontend job present | VERIFIED | All three Python jobs use `--group dev`; frontend job present with all required steps |
| `backend/api/query.py` | verify_citations() function; citation_verified in /query/ask response | VERIFIED | `_CITATION_RE`, `verify_citations()` defined at module level; `citation_ok` computed and returned as `"citation_verified": citation_ok` in JSONResponse |
| `backend/api/chat.py` | citation_verified in SSE done event; import re at module level | VERIFIED | `import re` at line 15 (module level); `from backend.api.query import verify_citations` imported; done event yields `{'done': True, 'citation_verified': citation_ok}` |
| `tests/unit/test_api_endpoints.py` | 4 citation unit tests | VERIFIED | Tests: `test_citation_verified_all_present`, `test_citation_verified_fake_id`, `test_citation_verified_no_citations`, `test_citation_verified_mixed` |
| `tests/unit/test_normalizer.py` | TestInjectionScrubbing class with command_line/domain/url tests | VERIFIED | Class has 11 tests total (7 pre-existing + 4 new NormalizedEvent-path tests): `test_command_line_injection_stripped`, `test_command_line_clean_preserved`, `test_domain_injection_stripped`, `test_url_injection_stripped` |
| `tests/unit/test_investigation_chat.py` | audit logger handler test | VERIFIED | `test_llm_audit_logger_has_handler` present with `_INITIALIZED` reset pattern and `tmp_path` fixture |
| `config/caddy/Caddyfile` | max_size 100MB scoped to /api/ingest/file | VERIFIED | `handle /api/ingest/file { request_body { max_size 100MB } }` appears before generic `/api/*` block |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/core/config.py` | `backend/core/auth.py` | `from backend.core.config import settings` | WIRED | Line 16 of auth.py: `from backend.core.config import settings`; `settings.AUTH_TOKEN.strip()` used at line 29 |
| `dashboard/src/lib/api.ts` | `backend/core/auth.py` | Authorization: Bearer header on every request | WIRED | `authHeaders()` spreads into every fetch() call; no unguarded fetch found |
| `config/caddy/Caddyfile` | `/api/ingest/file` | request_body max_size 100MB scoped to handle block | WIRED | 100MB limit is inside the `/api/ingest/file` handle block, not the generic `/api/*` block; Caddy first-match wins |
| `.github/workflows/ci.yml` frontend job | `dashboard/package.json` | npm run build, npm run check | WIRED | `"check": "svelte-check --tsconfig ./tsconfig.json"` confirmed in package.json; `"build"` script also present |
| `.github/workflows/ci.yml` | `pyproject.toml` | uv sync --group dev | WIRED | All three Python jobs use `uv sync --group dev`; no remaining `--extra dev` or bare `uv sync` in install steps |
| `backend/api/query.py` | `verify_citations()` | called after ollama.generate(), before JSONResponse | WIRED | Line 219: `citation_ok = verify_citations(answer, ids)` followed by JSONResponse including `"citation_verified": citation_ok` |
| `backend/api/chat.py` | `verify_citations()` | imported from query.py, called on full_tokens after stream | WIRED | `from backend.api.query import verify_citations` at module level; called at line 181 after stream completes |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| P16-SEC-01 | 16-01, 16-03 | Auth coherent end-to-end; secure-by-default | SATISFIED | AUTH_TOKEN="changeme" default; empty-token guard; Bearer headers on all frontend requests |
| P16-SEC-02 | 16-03 | Upload route unified; Caddy limits confirmed | SATISFIED | ingest.upload() posts to /api/ingest/file; Caddyfile has 100MB scoped to that handle |
| P16-SEC-03a | 16-05 | Injection scrubbing tested | SATISFIED | TestInjectionScrubbing has 11 tests including 4 NormalizedEvent-path tests covering command_line, domain, url |
| P16-SEC-03b | 16-05 | Citation verification implemented | SATISFIED | verify_citations() in query.py; citation_verified field in /query/ask and /investigations/chat SSE done event |
| P16-SEC-03c | 16-05 | LLM audit logging tested | SATISFIED | test_llm_audit_logger_has_handler in test_investigation_chat.py; verifies >=1 handler and propagate=False |
| P16-CI-04 | 16-04 | Frontend validation in CI pipeline | SATISFIED | frontend job in ci.yml: Node 20, npm ci, npm run build, npm run check; parallel execution (no needs:) |
| P16-DEP-05 | 16-02 | pyproject.toml dev/runtime deps separated | SATISFIED | [dependency-groups] dev contains pytest/pytest-asyncio/pytest-cov/ruff; httpx stays in main deps |

All 7 requirements satisfied. No orphaned requirements detected.

---

## Anti-Patterns Found

No anti-patterns detected in modified files. Scan covered:
- `backend/core/config.py` — clean
- `backend/core/auth.py` — clean
- `backend/api/query.py` — clean
- `backend/api/chat.py` — clean
- `dashboard/src/lib/api.ts` — clean
- `tests/unit/test_auth.py` — clean
- `tests/unit/test_normalizer.py` — clean
- `tests/unit/test_investigation_chat.py` — clean

---

## Human Verification Required

### 1. Frontend auth flow in browser

**Test:** Load the dashboard in a browser with no token set. Open DevTools Network tab. Trigger any API call (e.g., health check or events list).
**Expected:** Request includes `Authorization: Bearer changeme` header; backend returns data (not 401).
**Why human:** localStorage behavior and Vite env substitution cannot be verified statically.

### 2. File upload end-to-end with Caddy

**Test:** With Caddy running, upload a file >10MB and <100MB to the dashboard upload form.
**Expected:** Upload succeeds (not blocked by Caddy with 413); ingest job status returned.
**Why human:** Requires running Caddy + backend to verify the 100MB body limit is applied at the proxy layer.

### 3. SSE citation_verified field in browser

**Test:** Submit a question via the dashboard query interface. In DevTools, inspect the final SSE `done` event.
**Expected:** `{"done": true, "citation_verified": true}` (or false when LLM hallucinates an ID).
**Why human:** SSE stream inspection requires a live browser and running Ollama backend.

---

## Summary

Phase 16 goal is fully achieved. All 5 security/operational gaps identified in the external critique have been closed:

1. **Auth coherent end-to-end** — AUTH_TOKEN defaults to "changeme" (not ""), empty token guard rejects all requests, frontend sends Bearer headers on every fetch() call.

2. **Upload route unified and Caddy confirmed** — Frontend posts to /api/ingest/file; Caddyfile already had the 100MB limit scoped correctly to that handle block (no edit needed, verified by grep).

3. **Security claims demonstrated** — injection scrubbing has 11 unit tests; citation verification is implemented as a pure function and wired into both /query/ask and /investigations/chat SSE done events; audit logger smoke test confirms file handler is configured.

4. **Frontend in CI** — Parallel `frontend` job added with Node 20, npm ci, npm run build, npm run check; runs on every push/PR with no dependency on other jobs.

5. **Deps separated** — [dependency-groups] dev contains pytest/pytest-asyncio/pytest-cov/ruff; these are removed from main [dependencies]; httpx remains in main as a runtime dep for OllamaClient; all three Python CI jobs updated to `uv sync --group dev`; .gitignore deduplicated to single entry for .claude/settings.local.json.

Three items flagged for human verification are runtime behaviors (browser auth flow, Caddy file upload, SSE stream inspection) that cannot be confirmed programmatically.

---

_Verified: 2026-03-31T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
