# Phase 19: Identity & RBAC — Research

**Researched:** 2026-03-31
**Domain:** Authentication / RBAC / TOTP MFA / Audit Attribution
**Confidence:** HIGH (verified against official docs and project source)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P19-T01 | Operator data model — SQLite operators table, bcrypt-hashed API keys, admin bootstrap from env | SQLite DDL migration pattern confirmed from sqlite_store.py; bcrypt via passlib[bcrypt]; secrets.token_urlsafe for key gen |
| P19-T02 | Multi-operator auth — verify_token looks up operator by bearer token; injects operator_id + role into request.state; stamps audit log entries with operator attribution | FastAPI request.state injection pattern; existing verify_token async def signature; llm_audit logger accepts extra dict |
| P19-T03 | RBAC middleware — require_role() FastAPI dependency; admin/analyst roles; 403 on violation | FastAPI Depends injection; 401 vs 403 distinction (unauthenticated vs unauthorized) |
| P19-T04 | Optional TOTP MFA — pyotp TOTP per operator; X-TOTP-Code header verification; QR provisioning endpoint | pyotp.TOTP API; otpauth:// URI format; replay prevention via seen-codes set |
| P19-T05 | Operator management API + SettingsView tab — CRUD (admin only); key rotation; Svelte Operators tab | ReportsView tab pattern; api.ts namespace pattern; Svelte 5 runes |
</phase_requirements>

---

## Summary

Phase 19 upgrades the single shared bearer token in `backend/core/auth.py` to named-operator identity with bcrypt-hashed API keys, role-based access control, optional per-operator TOTP MFA, and audit log attribution. All state lives in SQLite (`graph.db`) alongside existing tables using the established `self._conn / _DDL` pattern.

The existing `verify_token` function (a plain `async def`) becomes a lookup function: it hashes the presented token, queries the `operators` table, attaches `operator_id` and `role` to `request.state`, and enforces MFA if enabled. A companion `require_role()` dependency gates admin-only endpoints. Backward compatibility is preserved: `settings.AUTH_TOKEN` remains the single legacy token; if the `operators` table is empty, a synthetic `admin` operator record is constructed from the env var so existing single-token deployments continue to work with zero migration friction.

The Svelte 5 SettingsView Operators tab follows the exact tab-switching pattern from `ReportsView.svelte` (`$state<'operators' | '...'>`) and list/create/delete CRUD via a new `api.settings.operators` namespace in `api.ts`.

**Primary recommendation:** Use `passlib[bcrypt]` (not the bare `bcrypt` package) for all hashing — it provides a stable timing-safe `verify` method, cost-factor control, and is the de-facto FastAPI ecosystem standard. Use `pyotp` 2.x for TOTP; use `qrcode[pil]` for QR provisioning. Both are small, offline-first, and widely used in air-gapped contexts.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| passlib[bcrypt] | >=1.7.4 | bcrypt hash + verify for API keys | Timing-safe `.verify()`, wraps C bcrypt; FastAPI official docs use it; battle-tested |
| pyotp | >=2.9 | TOTP secret gen, code generation, verification | Pure Python, no cloud, RFC 6238 compliant, used in Django/Flask auth add-ons |
| qrcode[pil] | >=7.4 | Generate QR PNG for otpauth:// provisioning URI | Standard; `pil` extra adds PNG render without X11 |
| secrets (stdlib) | Python 3.12 | `secrets.token_urlsafe(32)` for API key generation | CSPRNG, stdlib, no dependency |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hmac (stdlib) | Python 3.12 | `hmac.compare_digest()` for constant-time string comparison | Use when not going through passlib (e.g. legacy token comparison) |
| io (stdlib) | Python 3.12 | `BytesIO` buffer for QR PNG response | Avoid temp files on Windows |
| base64 (stdlib) | Python 3.12 | Encode QR PNG for JSON transport | API returns base64 data URI |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| passlib[bcrypt] | bare `bcrypt` package | bcrypt package has no `verify()` helper; passlib is the ergonomic wrapper; use passlib |
| pyotp | python-otp | pyotp is more widely maintained with active releases; stick with pyotp |
| SQLite (existing) | Separate auth DB | Adds operational complexity; SQLite already open; use existing graph.db via new table |

