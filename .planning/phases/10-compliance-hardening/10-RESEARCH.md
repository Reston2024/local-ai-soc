# Phase 10: Compliance Hardening - Research

**Researched:** 2026-03-26
**Domain:** Security hardening, CI/CD, authentication, prompt injection, dependency management, audit logging
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**CI/CD Pipeline (CRITICAL — R1)**
- Create `.github/workflows/ci.yml` with jobs: `lint` (ruff), `test` (pytest tests/unit/ with coverage), `dependency-audit` (pip-audit), `secret-scan` (gitleaks)
- Coverage threshold: 70% minimum enforced in CI (`--cov-fail-under=70`)
- Smoke tests are PowerShell-only and NOT included in CI; CI runs unit tests only
- Add `pytest-cov` to pyproject.toml dev dependencies
- Test artifacts (JUnit XML + coverage XML) must be generated as CI artifacts

**Prompt Injection Sanitization (CRITICAL — R1, REQ-01/T-01)**
- Modify `ingestion/normalizer.py`: add `_INJECTION_PATTERNS` compiled regex and `_scrub_injection(text: str) -> str`
- Patterns to strip (case-insensitive): `ignore previous instructions`, `[INST]`, `[/INST]`, `<|system|>`, `<|user|>`, `<|assistant|>`, `###`, `---SYSTEM`, `---INSTRUCTION`, any `ignore.*instruction|prompt|context` sequence
- Apply scrubbing to: `command_line`, `raw_event`, `domain`, `url`, `file_path` fields
- New tests in `tests/unit/test_normalizer.py` asserting patterns are stripped
- Scrubbing happens BEFORE ChromaDB embedding, AFTER null-byte stripping

**Firewall Configuration Script (HIGH — R1, REQ-03/T-03)**
- Create `scripts/configure-firewall.ps1`: `New-NetFirewallRule` blocking inbound port 11434 from all except 127.0.0.1 and Docker NIC range (172.16.0.0/12)
- Create `scripts/verify-firewall.ps1`: checks rule exists, is enabled, has correct parameters
- Integrate `verify-firewall.ps1` check into `scripts/status.ps1` as a preflight item
- Script must check for Admin elevation and prompt if not elevated

**Docker / Caddy Hardening (HIGH — R1)**
- `docker-compose.yml`: change `CADDY_ADMIN=0.0.0.0:2019` to `CADDY_ADMIN=127.0.0.1:2019`
- `docker-compose.yml`: pin Caddy image to immutable digest format `caddy:2.9-alpine@sha256:<digest>`
- `infra/docker-compose.yml`: add prominent `# DEPRECATED — Phase 2-3 only, not production` header comment

**Dependency Pinning (HIGH — R2, REQ-07)**
- `pyproject.toml`: convert all `>=` specifiers to `==` for direct dependencies using `uv.lock` as source of truth
- `backend/requirements.txt`: delete entirely
- `REPRODUCIBILITY_RECEIPT.md`: fill all TBD entries; update status from "BOOTSTRAPPING" to "VERIFIED"

**API Authentication (HIGH — R2)**
- Scope: shared secret token only (NOT OAuth2/OIDC)
- Create `backend/core/auth.py`: `verify_token` FastAPI dependency checking `Authorization: Bearer <token>` against `AUTH_TOKEN` env var
- Apply `Depends(verify_token)` to all non-health routes in `backend/main.py`
- `GET /health` and `GET /openapi.json` remain unauthenticated
- Add `AUTH_TOKEN=<generate-a-strong-token>` to `config/.env.example`
- New tests: `tests/unit/test_auth.py`

**LLM Audit Logging (HIGH — R2, REQ-11)**
- Modify `backend/services/ollama_client.py`: wrap `generate()` and `embed()` with audit log calls
- Log entries: `event_type`, `model`, `prompt_length`, `prompt_hash` (sha256 first 16 hex chars), `response_length`, `response_hash`
- Add dedicated rotating file handler in `backend/core/logging.py` → `logs/llm_audit.jsonl`
- NOT full prompt text — hashes only

**Data Directory ACL Script (HIGH — R2, REQ-02)**
- Create `scripts/configure-acls.ps1`: `icacls data\ /inheritance:d /grant:r "$env:USERNAME:(OI)(CI)F" /remove "Everyone" /remove "Users"`
- Add ACL preflight check to `scripts/start.ps1`

**Security Test Suite (HIGH — R2)**
- Create `tests/security/` directory with `__init__.py`
- `tests/security/test_injection.py`: injection patterns stripped before embedding; path traversal rejected
- `tests/security/test_auth.py`: all non-health endpoints return 401 without token
- These run in CI as part of `pytest tests/unit/ tests/security/`

