# REPRODUCIBILITY_RECEIPT.md
# AI-SOC-Brain — Reproducibility Receipt

**Status:** BOOTSTRAPPING — will be updated as Phase 1 completes
**Date:** 2026-03-15

---

## Hardware Requirements

| Component | Minimum | This System |
|-----------|---------|-------------|
| OS | Windows 10/11 x64 | Windows 11 26H2 |
| CPU | 8 cores | Intel Core Ultra 9 285K 24c |
| RAM | 32 GB | 96 GB |
| GPU VRAM | 8 GB (for 7B models) | 16 GB RTX 5080 |
| Disk | 100 GB free | 3.4 TB free |
| CUDA | 12.0+ | 13.1 |

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
uv pip install -r requirements.lock
# or: uv sync (if using pyproject.toml with lockfile)
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

```powershell
scripts\start.ps1
# This starts: Docker (Caddy), FastAPI (uvicorn)
# Open browser: https://localhost
```

### Step 9: Verify (Smoke Tests)

```powershell
scripts\smoke-test-phase1.ps1
# All checks should pass
```

---

## Pinned Versions

*To be updated as packages are installed and locked*

| Package | Version | Source |
|---------|---------|--------|
| Python | 3.12.x | uv |
| uv | 0.10.6 | astral.sh |
| fastapi | TBD | PyPI |
| uvicorn | TBD | PyPI |
| duckdb | 1.5.0 | PyPI |
| chromadb | TBD | PyPI |
| pydantic | TBD | PyPI |
| httpx | TBD | PyPI |
| pySigma | TBD | PyPI |
| langgraph | TBD | PyPI |
| evtx (pyevtx-rs) | TBD | PyPI |
| Ollama | TBD | ollama.com |
| qwen3:14b | TBD | ollama.com |
| mxbai-embed-large | TBD | ollama.com |
| Docker Desktop | TBD | docker.com |
| Caddy | 2.9+ | Docker Hub |
| Node.js | v24.14.0 | nodejs.org |
| Svelte | TBD | npm |
| Cytoscape.js | TBD | npm |
| D3.js | TBD | npm |

---

## Verification Checksums

*To be populated after initial build*

```
data/events.duckdb schema hash: TBD
data/graph.sqlite3 schema hash: TBD
Ollama model checksums: TBD
```

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