**Installation:**
```bash
uv add "passlib[bcrypt]>=1.7.4" "pyotp>=2.9" "qrcode[pil]>=7.4"
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── core/
│   ├── auth.py          # MODIFIED: verify_token → multi-operator lookup + state injection
│   ├── rbac.py          # NEW: require_role() dependency, OperatorContext dataclass
│   └── config.py        # UNCHANGED: AUTH_TOKEN still read for legacy bootstrap
├── stores/
│   └── sqlite_store.py  # MODIFIED: operators table DDL + ALTER TABLE migration + operator CRUD methods
├── api/
│   └── operators.py     # NEW: CRUD endpoints (admin only) + QR provisioning
└── models/
    └── operator.py      # NEW: Pydantic models (OperatorCreate, OperatorRead, OperatorRotate)
dashboard/src/
├── views/
│   └── SettingsView.svelte  # NEW: tab with Operators sub-tab
└── lib/
    └── api.ts               # MODIFIED: add api.settings.operators namespace
```

### Pattern 1: bcrypt API Key Hash + Verify

**What:** Raw API key is generated with `secrets.token_urlsafe(32)`, shown to user once, and stored only as a bcrypt hash in `operators.hashed_key`.

**When to use:** On operator creation and rotation. On every request, hash the presented bearer token and call `passlib` verify.

```python
# Source: passlib docs — https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt.html
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_api_key(raw_key: str) -> str:
    return _pwd_context.hash(raw_key)

def verify_api_key(raw_key: str, hashed: str) -> bool:
    # timing-safe; returns False rather than raising on mismatch
    return _pwd_context.verify(raw_key, hashed)
```

**Cost factor:** passlib default bcrypt cost=12. For API keys (not interactive password logins) this is appropriate — 12 rounds is ~0.3 s on a modern CPU, which is acceptable for per-request auth with connection reuse. Do NOT use cost=4 (too fast, offline brute-force risk).

**Important:** bcrypt truncates input at 72 bytes. `secrets.token_urlsafe(32)` generates ~43 chars (well within limit). Do not accept user-chosen keys longer than 72 bytes.

### Pattern 2: FastAPI request.state Operator Injection

**What:** `verify_token` attaches an `OperatorContext` to `request.state.operator` so route handlers can read operator identity without an extra DB lookup.

**When to use:** Every authenticated request. The context is read by audit logging and RBAC checks.

```python
# Source: FastAPI docs — https://fastapi.tiangolo.com/advanced/using-request-directly/
from dataclasses import dataclass
from fastapi import Request, Security, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

@dataclass
class OperatorContext:
    operator_id: str
    username: str
    role: str          # "admin" | "analyst"
    totp_verified: bool

_bearer = HTTPBearer(auto_error=False)

async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    token: str | None = Query(default=None),
) -> OperatorContext:
    raw = credentials.credentials if credentials else token
    if not raw:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 1. Try operator table lookup
    ctx = await _lookup_operator(request, raw)
    if ctx is None:
        # 2. Legacy fallback: compare to AUTH_TOKEN
        ctx = await _legacy_fallback(request, raw)
    if ctx is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 3. TOTP enforcement (if operator has MFA enabled)
    if ctx requires_totp and not await _verify_totp(request, ctx):
        raise HTTPException(status_code=401, detail="TOTP required")

    request.state.operator = ctx
    return ctx
```

**Key rule:** `verify_token` returns `OperatorContext` (not `None`) so routes can annotate with `Annotated[OperatorContext, Security(verify_token)]`.

### Pattern 3: RBAC Dependency

**What:** `require_role("admin")` returns a FastAPI dependency that checks `request.state.operator.role`.

**401 vs 403 distinction:**
- 401 = unauthenticated (no valid token at all)
- 403 = authenticated but insufficient role (token valid, role wrong)

```python
# Source: FastAPI docs — https://fastapi.tiangolo.com/tutorial/security/
from fastapi import Depends, HTTPException, Request

def require_role(*allowed_roles: str):
    async def _dep(request: Request, ctx: OperatorContext = Security(verify_token)):
        if ctx.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden: insufficient role")
        return ctx
    return _dep

# Usage in route:
@router.post("/api/operators", dependencies=[Depends(require_role("admin"))])
async def create_operator(...): ...
```

### Pattern 4: pyotp TOTP Implementation

**What:** Per-operator TOTP secret (base32, 32 bytes). QR code URI in `otpauth://` format. Verify with 1-step window tolerance (±30 s). Replay prevention via in-memory set of recently used codes.

