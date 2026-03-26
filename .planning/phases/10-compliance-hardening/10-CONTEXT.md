# Phase 10: Compliance Hardening - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning
**Source:** PRD Express Path (AI-SOC-Brain Compliance Report.docx — audit date 2026-03-25)

<domain>
## Phase Boundary

Phase 10 closes the material compliance gaps identified in an audit-grade compliance analysis of the AI-SOC-Brain repository. The audit assessed the system against NIST CSF 2.0, NIST SP 800-53 Rev. 5, NIST AI RMF 1.0, OWASP ASVS 4.0.3, OWASP SAMM 2.0, ISO/IEC/IEEE 15288:2023, NIST SP 800-207, and CIS Controls v8.

The system's overall posture was assessed as **PROTOTYPE-TO-OPERATIONAL — NON-COMPLIANT**. The audit found the architecture sound and the design intent aligned with most standards, but execution-level evidence required to satisfy any formal audit is absent across almost every control domain.

Phase 10 does NOT:
- Rewrite or refactor any existing capability
- Implement full NIST SP 800-53 Rev. 5 compliance (program-level investment)
- Build the Aegis Swarm Core architecture (deferred)
- Add new SOC analysis features

Phase 10 DOES:
- Deliver machine-verifiable CI/CD artifacts (highest-impact single gap)
- Implement documented-but-unimplemented security controls (T-01, T-02, T-03)
- Harden configuration files with trivial-effort high-impact fixes
- Add minimum viable authentication for localhost scope
- Complete incomplete documentation that causes contradictions

Scope is R1 (Immediate Blockers, weeks 1-2) + R2 (Short-Term Remediation, weeks 3-5) from the compliance report roadmap.

</domain>

<decisions>
## Implementation Decisions

### CI/CD Pipeline (CRITICAL — R1)
- Create `.github/workflows/ci.yml` with jobs: `lint` (ruff), `test` (pytest tests/unit/ with coverage), `dependency-audit` (pip-audit), `secret-scan` (gitleaks or trufflehog)
- Coverage threshold: 70% minimum enforced in CI (`--cov-fail-under=70`)
- Smoke tests are PowerShell-only and NOT included in CI (require running Windows backend); CI runs unit tests only
- Add `pytest-cov` to pyproject.toml dev dependencies
- Test artifacts (JUnit XML + coverage XML) must be generated as CI artifacts

### Prompt Injection Sanitization (CRITICAL — R1, REQ-01/T-01)
- Modify `ingestion/normalizer.py`: add `_INJECTION_PATTERNS` compiled regex and `_scrub_injection(text: str) -> str`
- Patterns to strip (case-insensitive): `ignore previous instructions`, `[INST]`, `[/INST]`, `<|system|>`, `<|user|>`, `<|assistant|>`, `###`, `---SYSTEM`, `---INSTRUCTION`, any `ignore.*instruction|prompt|context` sequence
- Apply scrubbing to: `command_line`, `raw_event`, `domain`, `url`, `file_path` fields
- New tests in `tests/unit/test_normalizer.py` asserting patterns are stripped
- Scrubbing happens BEFORE ChromaDB embedding, AFTER null-byte stripping

### Firewall Configuration Script (HIGH — R1, REQ-03/T-03)
- Create `scripts/configure-firewall.ps1`: `New-NetFirewallRule` blocking inbound port 11434 from all except 127.0.0.1 and Docker NIC range (172.16.0.0/12)
- Create `scripts/verify-firewall.ps1`: checks rule exists, is enabled, has correct parameters
- Integrate `verify-firewall.ps1` check into `scripts/status.ps1` as a preflight item
- Do NOT require Admin elevation silently — script must check and prompt if not elevated

