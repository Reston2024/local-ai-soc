# DEPRECATION.md — AI-SOC-Brain

This file tracks deprecated API paths, configuration options, and behaviours
that are scheduled for removal. All entries include a removal date and a
migration path.

---

## Active Deprecations

### 1. Legacy admin auth path (`AUTH_TOKEN` direct match)

| Field | Value |
|-------|-------|
| **Location** | `backend/core/auth.py` — `verify_token()`, legacy fallback block |
| **Config** | `AUTH_TOKEN` env var used directly as a shared secret |
| **Removal date** | **2026-07-01** |
| **Tracking** | S-02 |

**What it is:**
The `verify_token()` dependency falls back to an `hmac.compare_digest` check
against `AUTH_TOKEN` when no named operator record matches the token prefix.
A successful match returns `OperatorContext(operator_id='legacy-admin')` with
full admin role. TOTP enforcement is optional (conditioned on `LEGACY_TOTP_SECRET`).

**Why it is deprecated:**
The per-operator table (Phase 19) provides bcrypt-hashed, prefix-indexed API
keys with per-operator role assignment and audit trails. The raw `AUTH_TOKEN`
fallback bypasses all of that. It exists only to avoid breaking existing local
`.env` setups that pre-date Phase 19.

**Migration:**
1. Create a named operator via `POST /api/operators` (admin role).
2. Store the returned API key in your client configuration.
3. Remove `AUTH_TOKEN` from `.env` (or set it to a random value — it will
   no longer be used for authentication once all clients migrate).
4. Optionally remove `LEGACY_TOTP_SECRET` from `.env`.

---

### 2. Legacy ingest upload endpoint (`POST /api/ingest/upload`)

| Field | Value |
|-------|-------|
| **Location** | `backend/api/ingest.py` — `upload_file_legacy()` |
| **Endpoint** | `POST /api/ingest/upload` |
| **Removal date** | **2026-07-01** |

**What it is:**
A thin wrapper around `POST /api/ingest/file` preserved for clients that
targeted the old `/ingest/upload` path before Phase 28 renamed it.

**Migration:**
Switch all callers to `POST /api/ingest/file`. The request and response
shapes are identical.

---

### 3. Legacy admin operator bootstrap (`bootstrap_admin_if_empty`)

| Field | Value |
|-------|-------|
| **Location** | `backend/stores/sqlite_store.py` — `bootstrap_admin_if_empty()` |
| **Called from** | `backend/main.py` startup |
| **Removal date** | **2026-07-01** |

**What it is:**
At startup, if the `operators` table is empty, a synthetic `admin` operator
row is seeded using `AUTH_TOKEN` as the raw key. This is a one-time migration
helper that predates the operator-table auth path.

**Migration:**
Create at least one operator via `POST /api/operators` before removing
`AUTH_TOKEN` from `.env`. Once a named operator exists, `bootstrap_admin_if_empty`
is a no-op and can be removed safely on 2026-07-01.

---

## Removed (historical)

| Item | Removed | Notes |
|------|---------|-------|
| `backend/src/` package alias | Phase 11 (2026-03-26) | Replaced by `backend/` direct imports |
| `STATE.md` | Phase 35 (2026-04-10) | Superseded by `STATUS.md` |
| `mxbai-embed-large` embedding model | Phase 54 (2026-04-17) | Replaced by `bge-m3` via Ollama |