```python
# Source: pyotp docs — https://pyauth.github.io/pyotp/
import pyotp
import secrets

def generate_totp_secret() -> str:
    """Generate a random base32 secret for a new TOTP slot."""
    return pyotp.random_base32()   # 32-char base32 string (160 bits)

def get_provisioning_uri(secret: str, username: str) -> str:
    """Return the otpauth:// URI to encode in a QR code."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name="AI-SOC-Brain")

def verify_totp(secret: str, code: str, valid_window: int = 1) -> bool:
    """Verify a 6-digit TOTP code, ±1 window (allows 30 s clock skew)."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=valid_window)
```

**Replay prevention:** Maintain a small in-memory dict `_seen_totp: dict[str, str]` mapping `operator_id -> last_used_code`. Reject a code that equals `_seen_totp[operator_id]` even if still within its window. This dict is process-local (single uvicorn worker) and survives until restart — sufficient for the single-desktop deployment model.

**QR code generation:**
```python
import qrcode
import io
import base64

def totp_qr_png_b64(provisioning_uri: str) -> str:
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
```

### Pattern 5: SQLite operators Table Migration

**What:** Add `operators` table to existing `_DDL` in `sqlite_store.py`. Apply backward-compatible `ALTER TABLE` migration in `__init__` using the established try/except pattern (already used for `risk_score`).

```python
# New DDL block to append to _DDL string (before closing """)
"""
CREATE TABLE IF NOT EXISTS operators (
    operator_id     TEXT PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    hashed_key      TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'analyst',   -- 'admin' | 'analyst'
    totp_secret     TEXT,                              -- NULL = MFA disabled
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    last_seen_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_operators_username ON operators (username);
"""
```

**Bootstrap logic in SQLiteStore.__init__:**
```python
# Insert legacy admin from AUTH_TOKEN if operators table is empty
# (called from lifespan after SQLiteStore init)
def bootstrap_admin_if_empty(self, auth_token: str) -> None:
    count = self._conn.execute("SELECT COUNT(*) FROM operators").fetchone()[0]
    if count == 0:
        from backend.core.operator_utils import hash_api_key
        self._conn.execute(
            "INSERT INTO operators (operator_id, username, hashed_key, role, is_active, created_at) "
            "VALUES (?, 'admin', ?, 'admin', 1, ?)",
            ("legacy-admin", hash_api_key(auth_token), _now_iso())
        )
        self._conn.commit()
```

**Important:** `CREATE TABLE IF NOT EXISTS` is idempotent — safe to run every startup. No `ALTER TABLE` migrations needed for Phase 19 since the table is new.

### Pattern 6: Backward Compatibility (Legacy Token Path)

The verify_token lookup order:

1. Query `operators` table by bcrypt-verifying presented token against all active operators.
2. If no operator found AND presented token == `settings.AUTH_TOKEN` (constant-time compare via `hmac.compare_digest`) → synthesize a legacy `OperatorContext(operator_id="legacy-admin", role="admin", totp_verified=True)`.
3. Otherwise → 401.

This means existing single-token deployments need zero config change. As soon as an operator is added via the API, the legacy path still works in parallel until the operator explicitly removes the AUTH_TOKEN env var.

**Efficient bcrypt lookup:** bcrypt is slow by design — do NOT SELECT all operators and verify each hash. Instead: store a fast SHA-256 prefix index:
- Add column `key_prefix TEXT` (first 8 chars of raw key, or SHA-256 truncated to 16 hex chars)
- On verify: `SELECT * FROM operators WHERE key_prefix = ?` → then bcrypt-verify only that row
- This turns O(n) bcrypt hashes into O(1) DB lookup + 1 bcrypt verify

Alternative simpler approach for small teams (< 10 operators): just SELECT all active operators and verify sequentially. For a single-desktop tool with 1-3 operators this is fine (< 3 bcrypt verifies at ~0.3 s each = under 1 s worst case, but in practice connection keepalive means this is rare).

**Recommendation:** Use `key_prefix` column for deterministic O(1) behavior regardless of operator count.

### Pattern 7: Audit Attribution Threading

**What:** The `llm_audit` logger in `ollama_client.py` already accepts `extra={}` kwargs. Add `operator_id` to every audit entry.