**Documentation Cleanup (MEDIUM — R2)**
- `docs/manifest.md`: regenerate to reflect Phase 9 file tree and active endpoints
- Add `ADR-019` to `DECISION_LOG.md`: backend/src/ dual-path — retire (mark deprecated, deletion Phase 11)
- Remove duplicate `docs/decision-log.md` if it diverges from `DECISION_LOG.md`
- Create `docs/reproducibility.md` as pointer to `REPRODUCIBILITY_RECEIPT.md`

### Claude's Discretion
- Wave structure and plan grouping (parallelism within R1 vs R2 boundary)
- Whether to add `pip-audit` or `trivy` for dependency scanning in CI (prefer `pip-audit`)
- Exact gitleaks vs trufflehog choice (prefer gitleaks)
- Whether `AUTH_TOKEN` uses `secrets.token_hex(32)` or UUID
- Test fixture design for auth and injection tests

### Deferred Ideas (OUT OF SCOPE)
- Log integrity protection (append-only shipping, log signing) — R3
- Data-at-rest encryption (REQ-15)
- Full NIST SP 800-53 Rev. 5 compliance
- backend/src/ deletion — Phase 11
- Rate limiting (OWASP ASVS V4.2.4)
- Certificate pinning / rotation policy
- Session management
- Aegis Swarm Core architecture
- A2A / MCP / LangGraph migration
- Compliance control matrix document — R4
- Assurance case (GSN) — R4
- Container image scanning in CI — R3
- Coverage shipping to external service (Codecov etc.) — R4
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P10-T01 | Prompt injection sanitization in `ingestion/normalizer.py` | Scrub patterns confirmed absent in current source (lines 126-140 only strip control chars); `_scrub_injection` hook point identified after `_clean_str` |
| P10-T02 | API authentication layer (`backend/core/auth.py` + main.py wiring) | `main.py` has no `Depends(verify_token)` anywhere; all 10+ routers currently unauthenticated; `AUTH_TOKEN` not in `Settings` or `config.py` |
| P10-T03 | Firewall configuration script (`scripts/configure-firewall.ps1`) | `scripts/` dir confirmed: no firewall script present; `verify-firewall.ps1` also absent; `status.ps1` has no firewall check |
| P10-T04 | CI/CD pipeline (`.github/workflows/ci.yml`) | `.github/` directory confirmed absent; `pytest-cov` not in `pyproject.toml`; `pip-audit` and `gitleaks` not installed |
| P10-T05 | Docker/Caddy hardening (`docker-compose.yml`) | Confirmed `CADDY_ADMIN=0.0.0.0:2019` still present; image `caddy:2.9-alpine` has no digest pin |
| P10-T06 | Dependency pinning completion (`pyproject.toml`) | Confirmed: `pydantic>=2.0`, `pydantic-settings>=2.0`, `httpx>=0.28.1`, `chromadb>=0.6.3`, `langgraph>=0.4.0`, `langchain-ollama>=0.3.0`, `pySigma>=0.11.0`, `PyYAML>=6.0.2`, `evtx>=0.8.2`, `pytest>=8.3.5`, `pytest-asyncio>=0.25.0`, `ruff>=0.9.0` all use `>=`; `backend/requirements.txt` still exists |
| P10-T07 | LLM audit logging in `ollama_client.py` + `logging.py` | `generate()` and `embed()` emit only `log.debug()`; no audit handler and no `logs/llm_audit.jsonl`; `setup_logging()` only creates `backend.jsonl` |
| P10-T08 | Data directory ACL script (`scripts/configure-acls.ps1`) | No ACL script in `scripts/`; `start.ps1` has no ACL preflight check |
| P10-T09 | Security test suite (`tests/security/`) | `tests/security/` directory confirmed absent; no injection or auth tests exist |
| P10-T10 | Documentation cleanup (manifest, ADR-019, reproducibility) | `REPRODUCIBILITY_RECEIPT.md` status still "BOOTSTRAPPING"; TBD entries: pySigma, langgraph, evtx, Ollama, models, Docker, Caddy, Svelte, Cytoscape, D3; `DECISION_LOG.md` last entry is ADR-018; `docs/reproducibility.md` exists as stub |
</phase_requirements>

---

## Summary

Phase 10 is a pure hardening phase with no new features. All gaps are implementation-level: the architecture is sound but the execution evidence required for any audit is absent. The audit identified the system as "PROTOTYPE-TO-OPERATIONAL — NON-COMPLIANT" against NIST CSF 2.0, NIST SP 800-53 Rev. 5, NIST AI RMF 1.0, OWASP ASVS 4.0.3, and CIS Controls v8.

