---
phase: 03-detection-rag
verified: 2026-03-15T00:00:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
human_verification:
  - test: "docker compose up -d --build starts cleanly with OpenSearch health gate"
    expected: "Backend service starts only after opensearch returns service_healthy; curl http://localhost:8000/health returns {\"status\":\"ok\"}"
    why_human: "Requires a running Docker daemon and JVM startup time; cannot verify programmatically in this environment"
  - test: "GET /search?q=suspicious-domain.test returns results after live event ingest"
    expected: "After POSTing a suspicious DNS event and waiting for indexing, the /search endpoint returns at least one matching document from the soc-events index"
    why_human: "Requires a live OpenSearch instance; endpoint returns [] gracefully when OS is unavailable, so the happy-path requires manual end-to-end verification"
---

# Phase 3: Detection + RAG Verification Report

**Phase Goal:** OpenSearch live indexing + Sigma YAML detection rules surfaced in /alerts. Keep all 32 existing tests passing.
**Verified:** 2026-03-15
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | test_phase3.py exists with stubs for all Phase 3 behaviors (Nyquist gate) | VERIFIED | `backend/src/tests/test_phase3.py` — 222 lines, 9 test methods across 5 classes |
| 2 | try_index() always attempts HTTP PUT when OPENSEARCH_URL is set (guard removed from docker-compose level) | VERIFIED | `opensearch_sink.py` retains URL guard for broken-URL protection only; docker-compose sets `OPENSEARCH_URL=http://opensearch:9200` unconditionally; P3-T8 passes |
| 3 | GET /search?q= endpoint returns a JSON array (gracefully [] when OpenSearch unavailable) | VERIFIED | `@router.get("/search")` at routes.py:116-150; P3-T1, P3-T2 both pass |
| 4 | docker-compose.yml backend service sets OPENSEARCH_URL and depends_on opensearch service_healthy | VERIFIED | `OPENSEARCH_URL=http://opensearch:9200` at line 13; `depends_on: opensearch: condition: service_healthy` at lines 20-22 |
| 5 | infra/vector/vector.yaml opensearch_events sink active with fixed index soc-events | VERIFIED | `opensearch_events:` uncommented at lines 139-146; `index: "soc-events"` (no date suffix) |
| 6 | backend/src/detection/sigma/suspicious_dns.yml exists with valid UUID id field | VERIFIED | UUID `d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f9a`, `detection:` block, `query|contains` matching all 3 suspicious domains |
| 7 | sigma_loader.load_sigma_rules() returns a list of at least 1 callable | VERIFIED | `sigma_loader.py` — 148 lines, `load_sigma_rules()` exported; P3-T3 passes |
| 8 | Sigma matches produce Alert objects visible in GET /alerts (rule field = UUID from YAML) | VERIFIED | `_SIGMA_RULES` wired in routes.py `_store_event`; P3-T4, P3-T5, P3-T6 all pass |
| 9 | All 32 existing tests continue to pass (41 total with Phase 3 tests) | VERIFIED | `uv run pytest backend/src/tests/` — 41 passed in 0.24s |

**Score:** 9/9 truths verified

---

## Required Artifacts

