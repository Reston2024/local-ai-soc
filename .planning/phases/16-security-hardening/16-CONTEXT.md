# Phase 16: Security Hardening — Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Source:** External security critique (B/83 grade) — PRD Express Path

<domain>
## Phase Boundary

Close the 5 highest-priority security and operational gaps identified in the external security critique. This phase makes the project's security posture match its stated claims, hardens the full authentication stack end-to-end, unifies the upload route surface, and adds frontend validation to CI. No new features are introduced — this is hardening only.

**Not in scope:** Threat Hunting (Phase 17), SOAR (Phase 18), Reporting (Phase 19).

</domain>

<decisions>
## Implementation Decisions

### 1. End-to-End Auth (HIGHEST PRIORITY)

**Critique finding:** `AUTH_TOKEN` defaults to empty string → all requests pass when unset. Frontend `api.ts` issues fetch calls without `Authorization: Bearer` headers. Caddy does not inject headers. When `AUTH_TOKEN` is set, the dashboard silently breaks.

**Locked decisions:**
- `AUTH_TOKEN` MUST have a non-empty default (e.g. `"changeme"`) so auth is ON by default in all environments
- `backend/core/auth.py` must reject empty-string token as if no token is configured (i.e. treat `AUTH_TOKEN=""` as misconfiguration that forces 401 on all `/api/*` routes)
- `dashboard/src/lib/api.ts` MUST attach `Authorization: Bearer <token>` on every fetch call including SSE endpoints
- The token value must be read from a browser-accessible source (env var via Vite `VITE_API_TOKEN`, localStorage key `api_token`, or a `/api/config` endpoint — choose one)
- Chosen mechanism: read from `localStorage.getItem('api_token')` with fallback to Vite env `VITE_API_TOKEN` (default `"changeme"` in `.env`) — this allows override without rebuild
- All API calls in `api.ts` (fetch, SSE EventSource) must include the header
- Add a smoke test: with `AUTH_TOKEN=testtoken`, any unauthenticated call must return 401; same call with correct header must succeed

### 2. Upload Route Unification

**Critique finding:** Frontend uploads to `/api/ingest/upload`; backend has `/ingest/upload` as a legacy alias to `/ingest/file`; Caddy gives 100 MB body limit only to `/api/ingest/file`, not `/api/ingest/upload`. Result: large uploads via the frontend may be capped at the 10 MB generic limit.

**Locked decisions:**
- Pick ONE canonical route: `/api/ingest/file` (already has the Caddy 100 MB exception)
- Update `dashboard/src/lib/api.ts` `ingestFile()` to POST to `/api/ingest/file`
- Remove or keep (but do not advertise) the `/api/ingest/upload` alias — it can remain for backward compat but must be documented as deprecated
- Verify Caddy `Caddyfile` has a single `body_size_limit 100MB` block scoped to `/api/ingest/file` (not `/api/ingest/upload`)
- Add a test that verifies the upload route alignment

### 3. Convert Security Claims to Demonstrable Controls

**Critique finding:** Threat model claims prompt-injection scrubbing, citation verification for every LLM response, and LLM I/O audit logging. Code review found: basic system prompt asking model to cite event IDs; no citation verification layer; route logs metadata (lengths) not full LLM inputs/outputs.

**Locked decisions:**

#### 3a. Prompt Injection Scrubbing
- `ingestion/normalizer.py` must have a documented sanitization step that strips known injection patterns (`ignore previous instructions`, `you are now`, etc.) from user-controlled free-text fields before they are embedded or passed to LLM
- Must be tested: inject pattern in `command_line` → verify it is scrubbed from the embedded text

#### 3b. Citation Verification
- After each LLM response in `/api/query` and `/api/investigations/{id}/chat`, verify that event IDs cited in the response actually exist in the retrieved context
- If a cited ID is not in the context, either strip the citation or flag it as unverified
- Add a `citation_verified: bool` field to the response payload
- Add a unit test: LLM response cites a fake event ID → verifier flags it