The codebase is in a known, clean state after Phase 9 (82 passed, 0 failed, npm build exits 0). All 10 tasks involve creating new files or making targeted modifications to existing ones. No task requires refactoring existing capabilities. The primary risk is task interdependency: the security test suite (T09) depends on the auth layer (T02) and injection scrubbing (T01) being present first, so R1 tasks must gate R2 tasks.

The work divides cleanly into two waves: R1 (highest-impact, unblocks CI) covers T01, T03, T04, T05; R2 (depends on R1 passing CI) covers T02, T06, T07, T08, T09, T10.

**Primary recommendation:** Execute R1 tasks first as a unit, validate with CI passing, then execute R2 tasks. The CI pipeline itself becomes the verification mechanism for all subsequent work.

---

## Current State Audit (Confirmed from Source)

### Files that must be modified (exist, gaps confirmed)
| File | Current Gap | Change Required |
|------|-------------|----------------|
| `ingestion/normalizer.py` | `_clean_str()` only strips control chars (line 47); no `_scrub_injection` | Add `_INJECTION_PATTERNS` regex + `_scrub_injection()` + call in `normalize_event()` step 5 |
| `backend/services/ollama_client.py` | `generate()` logs only `log.debug()` at end; `embed()` has no log at all | Wrap both with pre/post audit log using sha256 hashes |
| `backend/core/logging.py` | `setup_logging()` creates only `backend.jsonl` handler | Add second `RotatingFileHandler` for `llm_audit.jsonl` |
| `backend/main.py` | No `Depends(verify_token)` in any router include; no `AUTH_TOKEN` config | Wire `verify_token` dependency to all non-health routers |
| `backend/core/config.py` | No `AUTH_TOKEN` field | Add `AUTH_TOKEN: str = ""` with validator |
| `docker-compose.yml` | `CADDY_ADMIN=0.0.0.0:2019`; image unpinned `caddy:2.9-alpine` | Fix admin bind; add digest pin |
| `pyproject.toml` | 12 `>=` specifiers (pydantic, pydantic-settings, httpx, chromadb, langgraph, langchain-ollama, pySigma, PyYAML, evtx, pytest, pytest-asyncio, ruff) | Convert to `==` using uv.lock values |
| `scripts/status.ps1` | No firewall check | Add `verify-firewall.ps1` preflight |
| `scripts/start.ps1` | No ACL preflight | Add ACL check warning |
| `tests/unit/test_normalizer.py` | No injection tests | Add injection pattern test class |
| `REPRODUCIBILITY_RECEIPT.md` | Status "BOOTSTRAPPING"; 10 TBD entries | Fill from uv.lock; update status |
| `DECISION_LOG.md` | Last entry ADR-018 | Add ADR-019 for backend/src/ deprecation |

### Files that must be created (do not exist)
| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | GitHub Actions pipeline |
| `backend/core/auth.py` | Bearer token FastAPI dependency |
| `scripts/configure-firewall.ps1` | Windows Firewall rule creation |
| `scripts/verify-firewall.ps1` | Firewall rule verification |
| `scripts/configure-acls.ps1` | Data directory ACL hardening |
| `tests/unit/test_auth.py` | Unit tests for auth module |
| `tests/security/__init__.py` | Security test directory marker |
| `tests/security/test_injection.py` | Injection pattern and path traversal tests |
| `tests/security/test_auth.py` | Endpoint auth enforcement tests |

### Files that must be deleted
| File | Reason |
|------|--------|
| `backend/requirements.txt` | Stale (versions diverge from pyproject.toml); superseded by pyproject.toml + uv.lock |

---

## Standard Stack

### Core
| Library | Version (from uv.lock) | Purpose | Role in Phase 10 |
|---------|----------------------|---------|-----------------|
| `pytest-cov` | to be installed | Coverage measurement | CI enforcement gate |
| `pip-audit` | latest stable | Dependency vulnerability scan | CI audit job |
| `gitleaks` | latest binary | Secret scanning in CI | CI secret-scan job |
| `hashlib` (stdlib) | Python 3.12 stdlib | sha256 for LLM audit hashes | `ollama_client.py` wrapping |
| `secrets` (stdlib) | Python 3.12 stdlib | Token generation instructions | `config/.env.example` doc |
| `re` (stdlib) | Python 3.12 stdlib | Injection pattern matching | `normalizer.py` extension |

