# Security Claims — Implementation & Test Traceability

This document maps every security claim made in README.md and STATE.md
to the code that implements it and the test that verifies it.
Purpose: make claims falsifiable. If a claim has no test, it is marked **UNTESTED**.

Last updated: 2026-04-19  
Reference: `governance/release_state.yaml` schema_version 1.0

---

## Authentication & Access Control

| Claim | Implementing Code | Verifying Test | Status |
|-------|-------------------|----------------|--------|
| Bearer token required on all `/api/*` routes | `backend/core/auth.py` `verify_token()` | `tests/security/test_auth.py::test_sensitive_routes_require_auth` (14 routes) | ✅ TESTED |
| Empty `AUTH_TOKEN` rejects all requests (misconfiguration guard) | `backend/core/auth.py` line 64 — `if not configured: raise 401` | `tests/security/test_auth.py::test_empty_auth_token_rejects_all_requests` | ✅ TESTED |
| Whitespace-only `AUTH_TOKEN` rejected | `backend/core/auth.py` — `.strip()` before check | `tests/security/test_auth.py::test_whitespace_only_auth_token_rejects_all_requests` | ✅ TESTED |
| `?token=` query param accepted for binary downloads | `backend/core/auth.py` `token: str | None = Query(...)` | `tests/security/test_auth.py::test_query_param_token_bypasses_header_requirement` | ✅ TESTED |
| Wrong token → 401 | `backend/core/auth.py` final `raise HTTPException(401)` | `tests/security/test_auth.py::test_wrong_token_returns_401` | ✅ TESTED |
| Non-Bearer scheme (Basic, Digest) → 401/403 | FastAPI `HTTPBearer(auto_error=False)` + verify_token | `tests/security/test_auth.py::test_non_bearer_scheme_returns_401` | ✅ TESTED |
| RBAC roles (admin/analyst/viewer) enforced | `backend/core/rbac.py` `require_role()` | `tests/unit/test_rbac.py` | ✅ TESTED |
| TOTP enforcement when `totp_secret` configured | `backend/core/auth.py` lines 98–106 | `tests/unit/test_totp.py` | ✅ TESTED |
| bcrypt for operator key storage | `backend/core/operator_utils.py` `hash_api_key()` | `tests/unit/test_operator_store.py` | ✅ TESTED |
| Timing-safe comparison (no timing oracle) | `backend/core/auth.py` `hmac.compare_digest()` + `verify_api_key()` | No dedicated timing test | ⚠️ IMPLICIT |
| `/health` endpoint publicly accessible (no auth) | `backend/api/health.py` — no `verify_token` dependency | `tests/security/test_auth.py::test_health_endpoint_no_auth_required` | ✅ TESTED |

---

## Injection Defense

| Claim | Implementing Code | Verifying Test | Status |
|-------|-------------------|----------------|--------|
| Prompt injection patterns stripped from ingest fields | `ingestion/normalizer.py` `_scrub_injection()` | `tests/security/test_injection.py::test_injection_patterns_stripped` | ✅ TESTED |
| Base64-encoded injection payloads decoded and stripped | `ingestion/normalizer.py` — base64 decode in `_scrub_injection()` | `tests/security/test_injection_hardening.py::test_base64_bypass_scrubbed` | ✅ TESTED |
| Chat question sanitized before LLM prompt construction | `backend/api/chat.py` — calls `_scrub_injection(body.question)` | `tests/security/test_injection_hardening.py::test_chat_question_scrubbed` | ✅ TESTED |
| Sigma field values parameterized (no SQL injection) | `detections/matcher.py` `rule_to_sql_with_params()` — uses `?` placeholders | `tests/security/test_sigma_hardening.py` (5 tests) | ✅ TESTED |
| File upload path traversal rejected | `backend/api/ingest.py` — extension allowlist `.evtx`, `.json`, `.ndjson`, `.jsonl`, `.csv` | `tests/security/test_injection.py::test_path_traversal_rejected` | ✅ TESTED |

---

## Data Isolation & Storage Security

| Claim | Implementing Code | Verifying Test | Status |
|-------|-------------------|----------------|--------|
| DuckDB external access disabled | `backend/stores/duckdb_store.py` — `enable_external_access=false` on all connections | `tests/unit/test_duckdb_store.py` | ✅ TESTED |
| DuckDB writes serialized through write queue (no concurrent write races) | `backend/stores/duckdb_store.py` `execute_write()` + asyncio queue | `tests/unit/test_duckdb_store.py` | ✅ TESTED |
| Sigma guard validates all rules at startup (no malformed rule execution) | `backend/services/sigma_guard.py` | `tests/unit/test_sigma_guard.py` | ✅ TESTED |

---

## LLM / AI Security