**How:** `OllamaClient` currently has no knowledge of the request context. Best approach: pass `operator_id` as an optional parameter to `generate()` and `embed()` methods, defaulted to `"system"`. Routes call `ollama.generate(..., operator_id=request.state.operator.operator_id)`.

```python
# In ollama_client.py generate():
_audit_log.info("", extra={
    "event_type": "llm_generate",
    "operator_id": operator_id or "system",
    ...
})
```

This is a non-breaking additive change — existing callers that don't pass `operator_id` default to `"system"`.

### Anti-Patterns to Avoid

- **Storing raw API keys:** Never store the key itself, only the bcrypt hash. The key is shown once on creation and gone.
- **Using `==` for token comparison outside passlib:** Python string `==` is not constant-time. Use `hmac.compare_digest` for the legacy AUTH_TOKEN path.
- **bcrypt on tokens > 72 bytes:** bcrypt silently truncates. Generate keys with `secrets.token_urlsafe(32)` = 43 chars max; validate length on input.
- **Single SELECT all + loop verify:** Leaks timing info proportional to operator count. Use `key_prefix` index.
- **TOTP window > 1:** window=1 (one step = 30 s tolerance) is the industry standard. window=2+ increases replay window.
- **Storing TOTP seen-codes in SQLite:** Unnecessary for single-process, single-desktop. In-memory is fine.
- **Raising 403 for unauthenticated requests:** 401 = no/invalid credentials. 403 = valid credentials + wrong role. Never swap these.
- **Re-importing verify_token inside tests without clearing module cache:** The existing test pattern uses `patch("backend.core.auth.settings")` — follow this exactly for new tests.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| bcrypt hashing | Custom hash scheme | passlib[bcrypt] | bcrypt has known-good cost factor; timing-safe; passlib handles salt generation |
| TOTP generation | RFC 6238 reimplementation | pyotp | Clock drift, window math, base32 encoding edge cases |
| QR code rendering | PNG pixel manipulation | qrcode[pil] | Error correction, quiet zone, format compliance |
| Constant-time comparison | `if a == b` | `hmac.compare_digest` / passlib.verify | Timing oracle vulnerability |
| API key generation | `random.choices` | `secrets.token_urlsafe` | CSPRNG vs PRNG; `random` is not cryptographically secure |

**Key insight:** The three most dangerous DIY auth mistakes (timing oracles, weak randomness, home-grown hash) are each eliminated by using the standard library/passlib combination above.

---

## Common Pitfalls

### Pitfall 1: bcrypt Timing Leak on Lookup Miss

**What goes wrong:** If no operator is found in DB, the code skips bcrypt verify and returns 401 quickly; if found, bcrypt runs slowly. An attacker can time requests to enumerate valid key prefixes.

**Why it happens:** Conditional bcrypt execution.

**How to avoid:** Always run one bcrypt verify even on lookup miss. Cache a dummy bcrypt hash at startup and call `_pwd_context.verify(raw_key, _dummy_hash)` when no operator is found, then return 401.

**Warning signs:** 401 responses are consistently faster than 401 responses for valid-format tokens.

### Pitfall 2: TOTP Replay Window Confusion

**What goes wrong:** pyotp `valid_window` parameter counts steps on each side. `valid_window=1` means current step ± 1, which is ±30 s. This is standard. Many tutorials incorrectly use `valid_window=2` (±60 s) which doubles the replay window.

**Why it happens:** Misreading the docs.

**How to avoid:** Use `valid_window=1`. Document the choice.

### Pitfall 3: Missing `request` Parameter in verify_token Signature

**What goes wrong:** Current `verify_token` signature is `async def verify_token(credentials, token)`. Adding `request: Request` as a parameter changes the FastAPI dependency signature, which may break existing route tests that call `verify_token` directly.

**Why it happens:** FastAPI dependency injection resolves `Request` automatically, but unit tests that call the function directly must now pass a mock Request.

**How to avoid:** Update all existing `test_auth.py` tests to pass a mock `Request` object with `app.state.stores` set.

### Pitfall 4: SQLite Thread Safety for Operators

**What goes wrong:** `self._conn` with `check_same_thread=False` is shared. New `operators` methods must follow the same synchronous pattern and be wrapped in `asyncio.to_thread()` from async routes — same as all other SQLiteStore methods.

**Why it happens:** Forgetting the pattern for new methods.