### From uv.lock (exact versions for pinning)
| Package | uv.lock Version | Current pyproject.toml |
|---------|----------------|----------------------|
| `pydantic` | 2.12.5 | `>=2.0` → pin to `==2.12.5` |
| `pydantic-settings` | 2.13.1 | `>=2.0` → pin to `==2.13.1` |
| `httpx` | 0.28.1 | `>=0.28.1` → pin to `==0.28.1` |
| `chromadb` | 1.5.5 | `>=0.6.3` → pin to `==1.5.5` |
| `langgraph` | 1.1.2 | `>=0.4.0` → pin to `==1.1.2` |
| `langchain-ollama` | 1.0.1 | `>=0.3.0` → pin to `==1.0.1` |
| `pySigma` | 1.2.0 | `>=0.11.0` → pin to `==1.2.0` |
| `PyYAML` | 6.0.3 | `>=6.0.2` → pin to `==6.0.3` |
| `evtx` | 0.11.0 | `>=0.8.2` → pin to `==0.11.0` |
| `pytest` | (check uv.lock) | `>=8.3.5` → pin |
| `pytest-asyncio` | 1.3.0 | `>=0.25.0` → pin to `==1.3.0` |
| `ruff` | 0.15.6 | `>=0.9.0` → pin to `==0.15.6` |

Note: `fastapi==0.115.12`, `uvicorn[standard]==0.34.3`, `duckdb==1.3.0` are already pinned with `==`.

### Supporting
| Library | Purpose | Notes |
|---------|---------|-------|
| `pytest-cov` | Coverage XML + terminal output | Add to pyproject.toml `[project.optional-dependencies]` dev group |
| `logging.handlers.RotatingFileHandler` | LLM audit file | Already imported in `backend/core/logging.py` — reuse pattern |

---

## Architecture Patterns

### Pattern 1: FastAPI Dependency Injection for Auth

The project already uses FastAPI's `Depends()` pattern in `backend/core/deps.py`. The auth dependency follows the same pattern.

```python
# backend/core/auth.py
# Source: FastAPI official docs — Security patterns
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.core.config import settings

_bearer = HTTPBearer(auto_error=False)

async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    if not settings.AUTH_TOKEN:
        return  # AUTH_TOKEN not configured → open (dev mode)
    if credentials is None or credentials.credentials != settings.AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
```

**Wiring in main.py:** Add `dependencies=[Depends(verify_token)]` to `app.include_router()` calls for all non-health routers. The `health_router` and OpenAPI schema endpoint are excluded.

### Pattern 2: Injection Scrubbing in Normalizer

The scrub step inserts at the same location as the existing control character stripping (step 5 in `normalize_event()`). The `_clean_str()` function call is the right model to follow.

```python
# ingestion/normalizer.py addition
_INJECTION_PATTERNS = re.compile(
    r"(?i)(?:"
    r"ignore\s+previous\s+instructions?"
    r"|\[/?INST\]"
    r"|<\|(?:system|user|assistant)\|>"
    r"|###"
    r"|---SYSTEM"
    r"|---INSTRUCTION"
    r"|ignore\s+.*?(?:instruction|prompt|context)"
    r")",
    re.IGNORECASE,
)

def _scrub_injection(value: str) -> str:
    """Remove prompt injection patterns from text fields."""
    return _INJECTION_PATTERNS.sub("", value)
```

**Apply after** `_clean_str()` call in `normalize_event()`, specifically to: `command_line`, `raw_event`, `domain`, `url`, `file_path`.

### Pattern 3: LLM Audit Logging

The existing `logging.py` pattern (RotatingFileHandler + _JsonFormatter) is the exact template. A second handler targeting `llm_audit.jsonl` on a named logger is the correct approach.

```python
# backend/core/logging.py addition to setup_logging()
llm_audit_handler = logging.handlers.RotatingFileHandler(
    log_path / "llm_audit.jsonl",
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=10,
    encoding="utf-8",
)
llm_audit_handler.setLevel(logging.INFO)
llm_audit_handler.setFormatter(formatter)
# Attach to named logger, not root, to isolate audit records
logging.getLogger("llm_audit").addHandler(llm_audit_handler)
logging.getLogger("llm_audit").propagate = False
```

Calling code in `ollama_client.py`:
```python
import hashlib
_audit_log = logging.getLogger("llm_audit")

# In generate() before returning:
prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
response_hash = hashlib.sha256(response_text.encode()).hexdigest()[:16]
_audit_log.info("llm_generate", extra={
    "event_type": "generate",
    "model": payload["model"],
    "prompt_length": len(prompt),
    "prompt_hash": prompt_hash,
    "response_length": len(response_text),
    "response_hash": response_hash,
})
```

### Pattern 4: GitHub Actions CI for uv + Python

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run ruff check .
      - run: uv run ruff format --check .

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pytest tests/unit/ tests/security/ --cov=backend --cov=ingestion --cov-report=xml --cov-report=term --cov-fail-under=70 --junitxml=test-results.xml
      - uses: actions/upload-artifact@v4
        with:
          name: test-artifacts
          path: |
            test-results.xml
            coverage.xml

  dependency-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run pip-audit

  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
