# AI-SOC-Brain

Local Windows desktop AI cybersecurity investigation platform.

Phase 7 complete — ingestion, detection, graph correlation, causality engine,
threat hunting, case management, Svelte 5 dashboard.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12 | `uv python install 3.12` |
| uv | 0.10+ | `winget install astral-sh.uv` |
| Node.js | 18+ LTS | `winget install OpenJS.NodeJS.LTS` |
| Docker Desktop | Latest | https://docs.docker.com/desktop/install/windows-install/ |
| **PowerShell 7** | **7.0+** | **`winget install Microsoft.PowerShell`** |
| Ollama | 0.13+ | `winget install Ollama.Ollama` |

> PowerShell 7 (pwsh) is required to run the management scripts.
> Windows ships with PS 5.1 by default — install PS7 separately.

## Quick Start

```powershell
git clone <repo-url> AI-SOC-Brain
cd AI-SOC-Brain
uv venv --python 3.12
.venv\Scripts\activate
uv pip install -r requirements.lock
scripts\start.cmd        # starts FastAPI + Caddy
```

Open https://localhost in your browser.

## Management Scripts

| Script | Description |
|--------|-------------|
| `scripts\start.cmd` | Start FastAPI backend + Caddy Docker container |
| `scripts\stop.cmd` | Stop all services |
| `scripts\status.cmd` | Show service health |

Run `scripts\start.cmd` (works from cmd.exe or PS 5.1 — auto-invokes pwsh).
Run `pwsh -File scripts\start.ps1` directly if you already have PS7.

## Development

```powershell
uv run pytest          # Python test suite
cd frontend && npm run dev   # Svelte dev server (http://localhost:5173)
```

See [REPRODUCIBILITY_RECEIPT.md](REPRODUCIBILITY_RECEIPT.md) for full setup steps.
See [ARCHITECTURE.md](ARCHITECTURE.md) for system design.