**How to avoid:** Every new SQLiteStore method is synchronous. Routes call `await asyncio.to_thread(store.method, args)`. No `async def` inside SQLiteStore.

### Pitfall 5: Svelte `$effect` Dependency Tracking for Tabs

**What goes wrong:** If the Operators tab load function is inside a `$effect` that reads `activeTab`, all tab switches will re-run the effect and re-fetch. The ReportsView pattern guards with `&& !loading && data === null`.

**How to avoid:** Follow the exact ReportsView `$effect` pattern:
```typescript
$effect(() => {
    if (activeTab === 'operators' && operators.length === 0 && !operatorsLoading) loadOperators()
})
```

### Pitfall 6: Key Display — One-Time Window

**What goes wrong:** The raw API key must be returned from the create endpoint exactly once, then discarded server-side (only the hash is stored). If the frontend doesn't capture it, it's lost.

**How to avoid:** `POST /api/operators` response includes `{ operator_id, username, role, api_key: "<raw>", created_at }`. After creation, `GET /api/operators/{id}` returns everything except `api_key`. The Svelte UI must show a copy-to-clipboard modal with explicit "I have saved this key" acknowledgment before dismissing.

---

## Code Examples

### SQLite DDL for operators table

```python
# Append to _DDL in backend/stores/sqlite_store.py
CREATE TABLE IF NOT EXISTS operators (
    operator_id     TEXT PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    hashed_key      TEXT NOT NULL,
    key_prefix      TEXT NOT NULL,          -- first 8 chars of raw key for fast lookup
    role            TEXT NOT NULL DEFAULT 'analyst',
    totp_secret     TEXT,                   -- NULL = MFA disabled
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    last_seen_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_operators_username  ON operators (username);
CREATE INDEX IF NOT EXISTS idx_operators_key_prefix ON operators (key_prefix);
```

### Operator lookup in verify_token

```python
# backend/core/auth.py (revised)
import hmac
import asyncio
from passlib.context import CryptContext
from fastapi import HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from backend.core.config import settings
from backend.core.rbac import OperatorContext

_bearer = HTTPBearer(auto_error=False)
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_dummy_hash = _pwd_ctx.hash("dummy-startup-hash")  # for constant-time miss

async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    token: str | None = Query(default=None),
) -> OperatorContext:
    raw = (credentials.credentials if credentials else None) or token
    if not raw:
        raise HTTPException(status_code=401, detail="Unauthorized")

    stores = request.app.state.stores
    ctx = await asyncio.to_thread(_lookup_operator_sync, stores.sqlite, raw)
    if ctx is None:
        # Legacy fallback — constant-time compare
        if hmac.compare_digest(raw, settings.AUTH_TOKEN.strip()):
            ctx = OperatorContext(
                operator_id="legacy-admin",
                username="admin",
                role="admin",
                totp_verified=True,
            )
    if ctx is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    request.state.operator = ctx
    return ctx
```

### Svelte SettingsView tab pattern (follows ReportsView exactly)