#### 3c. LLM I/O Audit Logging
- Every call to Ollama (prompt + response) must be logged at DEBUG level with: timestamp, endpoint, model, prompt_length, response_length, and the first 500 chars of prompt and response
- Log to the existing structured logger (do NOT log full text at INFO to avoid log bloat)
- Log file: `logs/llm_audit.log` (separate file handler, not stdout)
- Add a test verifying the audit log file receives entries on LLM calls

### 4. Frontend Validation in CI

**Critique finding:** CI runs ruff, pytest, pip-audit, gitleaks — but NO frontend build/type-check. Given the auth gap found, this matters.

**Locked decisions:**
- Add a `frontend` job to `.github/workflows/ci.yml` that runs: `npm ci`, `npm run build`, `npm run check` (svelte-check)
- Job runs on `ubuntu-latest`, uses Node 18+
- Job must fail the PR if any of the three steps fail
- Add `check` script to `dashboard/package.json` if not already present (`"check": "svelte-check --tsconfig ./tsconfig.json"`)
- Frontend job runs in parallel with the existing `test` job (no dependency between them)

### 5. Dependency Hygiene (pyproject.toml)

**Critique finding:** `pyproject.toml` places test/lint tools (`pytest`, `pytest-asyncio`, `ruff`) in main dependencies rather than a dev-only group. `.gitignore` has duplicate entries.

**Locked decisions:**
- Move `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, and any other dev-only packages to `[dependency-groups]` or `[project.optional-dependencies]` dev group
- **`httpx` stays in main `[dependencies]`** — it is a runtime dependency for `OllamaClient` in `backend/services/ollama_client.py`; it is NOT test-only
- Verify `uv sync` still works and `uv run pytest` still works after the move
- De-duplicate `.gitignore` entries (minor, can be in same commit)
- Do NOT break CI — update CI commands if needed (e.g. `uv sync --group dev`)

### Claude's Discretion

- Exact approach for reading the API token in the browser (localStorage + Vite env is the locked decision; the UI for setting it is Claude's call — a simple settings modal or pre-filled from env is fine)
- Whether to add a `/api/config` endpoint that returns the expected token for dev convenience (acceptable if it's clearly dev-only and gated)
- Log rotation config for `logs/llm_audit.log`
- Whether citation verification is synchronous in the response or async (synchronous preferred for correctness)
- Order of the plan waves within the phase

</decisions>

<specifics>
## Specific References

**Files known to need changes:**
- `backend/core/auth.py` — reject empty AUTH_TOKEN, enforce non-empty default
- `backend/core/config.py` — change `AUTH_TOKEN` default to `"changeme"`
- `dashboard/src/lib/api.ts` — add Bearer header to all fetch + SSE calls
- `dashboard/.env` / `dashboard/.env.example` — add `VITE_API_TOKEN=changeme`
- `config/caddy/Caddyfile` — verify 100MB limit on `/api/ingest/file` only
- `ingestion/normalizer.py` — add injection scrubbing
- `backend/api/query.py` or `backend/services/ollama.py` — citation verification + LLM I/O logging
- `backend/api/chat.py` — same LLM I/O logging
- `.github/workflows/ci.yml` — add frontend job
- `dashboard/package.json` — add/verify `check` script
- `pyproject.toml` — move dev deps to dev group
- `.gitignore` — deduplicate

**External critique scorecard (target):**
- Security engineering: B- → B+ (auth coherent, controls demonstrated)
- Frontend engineering: B → A- (CI coverage, auth working)
- DevOps/CI: B → B+ (frontend in CI)
- Overall: B (83) → B+ (87+)

**Critique grades by domain (current / target):**
- Security: B- → B+
- Frontend: B → A-
- DevOps: B → B+

</specifics>

<deferred>
## Deferred Ideas

- Full OWASP ASVS L2 compliance audit (too broad for one phase)
- NIST AI RMF formal documentation (doc-only work, not code)
- Velociraptor, multi-host fleet, remote access (out of scope per REQUIREMENTS.md)
- Token rotation or JWT (shared secret is sufficient for local single-analyst use)
- Rate limiting changes (already implemented in Phase 12)
- Citation verification for non-LLM routes (only LLM response routes need this)

</deferred>

---

*Phase: 16-security-hardening*
*Context gathered: 2026-03-31 via external security critique (B/83 grade → PRD Express Path)*
