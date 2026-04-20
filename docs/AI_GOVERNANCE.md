# AI Governance Policy — AI-SOC-Brain

**Version:** 1.0  
**Last updated:** 2026-04-19  
**Owner:** Platform Operator  
**Status:** Active

This document is the authoritative record of AI model usage in this platform.
It exists to make AI risk visible, auditable, and controllable. Every model deployed
must appear here. Any model change requires this document to be updated before deployment.

---

## 1. Model Inventory

### 1.1 `mxbai-embed-large` — Embedding Model

| Field | Value |
|-------|-------|
| **Role** | Semantic embedding for RAG retrieval |
| **Config key** | `OLLAMA_EMBED_MODEL` |
| **Risk tier** | LOW |
| **Output type** | Float vectors (opaque, never rendered to users) |
| **Data processed** | Normalized security event text, analyst notes |
| **Hallucination risk** | None — model produces vectors, not text |
| **Injection risk** | Low — malicious event data is embedded, not executed |
| **Mitigations** | Digest pinning (`OLLAMA_EMBEDDING_DIGEST`); output goes to ChromaDB only |
| **Human review required** | No — output never shown to analyst as-is |

### 1.2 `qwen3:14b` — General Analyst LLM

| Field | Value |
|-------|-------|
| **Role** | Analyst Q&A, threat hunt queries, triage summaries, incident reports |
| **Config key** | `OLLAMA_MODEL` |
| **Risk tier** | MEDIUM |
| **Output type** | Natural language text rendered to analyst |
| **Data processed** | Normalized event context, analyst questions |
| **Hallucination risk** | Medium — may invent IOCs, technique names, or event IDs not in evidence |
| **Injection risk** | Medium — adversary-controlled fields in events reach the prompt |
| **Mitigations** | See Section 3 (Prompt Defense Layers); citation verification on every response (`verify_citations`); evidence-context separation (system turn vs. user turn); `_scrub_injection()` on all user-controlled input; LLM audit log (`logs/llm_audit.jsonl`); digest pinning |
| **Human review required** | Yes — all LLM responses carry `[AI Advisory — not a verified fact]` prefix |

### 1.3 `foundation-sec:8b` — Cybersecurity Specialist LLM

| Field | Value |
|-------|-------|
| **Role** | Investigation copilot chat, incident summaries for active investigations |
| **Config key** | `OLLAMA_CYBERSEC_MODEL` |
| **Risk tier** | MEDIUM-HIGH |
| **Output type** | Natural language cybersecurity analysis rendered to analyst |
| **Data processed** | Full investigation timeline context, analyst questions |
| **Hallucination risk** | Medium-high — specialized model may confidently fabricate ATT&CK technique associations |
| **Injection risk** | Medium — timeline data may contain adversary-controlled content |
| **Mitigations** | Same as qwen3:14b; additionally: `_COPILOT_SYSTEM` explicitly instructs "Do not fabricate event IDs or hostnames"; model fall-through to qwen3:14b if foundation-sec is unavailable; chat history persisted to SQLite for forensic review |
| **Human review required** | Yes — chat responses are advisory only; analyst must verify any recommended action against raw event evidence |

### 1.4 `BAAI/bge-reranker-v2-m3` — Passage Reranker

| Field | Value |
|-------|-------|
| **Role** | Rerank RAG retrieval results for relevance before analyst Q&A |
| **Config key** | `RERANKER_URL`, `RERANKER_ENABLED` |
| **Risk tier** | LOW |
| **Output type** | Relevance scores (floats), no text generation |
| **Data processed** | Query text + candidate passages |
| **Hallucination risk** | None — model reorders results, does not generate text |
| **Injection risk** | Low — adversary cannot control which documents rank higher via reranker alone |
| **Mitigations** | Runs as isolated microservice (`backend/services/reranker_service.py`); disabled by default (`RERANKER_ENABLED=False`); no LLM audit logging needed |
| **Human review required** | No |

---

## 2. Prompt Template Versioning

All LLM prompt templates are source-controlled in `prompts/`.

### Policy

- Every template module computes and exposes `TEMPLATE_SHA256` — the SHA-256 of its own source file.
- The `OllamaClient.generate()` and `stream_generate()` methods accept `prompt_template_name` and `prompt_template_sha256` parameters, written to the `llm_provenance` table in SQLite.
- Any change to a template MUST increment the template version comment at the top of the file and update this document.
- Breaking changes (system prompt substantive changes, context structure changes) require a new template name prefix (e.g. `analyst_qa_v2`).

