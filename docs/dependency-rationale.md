# Dependency Rationale

Explains the purpose of every non-obvious runtime dependency in `pyproject.toml`.
Standard web-framework deps (fastapi, uvicorn, pydantic, httpx) are omitted.

Last audited: 2026-04-17

---

## AI / ML Dependencies

### `smolagents[litellm]>=1.24.0`
**Used by:** `backend/services/agent/runner.py`, `backend/services/agent/tools.py`
**Phase:** 45 — Agentic Investigation

The `ToolCallingAgent` from smolagents drives the 7-tool agentic investigation
pipeline (`POST /api/investigate/auto`). The `[litellm]` extra is required so
smolagents can proxy calls through LiteLLM to the local Ollama endpoint.
Direct httpx to Ollama is used for all non-agentic inference paths; smolagents
is *only* for the agentic pipeline where multi-step tool-calling logic is needed.

### `river>=0.21.0`
**Used by:** `backend/services/anomaly/scorer.py`, `backend/services/feedback/classifier.py`
**Phase:** 42 (anomaly scoring), 44 (feedback classifier)

River is an online machine learning library that trains incrementally without
storing the full dataset in memory. Two usages:
- `river.anomaly.HalfSpaceTrees` — streaming entity behavioral anomaly scoring
  (score trend sparklines in the dashboard)
- `river.linear_model.LogisticRegression` + `river.metrics.Accuracy` — analyst
  TP/FP feedback classifier that improves detection precision over time

Chosen over scikit-learn because it trains on each event as it arrives with
constant memory — appropriate for a desktop that may run for months without restart.

### `transformers>=4.40.0` (dev group)
**Used by:** `backend/services/reranker_service.py` (coverage-omitted standalone service)
**Phase:** 54 — HF Model Integration

The `BAAI/bge-reranker-v2-m3` cross-encoder reranker runs as a separate CUDA
process on `:8100`. It uses `transformers.AutoModelForSequenceClassification`
to score RAG candidate passages. Listed in the dev group because the main
`uv sync` installs it, but the actual CUDA torch wheel must be installed
separately (`pip install torch --index-url https://download.pytorch.org/whl/cu121`)
and is not listed in pyproject.toml to avoid pulling CPU torch into CI.

### `sentencepiece>=0.2.0` (dev group)
**Used by:** transformers tokeniser for bge-m3 / bge-reranker-v2-m3
**Phase:** 54

Required by the HuggingFace tokeniser for the bge family of models. Listed in
dev group alongside `transformers`.

### ~~`langgraph==1.1.2`~~ REMOVED
### ~~`langchain-ollama==1.0.1`~~ REMOVED

**Removal date:** 2026-04-17

Neither package was imported in any backend, ingestion, or test Python file.
All Ollama API calls use direct `httpx` async calls in `backend/services/ollama_client.py`.
The ARCHITECTURE.md anti-patterns section documents this decision: "LangChain chains —
Deprecated upstream. Direct httpx used instead." Both packages were vestigial
references from an earlier design that was superseded before Phase 1 landed.

---

## Threat Intelligence / Integration Dependencies

### `pymisp>=2.5.33.1`
**Used by:** `backend/services/intel/misp_sync.py`
**Phase:** 50 — MISP Threat Intelligence

The official MISP Python client. Used to pull IOC attributes from MISP
(running on the GMKtec box at `192.168.1.22:8443`) on a 6-hour sync cycle
and upsert them into DuckDB for IOC matching.

### `thehive4py==2.0.3`
**Used by:** `backend/services/thehive_client.py`, `backend/services/thehive_sync.py`
**Phase:** 52 — TheHive Case Management

The official TheHive Python client (v2 API). Used to auto-create cases in
TheHive from AI-SOC-Brain detections and push investigation artefacts.
Pinned to 2.0.3 because the v2 API surface differs materially from v1.

### `paramiko>=4.0.0`
**Used by:** Remote SSH utilities (Malcolm/GMKtec management)
**Phase:** 36+

SSH client used by management scripts that need to reach the GMKtec box
(e.g., Zeek log retrieval, Malcolm health checks). Not used in the FastAPI
request path.

### `dnstwist>=20250130`
**Used by:** `backend/services/dnstwist_service.py`
**Phase:** 33 — Threat Intelligence

