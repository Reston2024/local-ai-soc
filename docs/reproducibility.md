# Reproducibility Guide

## Wave 1 Foundation — AI SOC Brain

Branch: `feature/ai-soc-wave1-foundation`
Date: 2026-03-15

---

## Prerequisites

- Docker Desktop (Windows)
- Node.js 22+
- Python 3.12 (via uv: `uv venv --python 3.12`)
- PowerShell 7+

---

## Build & Start Stack

```powershell
# 1. Clone / checkout branch
git checkout feature/ai-soc-wave1-foundation

# 2. Build frontend
cd frontend
npm install
npm run build
cd ..

# 3. Start full stack
cd infra
docker compose up -d --build

# 4. Verify all services are up
docker compose ps
```

---

## Load Fixtures

```powershell
# Option A: Direct API call
Invoke-RestMethod -Method Post http://localhost:8000/fixtures/load

# Option B: Via Caddy HTTPS proxy (use -SkipCertificateCheck for self-signed)
Invoke-RestMethod -Method Post https://localhost/fixtures/load -SkipCertificateCheck

# Option C: curl
curl -X POST http://localhost:8000/fixtures/load
```

---

## Verify Endpoints

```powershell
# Health check
Invoke-RestMethod http://localhost:8000/health
# Expected: {"status":"ok"}

# Via Caddy (HTTPS)
Invoke-RestMethod https://localhost/health -SkipCertificateCheck
# Expected: {"status":"ok"}

# Events (after loading fixtures)
Invoke-RestMethod http://localhost:8000/events
# Expected: JSON array of 6 events

# Timeline
Invoke-RestMethod http://localhost:8000/timeline
# Expected: same events sorted by timestamp

# Graph
Invoke-RestMethod http://localhost:8000/graph
# Expected: {"nodes":[...],"edges":[...]}

# Alerts
Invoke-RestMethod http://localhost:8000/alerts
# Expected: JSON array (alerts generated from suspicious events)

# OpenSearch (scaffold — may not be fully indexed in Wave 1)
Invoke-RestMethod http://localhost:9200
```

---

## Run Smoke Tests

```bash
# Python smoke tests (no running server needed — uses TestClient)
cd C:\Users\Admin\AI-SOC-Brain
uv run pytest backend/src/tests/smoke_test.py -v
```

---

## Expected URLs

| Service | URL |
|---------|-----|
| Frontend (via Caddy HTTPS) | https://localhost |
| Frontend (direct) | http://localhost:5173 |
| Backend health | http://localhost:8000/health |
| Backend via Caddy | https://localhost/health |
| OpenSearch | http://localhost:9200 |

> **Note:** https://localhost uses Caddy's self-signed `tls internal` certificate.
> Browser will show a warning on first visit — accept it or use `-SkipCertificateCheck` in PowerShell.

---

## Stop Stack

```powershell
cd infra
docker compose down

# To also remove volumes (resets OpenSearch data):
docker compose down -v
```
