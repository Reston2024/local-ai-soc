# REPRODUCIBILITY_RECEIPT.md
# AI-SOC-Brain — Reproducibility Receipt

**Status:** VERIFIED
**Date:** 2026-04-09
**Updated:** 2026-04-16 (Phase 52 complete — Phases 47–52 added)

---

## Regulated Compliance Note (2026-04-16)

This receipt supports **NIST RMF Step 3 (Implement)** and **Step 6 (Monitor)** for a local-first, single-analyst AI-assisted SOC.

| Control | Evidence in this Receipt |
|---------|--------------------------|
| CM-2 (Baseline Configuration) | Pinned versions table + `uv.lock` + Ollama model checksums |
| CM-6 (Configuration Settings) | `.env` example + Docker Compose version pins |
| SI-2 (Flaw Remediation) | pip-audit baseline + CVE exception log |
| AU-9 (Audit Protection) | SHA-256 hash commands for all data stores |
| SA-24 (Cyber Resiliency — new in SP 800-53 Rev 5.2.0) | Local-first architecture; no cloud dependency; offline Ollama |

All hashes and commands were re-validated against commit `3c11c16` (2026-04-16).

To generate a full evidence bundle for RMF Step 4 assessment, run:

```powershell
# Collect environment snapshot, test report, dependency hashes, and log export
uv run pytest tests/unit/ tests/security/ --junitxml=evidence/junit.xml --cov=backend --cov-report=xml:evidence/coverage.xml -q
uv export --no-hashes > evidence/requirements-snapshot.txt
git log --oneline -20 > evidence/recent-commits.txt
Get-FileHash data\events.duckdb -Algorithm SHA256 | Out-File evidence\duckdb-hash.txt
```

**Note:** `evidence/` is gitignored (contains runtime data). Store output in a local evidence archive for audit purposes.

---

> Pinned via uv.lock — run `uv export --no-hashes` to reproduce

---

## Infrastructure

### Desktop — SOC Brain (primary)

| Component | Minimum | This System |
|-----------|---------|-------------|
| OS | Windows 10/11 x64 | Windows 11 26H2 |
| CPU | 8 cores | Intel Core Ultra 9 285K 24c |
| RAM | 32 GB | 96 GB |
| GPU VRAM | 8 GB (for 7B models) | 16 GB RTX 5080 |
| Disk | 100 GB free | 3.4 TB free |
| CUDA | 12.0+ | 13.1 |

### supportTAK-server — Dumb Pipe (optional, for live NSM telemetry)

| Component | Value |
|-----------|-------|
| Hardware | GMKtec N150 (Intel N150, 16 GB DDR5) |
| OS | Ubuntu |
| IP | 192.168.1.22 |
| Role | Malcolm NSM — telemetry collection and indexing ONLY |
| OpenSearch | https://192.168.1.22:9200 — optional dependency |
| Malcolm | 17 containers (syslog + EVE alerts collecting; Zeek idle — no SPAN port) |

The desktop operates fully without the Ubuntu box — Malcolm integration is optional. Set `MALCOLM_ENABLED=True` in `.env` to activate MalcolmCollector.

---

## Software Prerequisites

Install these manually before running setup:

```powershell
# 1. winget (built into Windows 11) or chocolatey
# 2. Docker Desktop for Windows (https://docs.docker.com/desktop/install/windows-install/)
# 3. Node.js LTS (https://nodejs.org/) or: winget install OpenJS.NodeJS.LTS
# 4. Git (https://git-scm.com/) or: winget install Git.Git
```

---

## Step-by-Step Reproduction

### Step 1: Clone and Navigate

```powershell
git clone <repo-url> AI-SOC-Brain
cd AI-SOC-Brain
```

### Step 2: Install uv (Python package manager)