### Docker / Caddy Hardening (HIGH — R1)
- `docker-compose.yml`: change `CADDY_ADMIN=0.0.0.0:2019` → `CADDY_ADMIN=127.0.0.1:2019`
- `docker-compose.yml`: pin Caddy image to immutable digest format `caddy:2.9-alpine@sha256:<digest>`
- `infra/docker-compose.yml`: add prominent `# DEPRECATED — Phase 2-3 only, not production` header comment (do NOT delete yet — ADR-019 decision pending)
- Verify Caddy digest by pulling and inspecting before pinning

### Dependency Pinning (HIGH — R2, REQ-07)
- `pyproject.toml`: convert all `>=` specifiers to `==` for direct dependencies using `uv.lock` as source of truth
- Packages requiring exact pinning: `pydantic`, `pydantic-settings`, `httpx`, `chromadb`, `langgraph`, `langchain-ollama`, `pySigma`, `PyYAML`, `evtx`, `pytest`, `pytest-asyncio`, `ruff`
- `backend/requirements.txt`: **delete entirely** — superseded by pyproject.toml + uv.lock
- `REPRODUCIBILITY_RECEIPT.md`: fill all TBD entries using `uv export` output; update status from "BOOTSTRAPPING" to "VERIFIED"; add Ollama model hashes via `ollama show --verbose`

### API Authentication (HIGH — R2)
- Scope: localhost single-analyst tool — shared secret token is sufficient, NOT OAuth2/OIDC
- Create `backend/core/auth.py`: `verify_token` FastAPI dependency checking `Authorization: Bearer <token>` header against `AUTH_TOKEN` env var
- Apply `Depends(verify_token)` to all non-health routes in `backend/main.py`
- `GET /health` and `GET /openapi.json` remain unauthenticated
- Add `AUTH_TOKEN=<generate-a-strong-token>` to `config/.env.example` with instructions
- New tests: `tests/unit/test_auth.py` — valid token passes, missing token returns 401, wrong token returns 401

### LLM Audit Logging (HIGH — R2, REQ-11)
- Modify `backend/services/ollama_client.py`: wrap `generate()` and `embed()` with audit log calls
- Log entries: `event_type`, `model`, `prompt_length`, `prompt_hash` (sha256 first 16 hex chars), `response_length`, `response_hash`
- Add dedicated rotating file handler in `backend/core/logging.py` → `logs/llm_audit.jsonl` (separate from `backend.jsonl`)
- NOT full prompt text (privacy/size concern) — hashes only in audit log; full prompt available via Ollama logs if needed