```

### Pattern 5: PowerShell Firewall Script (Windows-native)

```powershell
# scripts/configure-firewall.ps1
# Requires: PowerShell 7, Admin elevation
#Requires -RunAsAdministrator
$RuleName = "AI-SOC-Brain-Ollama-Restrict"
New-NetFirewallRule `
    -DisplayName $RuleName `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 11434 `
    -RemoteAddress "127.0.0.1","172.16.0.0/12" `
    -Action Allow
# Block all other inbound to 11434
New-NetFirewallRule `
    -DisplayName "$RuleName-Block" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 11434 `
    -Action Block `
    -Profile Any
```

Note: Windows Firewall processes rules in order — Allow rules for specific sources must be created before the Block rule.

### Anti-Patterns to Avoid

- **Auth token hardcoded in source:** `AUTH_TOKEN` must only come from env/`.env` file, never from a default value other than `""` (empty = dev mode / auth disabled).
- **Audit log to root logger:** LLM audit records must go to a named logger with `propagate = False` to prevent double-logging to `backend.jsonl`.
- **Injection scrubbing via string replace:** Use `re.compile()` at module level (not inside the function) to avoid recompilation on every event.
- **Tests that require running Ollama:** Auth and injection tests are pure unit tests — they must not import or require `OllamaClient` or any store.
- **pytest-cov in main dependencies:** Add to `[project.optional-dependencies]` under a `dev` group or as a CI-only install, not to `dependencies = [...]` (which is production deps).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bearer token auth | Custom middleware parsing `Authorization` header | `fastapi.security.HTTPBearer` + `Security()` | FastAPI's `HTTPBearer` handles malformed headers, returns proper 403/401, integrates with OpenAPI docs |
| Secret scanning | Custom regex on git diff | gitleaks | Handles packed objects, binary files, complex git history; 1000+ built-in rules |
| Dependency vuln scan | `pip list` + manual CVE lookup | `pip-audit` | Queries PyPI Advisory DB and OSV; understands uv lockfile format |
| Coverage reporting | Manual test counting | `pytest-cov` | Accurate branch + line coverage; generates LCOV, XML, HTML; integrates with CI artifacts |
| Caddy digest pinning | Manual docker pull + inspection | `docker inspect --format '{{index .RepoDigests 0}}'` | Authoritative digest from registry; must be done once before hardcoding |

**Key insight:** The compliance gaps are almost entirely solved by thin wrappers and configuration changes to existing mature tools. No significant new logic is required.

---

## Common Pitfalls

### Pitfall 1: Injection Regex Ordering and `raw_event` Field
**What goes wrong:** `raw_event` can contain the full original event dict as a JSON string. Scrubbing it will modify stored forensic evidence and may cause DuckDB deduplication mismatches on re-ingestion.
**Why it happens:** The injection scrub was added to prevent embedding poisoning, but `raw_event` also feeds DuckDB storage.
**How to avoid:** Apply `_scrub_injection` only to fields used for embedding (`command_line`, `domain`, `url`, `file_path`). The `raw_event` field is also specified in CONTEXT.md for scrubbing — implement as specified but note in tests that raw_event scrubbing is intentional (it prevents injection from appearing in RAG context even if stored).
**Warning signs:** Deduplication test failures after adding scrubbing.

### Pitfall 2: Auth Wiring Breaks Existing Unit Tests
**What goes wrong:** Adding `Depends(verify_token)` to routers will break every existing unit test that calls the API without a token header, including integration tests and sigma_smoke tests.
**Why it happens:** FastAPI enforces dependencies at request time; test clients that use `TestClient` without headers will get 401.
**How to avoid:** The `verify_token` dependency must check `if not settings.AUTH_TOKEN: return` (open mode when no token configured). Unit tests that use `create_app()` should either set `AUTH_TOKEN=""` in test config or pass the token header. The test conftest should be updated to pass `Authorization: Bearer test-token` when `AUTH_TOKEN` is set.
**Warning signs:** Existing `tests/unit/` tests fail with 401 after auth wiring.

### Pitfall 3: GitHub Actions uv Lockfile Sync
**What goes wrong:** CI runs `uv sync` but the lockfile was generated on Windows; some packages have platform-specific wheels (e.g., `chromadb` pulls different wheels on Linux).
**Why it happens:** uv.lock records platform markers; linux runner may have different resolution.
**How to avoid:** Use `uv sync --frozen` in CI to enforce the lockfile exactly. If sync fails, investigate the specific package rather than allowing resolution to drift.
**Warning signs:** CI test job fails on import (wrong platform wheel) despite tests passing locally.