| Claim | Implementing Code | Verifying Test | Status |
|-------|-------------------|----------------|--------|
| All Ollama calls logged to `logs/llm_audit.jsonl` | `backend/services/ollama_client.py` `_audit_log()` | `tests/unit/test_ollama_audit.py` | ✅ TESTED |
| LLM responses include grounding score | `backend/services/llm_provenance.py` | `tests/unit/test_llm_provenance.py` | ✅ TESTED |
| Citation verification on analyst QA responses | `backend/api/query.py` `verify_citations()` | `tests/unit/test_explain_api.py` | ✅ TESTED |
| Ollama model digest verified on startup | `backend/core/config.py` `verify_model_digest()` | `tests/unit/test_ollama_client.py` | ✅ TESTED |
| No hallucinated citations (citation IDs resolve to real events) | `backend/api/query.py` | No dedicated negative test | ⚠️ UNTESTED |
| Prompt injection in event fields cannot alter LLM behavior | `ingestion/normalizer.py` + `backend/api/chat.py` | Functional scrub tested; no end-to-end LLM probe | ⚠️ PARTIAL |
| analyst_qa system prompt prohibits fabrication and requires evidence grounding | `prompts/analyst_qa.py` `SYSTEM` | `tests/ai/test_llm_safety.py::TestAnalystQaSystemPrompt` (4 tests) | ✅ TESTED |
| Evidence and analyst question are in separate prompt trust domains | `prompts/analyst_qa.py` `build_prompt()` | `tests/ai/test_llm_safety.py::TestAnalystQaBuildPrompt` (4 tests) | ✅ TESTED |
| Copilot chat prompt prohibits fabrication and expresses uncertainty | `prompts/copilot.py` `SYSTEM` | `tests/ai/test_llm_safety.py::TestCopilotSystemPrompt` (6 tests) | ✅ TESTED |
| Copilot `SYSTEM` prompt SHA-256 fingerprinted and tracked in llm_provenance | `prompts/copilot.py` `TEMPLATE_SHA256`; `backend/api/chat.py` `record_llm_provenance` | `tests/ai/test_llm_safety.py::TestCopilotSystemPrompt::test_template_sha256_is_populated` | ✅ TESTED |
| Chat API scrubs analyst question before LLM prompt construction | `backend/api/chat.py` — calls `_scrub_injection(body.question)` | `tests/ai/test_llm_safety.py::TestChatApiPipelineContract` | ✅ TESTED |
| "system prompt" exfiltration phrase not stripped by `_scrub_injection` | `ingestion/normalizer.py` `_INJECTION_PATTERNS` | `tests/ai/test_llm_safety.py::test_strips_system_prompt_exfiltration` (xfail) | ❌ GAP (AG-006) |
| "you are now DAN" jailbreak phrase not stripped by `_scrub_injection` | `ingestion/normalizer.py` `_INJECTION_PATTERNS` | `tests/ai/test_llm_safety.py::test_strips_role_override` (xfail) | ❌ GAP (AG-006) |

---

## Supply Chain & Build

| Claim | Implementing Code | Verifying Test / Gate | Status |
|-------|-------------------|-----------------------|--------|
| Caddy container image digest-pinned | `docker-compose.yml` — `sha256:` digest | Manual verification (Phase 30) | ⚠️ NO CI GATE |
| Dependencies scanned for CVEs on every push | `.github/workflows/ci.yml` `dependency-audit` job | pip-audit gate | ✅ CI GATE |
| uv.lock consistency enforced | `.github/workflows/compliance.yml` `dependency-integrity` job | `uv sync` fails on stale lock | ✅ CI GATE |
| Secrets scanned on every push | `.github/workflows/ci.yml` `secret-scan` job (gitleaks) | gitleaks gate | ✅ CI GATE |
| No SBOM generated | — | — | ❌ GAP (AG-001) |
| No artifact signing | — | — | ❌ GAP (AG-002, optional) |

---

## Privacy / Monitoring

| Claim | Implementing Code | Verifying Test | Status |
|-------|-------------------|----------------|--------|
| EasyPrivacy blocklist loaded (46,871 domains) | `backend/services/intel/privacy_blocklist.py` `_parse_easyprivacy()` | `tests/unit/test_privacy_blocklist.py::test_parse_easyprivacy_extracts_domains` | ✅ TESTED |
| Disconnect.me blocklist loaded (4,790 entries) | `backend/services/intel/privacy_blocklist.py` `_parse_disconnect()` | `tests/unit/test_privacy_blocklist.py::test_parse_disconnect_extracts_all_categories` | ✅ TESTED |
| Tracker domain lookup functional | `PrivacyBlocklistStore.is_tracker()` | `tests/unit/test_privacy_blocklist.py::test_store_upsert_and_lookup` | ✅ TESTED |
| All privacy API endpoints require authentication | `backend/api/privacy.py` — `APIRouter(dependencies=[Depends(verify_token)])` | `tests/security/test_auth.py::test_sensitive_routes_require_auth` | ✅ TESTED |

---

## Gaps Summary

| Gap ID | Description | Risk | Roadmap | Status |
|--------|-------------|------|---------|--------|
| AG-001 | No SBOM | Medium — dependency surface not machine-readable | A-2 | Open |
| AG-002 | No artifact signing | Low (homelab deployment) | A-2 optional | Open |
| AG-003 | No AI_GOVERNANCE.md / model inventory | Medium | B-2 | ✅ Closed 2026-04-19 |
| AG-004 | No end-to-end scenario tests | Medium — detection pipeline not E2E validated | B-3 | ✅ Closed 2026-04-19 |
| AG-005 | `_COPILOT_SYSTEM` not SHA-256 fingerprinted | Low | C-1 | ✅ Closed 2026-04-19 |
| AG-006 | `_scrub_injection` missing "system prompt" and "you are now DAN" patterns | Medium | C-2 pattern review | Open — xfail tests document this |
| IMPLICIT-001 | Timing oracle protection not directly tested | Low — `hmac.compare_digest` is stdlib-proven | Accept | Open |
| PARTIAL-001 | LLM injection: scrub tested, no live LLM probe | Medium | C-2 eval harness | Open |