Domain permutation engine. Used in the OSINT enrichment pipeline to generate
typosquat candidates for suspected attacker domains during investigations.

### `shodan==1.31.0`
**Used by:** `backend/services/osint.py`
**Phase:** 33 — Threat Intelligence

Shodan API client. Used for IP reputation enrichment when `SHODAN_API_KEY` is
configured. Gracefully degrades when no key is set.

### `geoip2==4.8.1`
**Used by:** `backend/services/osint.py`, `backend/api/metrics.py`
**Phase:** 41 — Threat Map

MaxMind GeoIP2 client. Used to geolocate IP addresses for the threat map
(`ThreatIntelView`) and for per-country attacker statistics in the metrics API.
Requires a local GeoLite2 database file.

### `python-whois==0.9.5`
**Used by:** `backend/services/osint.py`
**Phase:** 33 — Threat Intelligence

WHOIS lookup library. Used during OSINT investigation to fetch domain
registration details for suspicious domains found in events.

---

## Security / Auth Dependencies

### `passlib[bcrypt]>=1.7.4`
**Used by:** `backend/core/operator_utils.py`
**Phase:** 19 — Identity & RBAC

bcrypt password hashing for operator API keys stored in the `operators` table.
The `[bcrypt]` extra pulls in the native bcrypt C extension for timing-safe
hashing.

### `pyotp>=2.9`
**Used by:** `backend/core/totp_utils.py`
**Phase:** 23.5 — Security Hardening

TOTP/HOTP implementation for MFA on the legacy admin path and per-operator TOTP.
Replay protection is implemented in SQLite `system_kv` so codes cannot be reused
across restarts.

### `qrcode[pil]>=7.4`
**Used by:** `backend/api/operators.py` (TOTP QR code generation)
**Phase:** 23.5

Generates QR codes for TOTP onboarding in `SettingsView`. The `[pil]` extra
is required for PNG output.

---

## Scheduling / Rate Limiting

### `apscheduler==3.11.2`
**Used by:** `backend/startup/workers.py`
**Phase:** 27, 33, 35

Background scheduler for Malcolm telemetry polling (every 30s), IOC feed
refresh (every 6h), and metrics aggregation jobs. AsyncIOScheduler is used
so jobs share the FastAPI event loop without spawning extra threads.

### `slowapi==0.1.9`
**Used by:** `backend/core/rate_limit.py`
**Phase:** 10 — Compliance Hardening

Rate limiting middleware for the FastAPI app. Wraps `limits` library with
Starlette/FastAPI integration. Applied to auth-sensitive endpoints to prevent
brute-force attacks.

---

## Reporting

### `weasyprint>=68.1`
**Used by:** `backend/api/reports.py`
**Phase:** 18 — Reporting & Compliance

Renders HTML/CSS incident reports to PDF. Chosen because it runs entirely
locally with no external service calls, produces compliant PDF/A output, and
handles the MITRE ATT&CK heatmap SVG correctly.

---

## Data Seeding

### `datasets>=2.21.0`
**Used by:** `scripts/seed_siem_data.py` (not a backend runtime path)
**Phase:** 8

HuggingFace datasets client. Used only in the `seed_siem_data.py` script to
pull synthetic SIEM event data from HuggingFace Hub for development seeding.
Not imported in any backend module. Kept in main dependencies (not dev group)
so the seed script works in production deployments without a `--group dev` install.

---

## Detection

### `pySigma==1.2.0`
**Used by:** `detections/matcher.py`, `detections/field_map.py`
**Phase:** 3 — Detection + RAG

Sigma rule parser and compiler. A custom DuckDB SQL backend was written because
no mature DuckDB backend exists upstream. `from sigma.collection import SigmaCollection`
is the import path — NOT `from pySigma`.

### `PyYAML==6.0.3`
**Used by:** Detection rule loading, playbook parsing

YAML parser for Sigma rules and playbook YAML files.

---

## Ingestion

### `evtx==0.11.0`
**Used by:** `ingestion/parsers/evtx_parser.py`
**Phase:** 2 — Ingestion

Rust-backed Python binding for reading Windows EVTX (Event Log) binary files.
Chosen over pure-Python alternatives for speed and correctness with malformed
records.