### Current Templates

| Template | File | Purpose | SHA-256 computed at |
|----------|------|---------|---------------------|
| `analyst_qa` | `prompts/analyst_qa.py` | Evidence-grounded analyst QA | Module import (runtime) |
| `triage` | `prompts/triage.py` | Alert triage and severity assessment | Module import (runtime) |
| `threat_hunt` | `prompts/threat_hunt.py` | Proactive threat hunting hypothesis generation | Module import (runtime) |
| `incident_summary` | `prompts/incident_summary.py` | Natural language incident reports | Module import (runtime) |
| `evidence_explain` | `prompts/evidence_explain.py` | Explain specific evidence artifacts | Module import (runtime) |
| `investigation_summary` | `prompts/investigation_summary.py` | Investigation closure summary | Module import (runtime) |
| `copilot_chat` | `backend/api/chat.py` (`_COPILOT_SYSTEM`) | Investigation copilot system prompt | Static string (not SHA-256 tracked — see AG-005) |

**Gap AG-005:** `_COPILOT_SYSTEM` in `backend/api/chat.py` is not SHA-256 fingerprinted. Roadmap: extract to `prompts/copilot.py` and add provenance tracking.

---

## 3. Prompt Defense Layers

The following mitigations are implemented in the production LLM pipeline:

### Layer 1 — Input Sanitization
- `ingestion/normalizer.py` `_scrub_injection()` strips prompt injection patterns from all ingested event fields before they are stored.
- Base64-encoded payloads are decoded and scanned before storage.
- `backend/api/chat.py` calls `_scrub_injection(body.question)` on every analyst question before incorporating into the LLM prompt.

### Layer 2 — Trust Domain Separation
- `prompts/analyst_qa.py` places evidence in the **system turn** (trusted context position) and the analyst question in the **user turn**.
- Evidence is wrapped in `[EVIDENCE]...[/EVIDENCE]` tags; the system prompt explicitly instructs the model to treat tag content as data only, never as instructions.
- This prevents indirect prompt injection where an adversary's event data attempts to override analyst instructions.

### Layer 3 — Output Verification
- `backend/api/query.py` `verify_citations()` checks that every `[event_id]` cited in an LLM response exists in the context that was passed to the model.
- A citation that references an event ID not in the context is flagged as a potential hallucination.
- The chat API emits `{"done": true, "citation_verified": false}` in the SSE stream when citation verification fails.

### Layer 4 — Audit Trail
- Every LLM call is logged to `logs/llm_audit.jsonl` with: event type, model, prompt length, prompt SHA-256 hash, response length, response SHA-256 hash, timestamp, operator ID, and success/error status.
- Non-streaming calls additionally write to the `llm_calls` table in DuckDB (prompt text truncated to 64 KB, plus SHA-256 hash).
- The `llm_provenance` table in SQLite records: audit ID, model, template name, template SHA-256, response SHA-256, grounding event IDs, and operator ID.

### Layer 5 — Model Integrity
- `OllamaClient.verify_model_digest()` checks the running model's SHA-256 digest against the operator-configured expected prefix.
- `OLLAMA_ENFORCE_DIGEST=True` causes hard startup failure on digest mismatch (recommended for production).
- `OllamaClient._check_model_drift()` logs a warning when the active model differs from the last known model (seeded to SQLite on first call).

---

## 4. Human-in-the-Loop Gates

These decisions require human analyst confirmation before the platform takes automated action:

| Decision | Trigger | Gate | Config |
|----------|---------|------|--------|
| Network block (IP firewall drop) | `confidence >= ENFORCEMENT_MIN_CONFIDENCE` | Operator must click "Approve" in enforcement panel | `ENFORCEMENT_REQUIRE_APPROVAL=True` |
| Automated response actions during learning period | Any high-confidence detection | All actions logged but NOT executed | `ENFORCEMENT_LEARNING_MODE=True` |
| Case escalation to TheHive | Sigma rule match above threshold | Human review before auto-case creation | `THEHIVE_SUPPRESS_RULES` allowlist |
| LLM-recommended remediation steps | Any copilot response | Response is advisory only — analyst must initiate action | System prompt instructs "advisory only" |
| Bulk ingest of untrusted log sources | File upload | Analyst must authenticate and explicitly POST to `/api/ingest` | Auth + explicit API call required |