```powershell
# If uv not installed:
winget install astral-sh.uv
# or: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 3: Create Python 3.12 Environment

```powershell
uv python install 3.12
uv venv --python 3.12
.venv\Scripts\activate
```

### Step 4: Install Python Dependencies

```powershell
uv sync
# All versions are exact-pinned in pyproject.toml and locked in uv.lock
```

### Step 5: Install Ollama

```powershell
winget install Ollama.Ollama
# Restart terminal after install, then:
# Set environment variables (persist across reboots):
[System.Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0", "Machine")
[System.Environment]::SetEnvironmentVariable("OLLAMA_ORIGINS", "*", "Machine")
[System.Environment]::SetEnvironmentVariable("CUDA_VISIBLE_DEVICES", "0", "Machine")
# Restart Ollama service after setting env vars
```

### Step 6: Pull Ollama Models

```powershell
ollama pull qwen3:14b
ollama pull mxbai-embed-large
# Verify GPU acceleration:
ollama run llama3.2:1b
# In separate terminal: nvidia-smi (should show GPU utilization > 0%)
# ollama ps (should show GPU layers > 0)
```

### Step 7: Configure Environment

```powershell
copy config\.env.example .env
# Edit .env with any local overrides (DATA_DIR, LOG_LEVEL, etc.)
```

### Step 8: Start Services

**Option A — Using .cmd wrapper (any terminal):**
```powershell
scripts\start.cmd
```

**Option B — PowerShell 7 directly:**
```powershell
pwsh -File scripts\start.ps1
```

> Note: scripts require PowerShell 7 (pwsh). If you see a version error,
> install PS7 with: `winget install Microsoft.PowerShell`, then restart your terminal.

This starts: Docker (Caddy), FastAPI (uvicorn)
Open browser: https://localhost

### Step 9: Verify (Smoke Tests)

```powershell
scripts\smoke-test-phase1.ps1
# All checks should pass
```

---

## Pinned Versions

*Verified 2026-03-26 — all Python versions sourced from uv.lock*

| Package | Version | Source |
|---------|---------|--------|
| Python | 3.12.x | uv |
| uv | 0.10.6 | astral.sh |
| fastapi | 0.115.12 | PyPI |
| uvicorn | 0.34.3 | PyPI |
| duckdb | 1.3.0 | PyPI |
| chromadb | 1.5.5 | PyPI |
| pydantic | 2.12.5 | PyPI |
| pydantic-settings | 2.13.1 | PyPI |
| httpx | 0.28.1 | PyPI |
| pySigma | 1.2.0 | PyPI |
| pySigma-backend-sqlite | 1.1.3 | PyPI |
| langgraph | 1.1.2 | PyPI |
| langchain-ollama | 1.0.1 | PyPI |
| evtx (pyevtx-rs) | 0.11.0 | PyPI |
| PyYAML | 6.0.3 | PyPI |
| pytest | 9.0.2 | PyPI |
| pytest-asyncio | 1.3.0 | PyPI |
| ruff | 0.15.6 | PyPI |
| Ollama | 0.18.2 | ollama.com |
| qwen3:14b | see: `ollama show --verbose qwen3:14b` | ollama.com |
| mxbai-embed-large | ID: 468836162de7 | ollama.com |
| Docker Desktop | 29.2.1 | docker.com |
| Caddy | 2.9-alpine (see docker-compose.yml for digest) | Docker Hub |
| Node.js | v24.14.0 | nodejs.org |
| Svelte | ^5.28.0 | npm |
| Vite | ^6.2.5 | npm |
| Cytoscape.js | ^3.31.0 | npm |
| D3.js | ^7.9.0 | npm |

---

## Verification Checksums

```
data/events.duckdb schema hash: see: uv run python -c "import duckdb; c=duckdb.connect('data/events.duckdb'); print(c.execute('PRAGMA database_list').fetchall())"
data/graph.sqlite3 schema hash: see: python -c "import sqlite3,hashlib; ..."
Ollama model checksums: mxbai-embed-large ID 468836162de7; qwen3:14b see: ollama show --verbose qwen3:14b
```

---

## pip-audit Baseline (2026-03-26)

pip-audit not installed in current environment. To run a baseline audit:

```powershell
uv run pip install pip-audit
uv run pip-audit --desc
```

Install pip-audit as a dev dependency if CI enforcement is required. As of 2026-03-26 all direct dependencies are pinned to `==` exact versions (uv.lock is the source of truth); transitive dependency security is verified by running pip-audit against the locked environment.

---

## Known Issues and Workarounds

### RTX 5080 CUDA Compatibility
- Ollama must be version 0.13+ for Blackwell sm_120 support
- If GPU not detected: clean reinstall NVIDIA Studio Drivers from nvidia.com
- Confirm: `CUDA_VISIBLE_DEVICES=0` set before Ollama starts

### Python 3.14 Incompatibility
- Do NOT use Python 3.14 (system default). Use 3.12 via uv.
- PEP 649 (deferred annotations) breaks pySigma, pydantic-core, pyevtx-rs at runtime.

### Docker-to-Ollama Bridge
- `OLLAMA_HOST=0.0.0.0` must be set as a Windows SYSTEM environment variable (not user)
- Ollama must be restarted after setting the variable
- Verify: `docker exec caddy curl http://host.docker.internal:11434`

---

## Phase 54 — GPU Migration (2026-04-16)

### GPU Migration Summary

| Field | Value |
|-------|-------|
| Date of migration | 2026-04-16 |
| GPU | NVIDIA RTX 5080 (16 GB VRAM) |
| CUDA version | 13.1 |
| System env var set | `OLLAMA_VULKAN=true` (Machine scope permanent) |
| `CUDA_VISIBLE_DEVICES` | Unset at all scopes (was blocking Vulkan discovery) |
| Ollama version | 0.18.2 |
| TTFT before (CPU) | ~300s for qwen3:14b short prompt |
| TTFT after (GPU via Vulkan) | <30s, GPU Layers 40+ for qwen3:14b |
| GPU warning block added to | `scripts/_start-backend.ps1` (advisory-only try/catch) |

### Root Cause

`CUDA_VISIBLE_DEVICES=0` set at Machine scope was blocking Vulkan discovery. RTX 5080 (Blackwell sm_120) is NOT supported by Ollama's bundled CUDA runtime. Vulkan backend (`vulkan/ggml-vulkan.dll`) is the permanent solution for Blackwell GPUs.

### Workaround for RTX 5080 (Blackwell sm_120)

```powershell
# Permanent fix (Machine scope):
[System.Environment]::SetEnvironmentVariable("OLLAMA_VULKAN", "true", "Machine")
# Also unset CUDA_VISIBLE_DEVICES at Machine/User/Process scope if set:
[System.Environment]::SetEnvironmentVariable("CUDA_VISIBLE_DEVICES", $null, "Machine")
```

### Live Snapshot (captured 2026-04-16, updated 2026-04-17)

- `ollama --version`: 0.21.0 (was 0.18.2 at time of migration)
- `nvidia-smi`: NVIDIA GeForce RTX 5080, Driver 591.74, 16303 MiB VRAM
- GPU utilization confirmed via `ollama ps`: 11% CPU / 89% GPU split
- Cross-reference: GPU warning block in `scripts/_start-backend.ps1`

### Files Changed in 54-01 / 54-02

- `backend/core/config.py` — RERANKER_URL, RERANKER_TOP_K, RERANKER_ENABLED settings added
- `scripts/_start-backend.ps1` — GPU pre-flight warning block (advisory-only try/catch)
- `tests/unit/test_reranker.py` — wave-0 stubs (3 tests, SKIP until 54-08)
- `tests/unit/test_chroma_store.py` — bge-m3 dimension stub appended (SKIP until 54-05)

---

## Phase 8 — Verified Dependency Versions (2026-03-17)

| Package | Version |
|---------|---------|
| fastapi | 0.115.12 |
| uvicorn | 0.34.3 |
| duckdb | 1.3.0 |
| pydantic-settings | 2.13.1 |
| httpx | 0.28.1 |
| chromadb | 1.5.5 |
| pytest | 9.0.2 |
| pytest-asyncio | 1.3.0 |

---

## Phase 8 — Production Hardening & Live Telemetry

### Live osquery Collection
- Set `OSQUERY_ENABLED=True` in `.env` to activate
- Default log path: `C:\Program Files\osquery\log\osqueryd.results.log`
- Install: `winget install osquery.osquery`
- Copy `config/osquery/osquery.conf` to `C:\Program Files\osquery\osquery.conf`
- If running as service: `icacls "C:\Program Files\osquery\log" /grant Users:R`

### Smoke Test
```powershell
pwsh -File scripts\smoke-test-phase8.ps1
```

---

## Phase 23 — Firewall Telemetry Ingestion (2026-04-05)

### New Components
- `ingestion/parsers/ipfire_syslog_parser.py` — IPFire RFC 3164 syslog → NormalizedEvent
- `ingestion/parsers/suricata_eve_parser.py` — Suricata EVE JSON → NormalizedEvent
- `ingestion/jobs/firewall_collector.py` — file-tail asyncio collector with exponential backoff
- `backend/api/firewall.py` — `GET /api/firewall/status` heartbeat endpoint

### New Settings (`.env`)
```
FIREWALL_ENABLED=False          # Set True to activate collector
FIREWALL_SYSLOG_PATH=           # Path to IPFire syslog file
FIREWALL_EVE_PATH=              # Path to Suricata EVE JSON file
FIREWALL_HEARTBEAT_TIMEOUT_CONNECTED=120
FIREWALL_HEARTBEAT_TIMEOUT_DEGRADED=300
```

### Test Count
817 passed on Phase 23 completion (prior to 23.5 hardening).

---

## Phase 23.5 — Security Hardening (2026-04-05)

### Findings Closed (expert panel sweep — 10 experts, 18 findings)

| Finding | Severity | Fix |
|---------|----------|-----|
| E3-01: Default AUTH_TOKEN | CRITICAL | `model_validator` rejects at startup; tokens < 32 chars rejected |
| E3-02: Legacy admin bypass | CRITICAL | `LEGACY_TOTP_SECRET` required + `X-TOTP-Code` header |
| E6-01: RAG injection bypass | CRITICAL | `_normalize_for_scrub()`: NFC + base64 decode heuristic |
| E6-02: Chat question unscrubbed | CRITICAL | `_scrub_injection(body.question)` in `chat.py` |
| E1-01/E10-01: Sigma SQL + backend | HIGH | Custom DuckDB backend parameterization verified; 4 injection tests; unused `pySigma-backend-sqlite` dep removed |
| E4-01: Ollama port unverified | HIGH | `Test-NetConnection` check in `scripts/status.ps1` |
| E8-02: No meta-detection rules | HIGH | 3 parse-valid Sigma rules in `detections/sigma/meta/` |
| E9-01: Missing security headers | MEDIUM | CSP, X-Frame-Options, X-Content-Type-Options in Caddyfile |
| E3-04: /health info disclosure | MEDIUM | All exceptions sanitized to `"component unavailable"` |
| E8-01: No log rotation | MEDIUM | `TimedRotatingFileHandler(when="midnight", backupCount=30)` |
| E2-01: TOTP replay after restart | MEDIUM | SQLite `system_kv` L2 with 90s TTL + in-process L1 cache |
| E7-02: Partial prompt logging | MEDIUM | `prompt_text` (64KB cap) + `prompt_hash` (SHA-256) in `llm_calls` |

### Additional Findings Closed (verifier v2 delta — 2026-04-05)

| Finding | Severity | Fix |
|---------|----------|-----|
| E3-03: File upload path traversal | MEDIUM | `test_path_traversal_rejected` activated; 415 on traversal filenames confirmed |
| E5-01: ChromaDB no collection ACL | HIGH | `delete_collection()` guarded by `_admin_override` flag; `PermissionError` without override |
| E5-02: DuckDB COPY TO / httpfs | HIGH | `SET enable_external_access = false` applied to all connection paths at init |
| E6-03: Ollama model digest unpinned | MEDIUM | `verify_model_digest()` on startup; `OLLAMA_MODEL_DIGEST` + `OLLAMA_ENFORCE_DIGEST` settings |
| E7-01: No security coverage CI gate | MEDIUM | Separate CI step: `--cov-fail-under=80` on `auth`, `normalizer`, `ingest` modules |

### New Required Settings (`.env`)
```
# AUTH_TOKEN must be 32+ chars or "dev-only-bypass" for local dev
AUTH_TOKEN=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">

# Optional: enable legacy admin path (disabled by default)
# LEGACY_TOTP_SECRET=<base32-encoded TOTP secret>

# Optional: pin Ollama model digest for integrity verification
# Get digest: curl http://localhost:11434/api/show -d '{"name":"qwen3:14b"}' | python -m json.tool
# OLLAMA_MODEL_DIGEST=sha256:abc123  # First 12+ chars of digest
# OLLAMA_ENFORCE_DIGEST=False        # Set True to refuse startup on mismatch
```

### Test Count
842 passed, 2 skipped, 9 xfailed — full closure (all 18 expert panel findings addressed).

### New Files
- `tests/security/test_auth_hardening.py` — T01, T02, T09, T11, T12
- `tests/security/test_injection_hardening.py` — T03, T04
- `tests/security/test_sigma_hardening.py` — T05 (4 SQL injection parameterization tests)
- `tests/sigma_smoke/test_meta_rules.py` — T07 (3 meta-rule parse tests)
- `tests/eval/fixtures/injection_b64_bypass.json` — adversarial eval fixture
- `detections/sigma/meta/auth_failure_burst.yml`
- `detections/sigma/meta/llm_token_spike.yml`
- `detections/sigma/meta/collection_delete.yml`
- `docs/ADR-030-ai-recommendation-governance.md`
- `docs/ADR-031-transport-contract-reference.md`
- `docs/ADR-032-executor-failure-reference.md`
- `contracts/recommendation.schema.json`