```typescript
// dashboard/src/views/SettingsView.svelte
let activeTab = $state<'operators' | 'system'>('operators')
let operators = $state<Operator[]>([])
let operatorsLoading = $state(false)
let operatorsError = $state('')
let newApiKey = $state<string | null>(null)   // one-time display after create

$effect(() => {
    if (activeTab === 'operators' && operators.length === 0 && !operatorsLoading)
        loadOperators()
})

async function loadOperators() {
    operatorsLoading = true; operatorsError = ''
    try { const r = await api.settings.operators.list(); operators = r.operators }
    catch (e: any) { operatorsError = e.message }
    finally { operatorsLoading = false }
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single shared `AUTH_TOKEN` string compare | Per-operator bcrypt hash lookup + `request.state` injection | Phase 19 | Multiple named operators, audit trail, rotation |
| No RBAC | `require_role("admin")` FastAPI Depends | Phase 19 | Admin-only CRUD endpoints are gated |
| No MFA | Optional per-operator TOTP via pyotp | Phase 19 | NIST CSF Govern baseline met |
| Audit log has no attribution | `operator_id` added to llm_audit entries | Phase 19 | Per-operator accountability |

**Deprecated/outdated:**
- Plain `AUTH_TOKEN == token` string compare: replaced by passlib verify + legacy fallback
- `verify_token` returning `None`: now returns `OperatorContext` (non-breaking — existing routes that don't use the return value are unaffected)

---

## Open Questions

1. **Bcrypt cost factor for per-request use**
   - What we know: cost=12 is ~0.3 s per hash; per-request hashing would add 300 ms to every request
   - What's unclear: The project uses HTTP keep-alive with the Svelte frontend — but the QR/provisioning endpoint is infrequent, and the main concern is key creation/rotation, not per-request verify
   - Recommendation: Use the `key_prefix` fast-lookup column so bcrypt verify runs at most once per new TCP connection; subsequent requests use the cached `request.state.operator`. With FastAPI's single-process model and a frontend that sends a single bearer token repeatedly, this is effectively free after first auth. If per-request bcrypt latency becomes a problem, add a short-lived (60 s) in-memory LRU cache keyed on `sha256(raw_key)[:16]`.

2. **TOTP seen-codes persistence across restarts**
   - What we know: In-memory dict is lost on restart; an attacker who captures a TOTP code could replay it within the 30 s window immediately after a restart
   - What's unclear: Whether this is an acceptable risk for an air-gapped desktop tool
   - Recommendation: For Phase 19, in-memory is sufficient. The threat model (air-gapped, single-analyst) makes restart-window replay extremely unlikely. Note this limitation in a comment.

3. **`verify_token` signature change and existing route tests**
   - What we know: 40+ routers all use `dependencies=[Depends(verify_token)]`; the return type changes from `None` to `OperatorContext`
   - Recommendation: Since existing routes don't consume the return value (they just have it as a dep), the change is non-breaking for routes. Existing `test_auth.py` tests that call `verify_token` directly need a mock `Request` with `app.state.stores.sqlite` set. Plan for a test fixture update task.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 with pytest-asyncio 1.3.0 (asyncio_mode=auto) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/unit/test_auth.py tests/unit/test_operator_store.py tests/unit/test_rbac.py tests/unit/test_totp.py -x` |