**Default posture:** `ENFORCEMENT_LEARNING_MODE=True` and `ENFORCEMENT_REQUIRE_APPROVAL=True`.
This means the platform OBSERVES and ADVISES but never autonomously takes network action until
the operator explicitly transitions to active enforcement mode after the documented baseline period.

---

## 5. Kill-Switch Procedure

Use this procedure when an LLM model must be immediately disabled (e.g. model compromise discovered,
unexpected behavior, supply chain incident).

### 5.1 Disable the General LLM (`qwen3:14b`)

```bash
# 1. Set digest enforcement to force startup failure with current model
echo 'OLLAMA_ENFORCE_DIGEST=True' >> .env
echo 'OLLAMA_MODEL_DIGEST=sha256:INVALID_DISABLE_ALL' >> .env

# 2. Restart the backend — it will refuse to start with a digest mismatch
# All /query/ask, /query/ask/stream, triage, threat-hunt endpoints become unavailable
# The frontend will show "LLM unavailable" gracefully

# 3. Pull a known-good replacement and update the digest
# ollama pull qwen3:14b
# curl http://localhost:11434/api/show -d '{"name":"qwen3:14b"}' | python -m json.tool
# Update OLLAMA_MODEL_DIGEST= in .env with the verified digest
# Set OLLAMA_ENFORCE_DIGEST=True to lock it
```

### 5.2 Disable the Cybersecurity Copilot (`foundation-sec:8b`)

```bash
# Setting OLLAMA_CYBERSEC_MODEL to empty or non-existent model falls through to qwen3:14b
# Full disable: set the model to a non-existent name to prevent the route from calling Ollama
echo 'OLLAMA_CYBERSEC_MODEL=disabled-model' >> .env
# Restart backend — /api/investigations/*/chat will return Ollama errors, caught gracefully
```

### 5.3 Disable All LLM Features

```bash
# Revoke the auth token — no requests can reach the API
# Generate a new token and update only trusted operator devices
python -c "import secrets; print(secrets.token_hex(32))"
# Update AUTH_TOKEN= in .env and restart the backend
```

### 5.4 Disable Enforcement Actions Only (Safest Default)

```bash
# Already the default — confirm these are set in .env:
ENFORCEMENT_LEARNING_MODE=True
ENFORCEMENT_REQUIRE_APPROVAL=True
# With these settings the platform cannot autonomously block network traffic
# regardless of what any LLM output says
```

---

## 6. Data Handling Policy

| Data type | Storage | Retention | Access |
|-----------|---------|-----------|--------|
| Security event fields (hostnames, IPs, process names) | DuckDB (local) | `RETENTION_DAYS` (default 90) | Auth required |
| LLM prompt text | DuckDB `llm_calls.prompt_text` (64 KB max), `logs/llm_audit.jsonl` | Retained indefinitely — rotate manually | Local only |
| LLM response text | `logs/llm_audit.jsonl` (hash only) | Retained indefinitely | Local only |
| Chat messages | SQLite `chat_messages` | Not auto-purged | Auth required |
| Analyst notes | SQLite | Not auto-purged | Auth required |

**Network isolation:** All LLM inference runs locally via Ollama at `http://127.0.0.1:11434`.
No event data, analyst questions, or LLM prompts are sent to any external service.
The only outbound network calls are OSINT enrichment APIs (VirusTotal, AbuseIPDB, Shodan) —
which receive only IOC hashes/IPs, never full event records or analyst questions.

---

## 7. Known Gaps and Roadmap

| Gap ID | Description | Risk | Roadmap |
|--------|-------------|------|---------|
| AG-003 | This document did not exist until Phase 53/B-2 | Medium — AI risk undocumented | ✅ Closed B-2 |
| AG-005 | `_COPILOT_SYSTEM` prompt not SHA-256 fingerprinted | Low — string visible in source, but not in provenance table | C-1 |
| PARTIAL-001 | Injection scrub tested functionally; no live end-to-end LLM probe | Medium — defense tested at unit level only | C-2: eval harness |
| UNTESTED-001 | No negative hallucination test (ask about non-existent event → must not fabricate) | Medium — `verify_citations` is tested; adversarial probing is not | C-2: eval harness |

---

## 8. Review Schedule

This document must be reviewed and updated:
- When any model is added, removed, or changed
- When any prompt template is substantively modified
- When enforcement mode transitions from learning → active
- At minimum every 90 days

**Next review due:** 2026-07-19