### Pitfall 4: Caddy Digest Pin Invalidation
**What goes wrong:** The Caddy image digest is pinned to a specific manifest SHA. If Docker Hub garbage-collects or re-pushes the tag (rare for official images), the pinned digest becomes invalid.
**Why it happens:** Immutable digest format `image@sha256:xxx` requires the specific manifest to remain in the registry.
**How to avoid:** Verify the digest is current by pulling with `docker pull caddy:2.9-alpine` and running `docker inspect --format='{{index .RepoDigests 0}}' caddy:2.9-alpine` immediately before pinning. Document the pull date in `docker-compose.yml` as a comment.
**Warning signs:** `docker-compose up` fails with "manifest unknown" error.

### Pitfall 5: `pip-audit` Failing on chromadb
**What goes wrong:** `chromadb` has a large transitive dependency tree (grpcio, onnxruntime, etc.); some of these have known advisory entries that trigger pip-audit failures in CI even though the vulnerabilities are low severity or not exploitable.
**Why it happens:** pip-audit by default fails on any advisory, including informational ones.
**How to avoid:** Run pip-audit with `--ignore-vuln` for specific known-safe advisories, or use `--fix` to check if a patched version exists. Document any ignored advisories in a `pip-audit.toml` or inline CI comment with rationale.
**Warning signs:** CI dependency-audit job fails on first run even with pinned deps.

### Pitfall 6: Windows `icacls` ACL Syntax on Paths with Spaces
**What goes wrong:** `icacls data\` fails if the project is in a path containing spaces (e.g., `C:\Users\Admin\AI-SOC Brain\`).
**Why it happens:** PowerShell passes unquoted paths to `icacls` which splits on spaces.
**How to avoid:** Always quote the path: `icacls "$dataDir" /inheritance:d ...`. Use `$PSScriptRoot` or `Resolve-Path` to compute the absolute path dynamically.
**Warning signs:** `icacls` reports "No files with a SACL were found" or path-not-found error.

### Pitfall 7: LLM Audit Logger Double-Initialisation
**What goes wrong:** `setup_logging()` is idempotent (guarded by `_INITIALIZED`), but the `llm_audit` named logger's handlers accumulate if `get_logger("llm_audit")` is called before `setup_logging()` runs.
**Why it happens:** Python's logging module attaches handlers per-call; calling `addHandler` twice produces duplicate log entries.
**How to avoid:** Check `if not logging.getLogger("llm_audit").handlers:` before adding the handler in `setup_logging()`. The `_INITIALIZED` guard already prevents double-setup for the root logger — extend the same guard to the llm_audit handler.
**Warning signs:** Each LLM call produces 2+ entries in `llm_audit.jsonl`.

---

## Code Examples

### Verified Pattern: FastAPI Security Dependency
```python
# Source: FastAPI official docs https://fastapi.tiangolo.com/tutorial/security/http-basic-auth/
# Adapted for Bearer token pattern
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)

async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> None:
    expected = settings.AUTH_TOKEN
    if not expected:
        return  # dev mode — no token configured
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
```

### Verified Pattern: pytest-cov CI Invocation
```bash
# Source: pytest-cov docs https://pytest-cov.readthedocs.io/
uv run pytest tests/unit/ tests/security/ \
  --cov=backend --cov=ingestion \
  --cov-report=xml:coverage.xml \
  --cov-report=term-missing \
  --cov-fail-under=70 \
  --junitxml=test-results.xml