| Full suite command | `uv run pytest tests/` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P19-T01 | operators table DDL — CREATE IF NOT EXISTS, index created | unit | `uv run pytest tests/unit/test_operator_store.py::TestOperatorDDL -x` | ❌ Wave 0 |
| P19-T01 | hash_api_key() produces bcrypt hash; verify returns True for correct key, False for wrong | unit | `uv run pytest tests/unit/test_operator_store.py::TestBcrypt -x` | ❌ Wave 0 |
| P19-T01 | bootstrap_admin_if_empty() inserts admin when table empty; no-op when operators exist | unit | `uv run pytest tests/unit/test_operator_store.py::TestBootstrap -x` | ❌ Wave 0 |
| P19-T02 | verify_token() returns OperatorContext for valid operator key | unit | `uv run pytest tests/unit/test_auth.py::test_operator_lookup_valid -x` | ❌ Wave 0 (update existing file) |
| P19-T02 | verify_token() falls back to AUTH_TOKEN legacy path | unit | `uv run pytest tests/unit/test_auth.py::test_legacy_token_fallback -x` | ❌ Wave 0 |
| P19-T02 | verify_token() injects operator_id into request.state | unit | `uv run pytest tests/unit/test_auth.py::test_state_injection -x` | ❌ Wave 0 |
| P19-T02 | audit log entries contain operator_id field | unit | `uv run pytest tests/unit/test_ollama_audit.py::test_operator_id_in_audit -x` | ❌ Wave 0 |
| P19-T03 | require_role("admin") returns 403 for analyst role | unit | `uv run pytest tests/unit/test_rbac.py::test_require_role_403 -x` | ❌ Wave 0 |
| P19-T03 | require_role("admin") passes for admin role | unit | `uv run pytest tests/unit/test_rbac.py::test_require_role_pass -x` | ❌ Wave 0 |
| P19-T03 | 401 returned for no token (unauthenticated, not 403) | unit | `uv run pytest tests/unit/test_auth.py::test_no_token_401 -x` | ✅ existing |
| P19-T04 | generate_totp_secret() returns valid base32 string | unit | `uv run pytest tests/unit/test_totp.py::test_generate_secret -x` | ❌ Wave 0 |
| P19-T04 | verify_totp() returns True for current code, False for wrong | unit | `uv run pytest tests/unit/test_totp.py::test_verify_totp -x` | ❌ Wave 0 |
| P19-T04 | replay attack: same code rejected twice in same window | unit | `uv run pytest tests/unit/test_totp.py::test_replay_prevention -x` | ❌ Wave 0 |
| P19-T04 | provisioning_uri() returns valid otpauth:// URI format | unit | `uv run pytest tests/unit/test_totp.py::test_provisioning_uri -x` | ❌ Wave 0 |
| P19-T05 | POST /api/operators creates operator, returns api_key once | unit | `uv run pytest tests/unit/test_operators_api.py::test_create_operator -x` | ❌ Wave 0 |
| P19-T05 | GET /api/operators response excludes hashed_key and totp_secret | unit | `uv run pytest tests/unit/test_operators_api.py::test_list_no_secrets -x` | ❌ Wave 0 |
| P19-T05 | POST /api/operators/{id}/rotate-key generates new key, old key rejected | unit | `uv run pytest tests/unit/test_operators_api.py::test_key_rotation -x` | ❌ Wave 0 |
| P19-T05 | Analyst cannot access POST /api/operators (403) | unit | `uv run pytest tests/unit/test_operators_api.py::test_analyst_forbidden -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/test_auth.py tests/unit/test_operator_store.py tests/unit/test_rbac.py tests/unit/test_totp.py -x`
- **Per wave merge:** `uv run pytest tests/`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_operator_store.py` — covers P19-T01 (DDL, bcrypt, bootstrap)
- [ ] `tests/unit/test_rbac.py` — covers P19-T03 (require_role 401/403)
- [ ] `tests/unit/test_totp.py` — covers P19-T04 (generate, verify, replay, URI)
- [ ] `tests/unit/test_operators_api.py` — covers P19-T05 (CRUD API, key display, rotation)
- [ ] Update `tests/unit/test_auth.py` — add operator lookup tests, legacy fallback, state injection (file exists, needs extension)
- [ ] Framework install: `uv add "passlib[bcrypt]>=1.7.4" "pyotp>=2.9" "qrcode[pil]>=7.4"` — none of these are in pyproject.toml yet

---

## Sources

### Primary (HIGH confidence)

- `backend/core/auth.py` (project) — existing verify_token signature, string-compare pattern, query-param fallback
- `backend/stores/sqlite_store.py` (project) — _DDL pattern, `self._conn`, `try/except ALTER TABLE` migration idiom, `asyncio.to_thread` wrapping expectation
- `backend/main.py` (project) — lifespan bootstrap pattern, `app.state.*` attachment, `dependencies=[Depends(verify_token)]` on every router
- `backend/core/deps.py` (project) — `get_stores`, `request.app.state.stores` pattern
- `backend/core/logging.py` (project) — `llm_audit` logger wired to `logs/llm_audit.jsonl`, `_audit_log.info("", extra={...})` call pattern
- `backend/services/ollama_client.py` (project) — `_audit_log.info` call sites and extra fields
- `dashboard/src/views/ReportsView.svelte` (project) — tab-switching pattern with `$state<'tab1'|'tab2'>`, `$effect` guards
- `dashboard/src/lib/api.ts` (project) — `authHeaders()` pattern, namespace structure (`api.reports`, `api.analytics`)
- `pyproject.toml` (project) — no bcrypt/pyotp/qrcode yet; fastapi 0.115.12, pytest-asyncio 1.3.0, asyncio_mode=auto

### Secondary (MEDIUM confidence)

- passlib official docs (https://passlib.readthedocs.io/en/stable/) — bcrypt cost factor guidance, `CryptContext` API
- pyotp official docs (https://pyauth.github.io/pyotp/) — `TOTP.verify(valid_window=1)`, `provisioning_uri()`, `random_base32()`
- FastAPI docs (https://fastapi.tiangolo.com/advanced/using-request-directly/) — `request.state` injection pattern
- FastAPI security docs (https://fastapi.tiangolo.com/tutorial/security/) — `require_role` dependency factory pattern

### Tertiary (LOW confidence)

- None — all findings verified against project source or official docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — passlib/pyotp/qrcode are well-documented; versions confirmed stable
- Architecture: HIGH — patterns derived directly from reading project source files
- Pitfalls: HIGH — derived from code analysis of current auth.py, sqlite_store.py patterns, and bcrypt/TOTP properties

**Research date:** 2026-03-31
**Valid until:** 2026-07-01 (passlib/pyotp are stable; FastAPI 0.115 API stable)
