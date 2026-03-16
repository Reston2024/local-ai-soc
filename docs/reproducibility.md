# Reproducibility Guide

## Phase 2 Ingestion — AI SOC Brain

Branch: `feature/ai-soc-phase2-ingestion`
Date: 2026-03-15
(includes all Wave 1 foundation commands)

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
# All tests — Wave 1 + Phase 2 (no running server needed — uses TestClient)
cd C:\Users\Admin\AI-SOC-Brain
uv run pytest backend/src/tests/ -v
# Expected: 32 passed (7 Wave 1 + 25 Phase 2)

# Wave 1 only
uv run pytest backend/src/tests/smoke_test.py -v
# Expected: 7 passed

# Phase 2 only
uv run pytest backend/src/tests/test_phase2.py -v
# Expected: 25 passed
```

---

## Phase 2 Ingestion Commands

```powershell
# Batch ingest via /ingest
$payload = @{
    source = "api"
    events = @(
        @{ timestamp = "2026-03-15T12:00:00Z"; host = "fw01"; src_ip = "192.168.1.10"; dst_ip = "9.9.9.9"; event = "connection"; port = 4444 }
    )
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post http://localhost:8000/ingest -Body $payload -ContentType "application/json"
# Expected: {"accepted":1,"alerts":2,"source":"api"}

# Ingest raw syslog line
$syslogLine = "<34>Mar 15 12:00:00 fw01 connection established from 192.168.1.10"
Invoke-RestMethod -Method Post http://localhost:8000/ingest/syslog -Body $syslogLine -ContentType "text/plain"
# Expected: {"accepted":1,"alerts":0,"event_id":"<uuid>"}

# Ingest CEF line
$cef = "CEF:0|PAN|PAN-OS|10.1|threat|Suspicious DNS|8|src=10.0.0.5 dst=9.9.9.9 dpt=53"
Invoke-RestMethod -Method Post http://localhost:8000/ingest/syslog -Body $cef -ContentType "text/plain"
# Expected: {"accepted":1,"alerts":1,"event_id":"<uuid>"}

# Connect SSE stream (PowerShell — streams until Ctrl+C)
# Best tested via browser: open http://localhost:8000/events/stream

# Send live syslog to Vector UDP (requires full Docker stack)
echo "<34>Mar 15 12:00:00 fw01 Suspicious DNS query to c2.evil.test" | nc -u localhost 514
```

---

## Enable OpenSearch Indexing (SCAFFOLD)

```powershell
# 1. Start with OPENSEARCH_URL set (adds indexing from backend)
$env:OPENSEARCH_URL = "http://opensearch:9200"
# Then restart backend container or set in docker-compose.yml environment section

# 2. Verify index created after ingesting events
Invoke-RestMethod http://localhost:9200/soc-events/_count
# Expected: {"count": N, ...}

# 3. Query index
Invoke-RestMethod "http://localhost:9200/soc-events/_search?q=host:fw01"
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

---

## Phase 5: Suricata EVE Parsing + Threat Scoring + ATT&CK Tagging — 2026-03-16

Branch: `feature/ai-soc-phase3-detection`

### Test fixture validation

```bash
# Verify fixture has 5 lines (one per EVE event type)
wc -l fixtures/suricata_eve_sample.ndjson
# Expected: 5

# Verify each line is valid JSON and inspect event types
python -c "
import json
with open('fixtures/suricata_eve_sample.ndjson') as f:
    for i, line in enumerate(f, 1):
        obj = json.loads(line)
        print(f'Line {i}: event_type={obj.get(\"event_type\")}')
"
# Expected output:
# Line 1: event_type=alert
# Line 2: event_type=dns
# Line 3: event_type=flow
# Line 4: event_type=http
# Line 5: event_type=tls
```

### Parser validation

```bash
# Verify dest_ip → dst_ip mapping (the critical Snort convention trap)
python -c "
from backend.src.parsers.suricata_parser import parse_eve_line
import json
line = json.dumps({'event_type':'flow','timestamp':'2026-03-16T00:00:00Z','host':'sensor','src_ip':'1.2.3.4','src_port':1234,'dest_ip':'5.6.7.8','dest_port':4444,'proto':'TCP','flow':{}})
result = parse_eve_line(line)
assert result['dst_ip'] == '5.6.7.8', f'FAIL: dst_ip={result.get(\"dst_ip\")}'
print('PASS: dest_ip correctly mapped to dst_ip')
"

# Verify severity inversion (1=critical, not 1=low — Snort convention)
python -c "
from backend.src.parsers.suricata_parser import parse_eve_line
import json
line = json.dumps({'event_type':'alert','timestamp':'2026-03-16T00:00:00Z','host':'sensor','src_ip':'1.1.1.1','dest_ip':'2.2.2.2','alert':{'signature':'Test','severity':1,'category':'Test'}})
result = parse_eve_line(line)
assert result['severity'] == 'critical', f'FAIL: severity={result.get(\"severity\")}'
print('PASS: severity=1 correctly maps to critical')
"
```

### Scoring model validation

```bash
uv run pytest backend/src/tests/test_phase5.py::TestThreatScorer -v
# Expected: 3 tests PASS (score_critical, score_sigma_hit, score_capped)
```

### ATT&CK tagging validation

```bash
uv run pytest backend/src/tests/test_phase5.py::TestAttackMapper -v
# Expected: 2 tests PASS (dns→c2, unmapped→[])
```

### Full Phase 5 suite

```bash
uv run pytest backend/src/tests/test_phase5.py -v
# Expected: 18 tests PASS, 0 FAIL, 0 ERROR
```

### Regression gate

```bash
uv run pytest backend/src/tests/ -v --tb=no -q
# Expected: 59 tests PASS (41 existing + 18 phase5), 0 FAIL
```

### GET /threats endpoint validation

```bash
# Load fixtures then check /threats endpoint
curl -s http://localhost:8000/threats | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'Threats returned: {len(data)}')
for t in data[:3]:
    print(f'  score={t.get(\"threat_score\", 0)} rule={t.get(\"rule\", \"?\")} tags={len(t.get(\"attack_tags\", []))}')
"
# Expected: alerts with threat_score > 0, sorted descending