| Artifact | Description | Status | Details |
|----------|-------------|--------|---------|
| `backend/src/tests/test_phase3.py` | 9 test stubs covering all Phase 3 behaviors | VERIFIED | 222 lines; 9 methods; all 9 pass |
| `backend/src/ingestion/opensearch_sink.py` | Unconditional try_index — no env-var guard blocking docker-compose | VERIFIED | 67 lines; `def try_index` present; OPENSEARCH_URL guard retained only for broken-URL prevention |
| `backend/src/api/routes.py` | GET /search endpoint + _SIGMA_RULES integration | VERIFIED | `@router.get("/search")` at line 116; `_SIGMA_RULES` at line 44; `sigma_loader` import at line 23 |
| `infra/docker-compose.yml` | OPENSEARCH_URL env var + healthcheck-gated depends_on | VERIFIED | Lines 13, 20-22, 47-52 confirm all three changes |
| `infra/vector/vector.yaml` | Active opensearch_events sink writing to soc-events index | VERIFIED | Lines 139-146; `type: elasticsearch`; `index: "soc-events"` |
| `backend/src/detection/sigma/suspicious_dns.yml` | Sigma rule matching query|contains on suspicious domains | VERIFIED | Valid YAML; UUID id; all 3 domains from enricher.py; level: high |
| `backend/src/detection/sigma_loader.py` | load_sigma_rules() returning list of NormalizedEvent -> Alert callables | VERIFIED | 148 lines; `load_sigma_rules` exported; field|modifier parsing; graceful degradation |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/src/api/routes.py` | `backend/src/ingestion/opensearch_sink.py` | `from backend.src.ingestion.opensearch_sink import try_index, OPENSEARCH_URL, INDEX_NAME, _get_client` | WIRED | Line 22; `try_index(event)` called at line 73 in `_store_event`; `_get_client` used in `/search` handler |
| `backend/src/api/routes.py` | OpenSearch `/_search` | `httpx POST in /search route` | WIRED | `client.post(url, ...)` at line 143; `hits` extracted from response at line 147 |
| `infra/vector/vector.yaml` | `http://opensearch:9200/soc-events` | `opensearch_events sink type: elasticsearch` | WIRED | `endpoint: "${OPENSEARCH_URL:-http://opensearch:9200}"`, `index: "soc-events"` |
| `backend/src/api/routes.py` | `backend/src/detection/sigma_loader.py` | `from backend.src.detection.sigma_loader import load_sigma_rules as _load_sigma_rules` | WIRED | Line 23; `_SIGMA_RULES = _load_sigma_rules()` at line 44; iterated in `_store_event` lines 57-63 |
| `backend/src/detection/sigma_loader.py` | `backend/src/detection/sigma/suspicious_dns.yml` | `Path(__file__).parent / "sigma"` directory scan | WIRED | `_SIGMA_DIR = Path(__file__).parent / "sigma"` at line 21; `sorted(_SIGMA_DIR.glob("*.yml"))` |
| `backend/src/detection/sigma_loader.py` | `backend/src/api/models.py` | `from backend.src.api.models import Alert as _Alert` (deferred import inside closure) | WIRED | Inside `rule_fn` closure at line 67; `Alert(...)` constructed at lines 92-99 |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| REQ-1: Remove env-var guard / always-set via docker-compose | 03-02 | Unconditionally activate opensearch_sink.py | SATISFIED | `OPENSEARCH_URL=http://opensearch:9200` in docker-compose.yml line 13; OPENSEARCH_URL guard in try_index only prevents broken-URL construction, not indexing |
| REQ-2: GET /search?q= endpoint backed by OpenSearch | 03-02 | Search endpoint returning JSON array | SATISFIED | `@router.get("/search")` with `simple_query_string` query; returns `[]` gracefully when OS unavailable |
| REQ-3: Vector sink in vector.yaml with fixed index soc-events | 03-02 | opensearch_events sink active | SATISFIED | `opensearch_events:` uncommented; `index: "soc-events"` (no date suffix) |
| REQ-4: backend/src/detection/sigma/ directory with suspicious_dns.yml | 03-03 | Sigma rule directory + first rule | SATISFIED | Directory exists; `suspicious_dns.yml` present with UUID id and detection block |
| REQ-5: backend/src/detection/sigma_loader.py — direct Python attribute matching | 03-03 | Sigma rule loader | SATISFIED | 148-line implementation with `field|modifier` parsing; `load_sigma_rules()` exported |
| REQ-6: Sigma matches produce Alert objects in GET /alerts | 03-03 | Sigma alerts surface in /alerts | SATISFIED | `_SIGMA_RULES` iterated in `_store_event`; P3-T6 verified end-to-end |
| REQ-7: docker-compose.yml: OPENSEARCH_URL + depends_on opensearch | 03-02 | docker-compose infra wiring | SATISFIED | OPENSEARCH_URL line 13; healthcheck lines 47-52; depends_on lines 20-22 |
| REQ-8: Wave 0 test stubs written before implementation (Nyquist gate) | 03-01 | TDD gate — stubs committed before implementation | SATISFIED | Commit `77843fa` (stubs) predates `4f1d230` (implementation) per git log |
| REQ-9: All 32 existing tests continue to pass (41 total) | all plans | Regression gate | SATISFIED | `41 passed in 0.24s` — all 32 pre-existing tests pass; 9 Phase 3 tests added |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/src/api/routes.py` | 72 | Stale comment: `# Index to OpenSearch if configured (SCAFFOLD — no-op if OPENSEARCH_URL unset)` | Info | Misleading — try_index IS now called unconditionally (line 73 calls it for every event); comment predates Phase 3 wiring. Code is correct; comment is outdated. |

No blocker or warning anti-patterns found. The stale comment is informational — the underlying code behaves correctly.

---

## Human Verification Required

### 1. Docker Compose Full Stack Startup

**Test:** Run `docker compose -f infra/docker-compose.yml up -d --build` in the project root and wait 60 seconds for OpenSearch JVM startup.
**Expected:** All 5 services start cleanly (backend, frontend, opensearch, vector, caddy). Backend service starts only after `opensearch` reaches `service_healthy`. `curl http://localhost:8000/health` returns `{"status":"ok","ingestion_sources":[...]}`.
**Why human:** Requires a running Docker daemon. OpenSearch JVM startup takes 30-60 seconds. Cannot simulate container healthcheck signaling programmatically.

### 2. Live /search Endpoint with Real OpenSearch

**Test:** After docker compose stack is running, POST `{"host":"test","event":"dns","query":"suspicious-domain.test","timestamp":"2026-03-15T12:00:00Z"}` to `http://localhost:8000/events`, then `GET http://localhost:8000/search?q=suspicious-domain.test`.
**Expected:** The search endpoint returns a JSON array containing at least one event document with `query` matching `suspicious-domain.test`. (In CI without OpenSearch, the endpoint returns `[]` gracefully — this is correct.)
**Why human:** Requires a live OpenSearch instance for the positive case. The graceful-degradation path (`[]`) is tested automatically; the success path requires the real service.

---

## Gaps Summary

No gaps found. All 9 requirements are satisfied by substantive, wired implementations. The phase goal is achieved:

- OpenSearch live indexing is active in docker-compose (OPENSEARCH_URL set unconditionally, healthcheck gate present)
- GET /search endpoint exists and returns gracefully when OpenSearch is unavailable
- Vector pipeline writes to the fixed `soc-events` index directly
- Sigma detection layer (`suspicious_dns.yml` + `sigma_loader.py`) is wired into `_store_event` and tested end-to-end
- 41 tests pass (32 pre-existing + 9 Phase 3)

The only open item is live end-to-end verification against a running Docker stack, which requires human execution.

---

_Verified: 2026-03-15_
_Verifier: Claude (gsd-verifier)_