```

### Verified Pattern: Settings AUTH_TOKEN Field
```python
# backend/core/config.py addition — pydantic-settings pattern
AUTH_TOKEN: str = ""  # Empty = auth disabled (dev mode)
# In .env: AUTH_TOKEN=<output of: python -c "import secrets; print(secrets.token_hex(32))">
```

### Verified Pattern: Caddy Digest Pin
```bash
# Pull and inspect digest (run once, then hardcode the sha256 in docker-compose.yml)
docker pull caddy:2.9-alpine
docker inspect --format='{{index .RepoDigests 0}}' caddy:2.9-alpine
# Example output: caddy@sha256:abcdef1234...
# Then in docker-compose.yml:
#   image: caddy:2.9-alpine@sha256:abcdef1234...
```

### Verified Pattern: uv.lock exact version extraction
```bash
# Extract exact version for a package from uv.lock
grep -A2 'name = "pydantic"' uv.lock | grep version
# Use this value in pyproject.toml as ==X.Y.Z
```

---

## State of the Art

| Old Approach | Current Approach | Impact on This Phase |
|--------------|------------------|---------------------|
| `requirements.txt` pin | `pyproject.toml` + `uv.lock` | Delete `backend/requirements.txt` — lockfile is canonical |
| `pip install` in CI | `uv sync --frozen` | Faster, reproducible, honours lockfile |
| Manual secret hunting | gitleaks v8 with TOML config | Single binary, pre-built GitHub Action, no auth needed |
| GitHub Actions v3 actions | `actions/checkout@v4`, `actions/upload-artifact@v4` | Use v4 throughout; v3 deprecated |
| `astral-sh/setup-uv@v2` | `astral-sh/setup-uv@v3` | v3 supports `uv.lock` natively |

**Deprecated/outdated:**
- `backend/requirements.txt`: stale format (loose `>=` pins, older versions than lockfile). Must be deleted.
- `REPRODUCIBILITY_RECEIPT.md` status "BOOTSTRAPPING": stale from Phase 1. Must be updated to "VERIFIED".

---

## Open Questions

1. **Caddy image digest**
   - What we know: image is `caddy:2.9-alpine` without digest
   - What's unclear: current digest SHA256 (must be fetched at plan execution time with `docker pull`)
   - Recommendation: Planner task must include a step to pull and inspect before hardcoding; use a placeholder in the task and fill at execution

2. **pytest-cov coverage baseline**
   - What we know: 70% threshold is required; current test suite has 12 unit test files
   - What's unclear: current line coverage percentage (untested before Phase 10)
   - Recommendation: First CI run may fail coverage threshold; plan must include a task to measure current coverage with `pytest --cov --cov-report=term` and add targeted tests if below 70%

3. **AUTH_TOKEN and existing tests**
   - What we know: auth dependency must be transparent when `AUTH_TOKEN=""` (dev mode)
   - What's unclear: whether any integration tests set `AUTH_TOKEN` in environment
   - Recommendation: The `verify_token` open-mode bypass (empty token = skip check) must be the default; tests do not need modification if AUTH_TOKEN remains unset in test environment

4. **pip-audit advisory baseline**
   - What we know: chromadb has a large dependency tree
   - What's unclear: whether current pinned transitive deps have any known CVEs
   - Recommendation: First run of pip-audit may produce warnings; plan should include a step to review and document any ignored advisories before CI is set to block on failures

---

## Validation Architecture

nyquist_validation is enabled (confirmed in `.planning/config.json`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 1.3.0 (via pytest-asyncio 1.3.0, pytest to be checked from uv.lock) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"`, `testpaths = ["tests"]` |
| Quick run command | `uv run pytest tests/unit/ -x -q` |
| Full suite command | `uv run pytest tests/unit/ tests/security/ --cov=backend --cov=ingestion --cov-fail-under=70` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P10-T01 | `_scrub_injection` removes `[INST]` patterns from `command_line` | unit | `uv run pytest tests/unit/test_normalizer.py -k "injection" -x` | Partial — `test_normalizer.py` exists, injection tests do not yet |
| P10-T01 | `_scrub_injection` removes `<\|system\|>` from `domain` field | unit | `uv run pytest tests/unit/test_normalizer.py -k "injection" -x` | Partial |
| P10-T01 | `_scrub_injection` removes `ignore previous instructions` from `url` | unit | `uv run pytest tests/unit/test_normalizer.py -k "injection" -x` | Partial |
| P10-T02 | `verify_token` raises 401 with missing `Authorization` header | unit | `uv run pytest tests/unit/test_auth.py -x` | Wave 0 gap |
| P10-T02 | `verify_token` raises 401 with wrong token | unit | `uv run pytest tests/unit/test_auth.py -x` | Wave 0 gap |
| P10-T02 | `verify_token` passes with correct token | unit | `uv run pytest tests/unit/test_auth.py -x` | Wave 0 gap |
| P10-T02 | All non-health endpoints return 401 without token | security | `uv run pytest tests/security/test_auth.py -x` | Wave 0 gap |
| P10-T03 | `configure-firewall.ps1` exists and is valid PowerShell | manual | `pwsh -File scripts/configure-firewall.ps1 -WhatIf` | Wave 0 gap — script file |
| P10-T03 | `verify-firewall.ps1` exits 0 when rule is present | manual | `pwsh -File scripts/verify-firewall.ps1` | Wave 0 gap |
| P10-T04 | CI workflow file is valid YAML and all jobs present | static check | `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` | Wave 0 gap |
| P10-T04 | `pytest-cov` installed and coverage enforced at 70% | unit | `uv run pytest tests/unit/ --cov=backend --cov-fail-under=70 -q` | Partial — pytest-cov not yet in pyproject.toml |
| P10-T05 | `CADDY_ADMIN` bound to 127.0.0.1 not 0.0.0.0 | static check | `grep "CADDY_ADMIN=127.0.0.1" docker-compose.yml` | Wave 0 gap (file exists, wrong value) |
| P10-T05 | Caddy image has digest pin | static check | `grep "sha256:" docker-compose.yml` | Wave 0 gap |
| P10-T06 | No `>=` specifiers remain in `[project.dependencies]` | static check | `python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); [print(x) for x in d['project']['dependencies'] if '>=' in x]"` | Wave 0 gap |
| P10-T06 | `backend/requirements.txt` is deleted | filesystem check | `test ! -f backend/requirements.txt && echo "PASS"` | Wave 0 gap |
| P10-T07 | `generate()` writes to `llm_audit.jsonl` after call | unit | `uv run pytest tests/unit/test_ollama_audit.py -x` | Wave 0 gap |
| P10-T07 | `embed()` writes to `llm_audit.jsonl` after call | unit | `uv run pytest tests/unit/test_ollama_audit.py -x` | Wave 0 gap |
| P10-T08 | `configure-acls.ps1` exists and contains `icacls` | static check | `grep -c "icacls" scripts/configure-acls.ps1` | Wave 0 gap |
| P10-T09 | SQL injection payload in Sigma rule cannot escape query context | security | `uv run pytest tests/security/test_injection.py -x` | Wave 0 gap |
| P10-T09 | Injected event text has patterns stripped before embedding | security | `uv run pytest tests/security/test_injection.py -k "embedding" -x` | Wave 0 gap |
| P10-T10 | `REPRODUCIBILITY_RECEIPT.md` status is "VERIFIED" | static check | `grep "VERIFIED" REPRODUCIBILITY_RECEIPT.md` | Wave 0 gap |
| P10-T10 | No TBD entries remain in receipt | static check | `grep -c "TBD" REPRODUCIBILITY_RECEIPT.md` (expect 0) | Wave 0 gap |
| P10-T10 | ADR-019 present in `DECISION_LOG.md` | static check | `grep "ADR-019" DECISION_LOG.md` | Wave 0 gap |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ tests/security/ --cov=backend --cov=ingestion --cov-fail-under=70 -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_auth.py` — covers P10-T02 (valid token, missing token, wrong token)
- [ ] `tests/unit/test_ollama_audit.py` — covers P10-T07 (audit log entries for generate/embed)
- [ ] `tests/security/__init__.py` — directory marker
- [ ] `tests/security/test_injection.py` — covers P10-T09, P10-T01 integration
- [ ] `tests/security/test_auth.py` — covers P10-T02 endpoint enforcement
- [ ] `backend/core/auth.py` — required before any auth tests can run
- [ ] `.github/workflows/ci.yml` — required before CI verification
- [ ] Framework: `pytest-cov` install: `uv add --dev pytest-cov`

*(Injection tests in `test_normalizer.py` are partial — the file exists but injection test class is absent. Add injection test class to existing file rather than creating a new one.)*

---

## Sources

### Primary (HIGH confidence)
- Direct file audit: `ingestion/normalizer.py` — control char stripping confirmed present, injection scrubbing confirmed absent (lines 46-60, 126-165)
- Direct file audit: `backend/services/ollama_client.py` — no audit logging in `generate()` or `embed()` (lines 128-200, 206-266)
- Direct file audit: `backend/core/logging.py` — only `backend.jsonl` handler (lines 134-151)
- Direct file audit: `backend/main.py` — no `verify_token` wiring (lines 244-318)
- Direct file audit: `docker-compose.yml` — `CADDY_ADMIN=0.0.0.0:2019` confirmed (line 23); no digest pin (line 9)
- Direct file audit: `pyproject.toml` — 12 `>=` specifiers confirmed (lines 12-41)
- Direct file audit: `uv.lock` — exact versions for all relevant packages extracted
- Direct file audit: `REPRODUCIBILITY_RECEIPT.md` — status "BOOTSTRAPPING", 10 TBD entries (lines 1-7, 138-148)
- Direct filesystem check: `.github/` absent; `tests/security/` absent; `scripts/configure-firewall.ps1` absent; `backend/requirements.txt` present

### Secondary (MEDIUM confidence)
- FastAPI security dependency pattern (HTTPBearer) — standard FastAPI pattern, well-documented, consistent with existing `deps.py` Depends usage in project
- GitHub Actions astral-sh/setup-uv@v3 — current stable version per project's use of uv toolchain
- gitleaks vs trufflehog selection — gitleaks preferred per CONTEXT.md (single binary, no auth), consistent with community consensus for GitHub Actions

### Tertiary (LOW confidence — flag for validation)
- pip-audit chromadb advisory risk — inference from chromadb's known dependency complexity; actual advisory status requires `pip-audit` first run to verify
- 70% coverage achievability — current coverage not measured; requires baseline check before CI threshold enforcement

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions directly from uv.lock; all patterns from existing codebase
- Architecture: HIGH — auth pattern follows existing FastAPI Depends pattern; logging pattern follows existing RotatingFileHandler pattern
- Pitfalls: MEDIUM — most from direct code audit; pip-audit advisory risk is inference-level

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (stable domain — CI/CD and security hardening patterns are mature)