### Data Directory ACL Script (HIGH — R2, REQ-02)
- Create `scripts/configure-acls.ps1`: `icacls data\ /inheritance:d /grant:r "$env:USERNAME:(OI)(CI)F" /remove "Everyone" /remove "Users"`
- Add ACL preflight check to `scripts/start.ps1` (warn if data/ accessible to other users, don't block startup)

### Security Test Suite (HIGH — R2)
- Create `tests/security/` directory with `__init__.py`
- `tests/security/test_injection.py`: Sigma rule with SQL injection payload cannot produce arbitrary SQL; injected event text has patterns stripped before embedding; file upload with path traversal filename rejected
- `tests/security/test_auth.py`: all non-health endpoints return 401 without token (after auth implementation)
- These tests run in CI as part of `pytest tests/unit/ tests/security/`

### Documentation Cleanup (MEDIUM — R2)
- `docs/manifest.md`: regenerate to reflect Phase 9 file tree and active endpoints
- Add `ADR-019` to `DECISION_LOG.md`: document `backend/src/` dual-path — decision is to **retire** (mark deprecated, do not delete in Phase 10, schedule deletion for Phase 11)
- Remove duplicate `docs/decision-log.md` if it diverges from `DECISION_LOG.md` at root (or redirect it)
- Create `docs/reproducibility.md` as a redirect/pointer to `REPRODUCIBILITY_RECEIPT.md` (broken link fix)

### Claude's Discretion
- Wave structure and plan grouping (parallelism within R1 vs R2 boundary)
- Whether to add `pip-audit` or `trivy` for dependency scanning in CI (prefer `pip-audit` — simpler, Python-native)
- Exact gitleaks vs trufflehog choice for secret scanning (prefer gitleaks — single binary, no auth required)
- Whether `AUTH_TOKEN` uses `secrets.token_hex(32)` or UUID — implementation detail
- Test fixture design for auth and injection tests

</decisions>

<specifics>
## Specific References from Audit Report

### Critical Findings Verbatim
- "No CI/CD pipeline exists. There is no .github/ directory, no workflow YAML, no automated gate enforcement."
- "No authentication or authorization exists on any API endpoint."
- "CADDY_ADMIN=0.0.0.0:2019 in docker-compose.yml... exposes Caddy's management API to any interface reachable by Docker."
- "ingestion/normalizer.py: Strips null bytes and C0/C1 control characters... MISSING: Prompt injection pattern stripping."
- "scripts/configure-firewall.ps1 is referenced in THREAT_MODEL.md (T-03) but does not exist in the repository."

### Remediation File Map (from report §6)
| Report Item | File | Action |
|---|---|---|
| 6.1 Auth Layer | `backend/core/auth.py` (new), `backend/main.py` (modify) | Create + wire |
| 6.2 Injection Scrub | `ingestion/normalizer.py` | Add patterns + function |
| 6.3 CI/CD | `.github/workflows/ci.yml` (new) | Create |
| 6.4 Firewall Script | `scripts/configure-firewall.ps1` (new) | Create |
| 6.5 Docker Hardening | `docker-compose.yml` | Fix CADDY_ADMIN + pin digest |
| 6.6 Dep Pinning | `pyproject.toml`, delete `backend/requirements.txt` | Exact pins |
| 6.7 LLM Audit | `backend/services/ollama_client.py`, `backend/core/logging.py` | Add audit handler |
| 6.8 Stale Docs | `docs/manifest.md`, `REPRODUCIBILITY_RECEIPT.md`, `DECISION_LOG.md` | Update |
| 6.9 ACL Script | `scripts/configure-acls.ps1` (new) | Create |
| 6.10 Security Tests | `tests/security/` (new dir) | Create |

### Compliance Control Matrix IDs (from report §5)
Critical: REQ-01 (injection), NEW-auth (IA-2), NEW-ci (SA-11)
High: REQ-02 (ACL), REQ-03 (firewall), REQ-07 (dep pinning), REQ-10 (auth), REQ-11 (LLM log), REQ-14 (release), NEW-caddy, NEW-digest, NEW-log-integrity

### Note on Test Branch
The audit was based on `feature/ai-soc-phase3-detection` branch. Current state is `master` after Phase 9 merge. Some findings (STATE.md header, backend/models/event.py) were already fixed in the post-merge cleanup commit today. The 10 requirements above reflect remaining open gaps only.

</specifics>

<deferred>
## Deferred (out of Phase 10 scope)

- **Log integrity protection** (append-only shipping, log signing) — R3 item, requires external infrastructure
- **Data-at-rest encryption** (REQ-15) — explicitly documented as future control in THREAT_MODEL.md
- **Full NIST SP 800-53 Rev. 5 compliance** — program-level investment, not a single phase
- **backend/src/ deletion** — ADR-019 documents the decision but deletion is Phase 11 to avoid regressions
- **Rate limiting** (OWASP ASVS V4.2.4) — medium priority, deferred
- **Certificate pinning / rotation policy** — low priority for localhost TLS
- **Session management** — not applicable until auth layer expanded beyond token
- **Aegis Swarm Core architecture** — separate project initiative, held off
- **A2A / MCP / LangGraph migration** — held off
- **Compliance control matrix document** (docs/compliance-matrix.md) — R4 item, requires completed controls first
- **Assurance case (GSN)** — R4 item
- **Container image scanning in CI** — R3 item
- **Coverage shipping to external service** (Codecov etc.) — R4 item

</deferred>

---

*Phase: 10-compliance-hardening*
*Context gathered: 2026-03-26 via PRD Express Path (AI-SOC-Brain Compliance Report.docx)*
