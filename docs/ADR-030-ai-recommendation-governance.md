# ADR-030: AI Recommendation Governance (AI RMF Alignment)

**Status:** Accepted
**Date:** 2026-04-03
**Deciders:** AI-SOC-Brain architecture team
**Canonical owner:** `local-ai-soc` (this repo)
**Cross-references:**
- `firewall/docs/ADR-T01-transport-contract.md` — delivery mechanism (canonical: firewall)
- `firewall/docs/ADR-E01-executor-failure-taxonomy.md` — executor failure modes (canonical: firewall)

---

## Context

The AI-SOC-Brain system produces analyst-facing investigation outputs that may result in
operator-approved network control changes on the connected IPFire firewall. This creates an
AI-in-the-loop decision chain where LLM outputs can indirectly affect operational security
infrastructure.

NIST AI RMF 1.0 (GOVERN/MAP/MEASURE/MANAGE) requires that AI systems affecting operational
decisions implement documented governance for: output traceability, human oversight gates,
confidence measurement, and incident accountability. NIST SP 800-61r3 (April 2025) further
requires that analysis artifacts be evidence-preserving and maintain chain-of-custody through
any containment action.

This ADR defines the governance structure for the **recommendation artifact** — the signed JSON
object that records an AI-assisted analyst decision before it crosses the trust boundary into
the firewall enforcement plane.

---

## Decision

### 1. Recommendation Artifact (AI RMF GOVERN 1.1 / MAP 1.5)

Every AI-assisted recommendation that may result in a firewall control change MUST be
materialised as a versioned, signed JSON artifact conforming to
`contracts/recommendation.schema.json` (maintained in this repo).

**Mandatory fields:**

| Field | Purpose | AI RMF mapping |
|-------|---------|----------------|
| `recommendation_id` | UUID; primary key for audit trail | GOVERN 1.1 — accountability |
| `case_id` | Links recommendation to investigation case | GOVERN 1.1 — traceability |
| `type` | Action class (`network_control_change`, etc.) | MAP 1.5 — scope declaration |
| `proposed_action` | Specific control operation | MAP 1.5 — impact boundary |
| `target` + `scope` | What is affected and where | MAP 1.5 — blast-radius bounding |
| `rationale` | Human-readable reasoning chain | GOVERN 1.1 — explainability |
| `evidence_event_ids` | Event IDs that ground the recommendation | MEASURE 2.5 — grounding |
| `retrieval_sources` | RAG chunks used (`count` + `ids`) | MEASURE 2.5 — retrieval audit |
| `inference_confidence` | Enum: `high \| medium \| low \| none` | MEASURE 2.6 — uncertainty |
| `model_id` | Ollama model identifier | MANAGE 4.1 — model provenance |
| `model_run_id` | Links to `llm_audit_provenance` row | MANAGE 4.1 — run traceability |
| `prompt_inspection` | Structured object (see §3) | GOVERN 1.1 — injection defence |
| `generated_at` | ISO-8601 UTC timestamp | GOVERN 1.1 — time accountability |
| `analyst_approved` | Boolean; MUST be `true` before dispatch | GOVERN 1.1 — human-in-the-loop |
| `approved_by` | Operator identifier | GOVERN 1.1 — accountability |
| `override_log` | Object; populated when analyst overrides AI | MANAGE 4.2 — override audit |
| `expires_at` | ISO-8601 UTC; firewall MUST reject after this | MAP 1.5 — time-bounded authority |

**The artifact is immutable once `analyst_approved` is set to `true`.** Any modification after
approval voids the artifact; a new artifact with a new `recommendation_id` must be created.

### 2. Human-in-the-Loop Gate (AI RMF GOVERN 1.1)

No recommendation artifact MAY be dispatched to the firewall enforcement plane unless:

1. `analyst_approved` is `true`
2. `approved_by` is populated with a non-empty operator identifier
3. The artifact has not expired (`current UTC < expires_at`)
4. The artifact passes schema validation against `contracts/recommendation.schema.json`

The dispatch path MUST enforce these conditions programmatically. There is no trusted-caller
exception — the firewall executor independently re-validates the artifact against its pinned
copy of the schema (see ADR-T01).

### 3. Prompt Inspection (structured audit, not boolean)

The `prompt_inspection` field MUST be a structured object, not a boolean flag. Boolean flags
are insufficient for audit evidence because they cannot distinguish between "passed because
checks ran" and "passed because checks were skipped".

Required structure:

```json
{
  "method": "pattern_scrub_v2",
  "passed": true,
  "flagged_patterns": [],
  "audit_log_id": "pi-uuid-v4"
}
```

| Sub-field | Type | Meaning |
|-----------|------|---------|
| `method` | string | Inspection algorithm version; version-pinned |
| `passed` | boolean | Result of the inspection run |
| `flagged_patterns` | string[] | Patterns matched (empty if `passed: true`) |
| `audit_log_id` | string | UUID linking to the prompt inspection audit log row |

If the inspection method is unavailable, `passed` MUST be `false` and `method` MUST be
`"unavailable"`. The artifact MAY still be dispatched at analyst discretion, but
`override_log` MUST document the decision.

### 4. Override Audit (AI RMF MANAGE 4.2)

When an analyst approves a recommendation that the AI assessed with `inference_confidence`
of `low` or `none`, or where `prompt_inspection.passed` is `false`, the `override_log` MUST
be populated:

```json
{
  "approved_at": "2026-04-03T12:30:00Z",
  "approval_basis": "Corroborating Suricata alert cluster reviewed manually",
  "modified_fields": [],
  "operator_note": "Low confidence due to sparse RAG; manual review confirms IOC"
}
```

`modified_fields` lists any recommendation fields the analyst altered before approval (e.g.,
narrowing the `scope` or changing `target`). An empty array indicates the AI output was
accepted without modification.

### 5. Model Drift Accountability (AI RMF MANAGE 4.1)

`model_id` and `model_run_id` MUST be populated from the `llm_audit_provenance` store (see
Phase 22 plan 22-04). If `_check_model_drift()` detected a model change since the last known
clean state when this recommendation was generated, the `model_id` field MUST reflect the
new model identifier, and the case MUST be flagged for additional review before dispatch.

This ensures that recommendations generated during an unexpected model change are surfaced
to the analyst rather than silently approved.

### 6. Receipt Ingestion (NIST SP 800-61r3 — evidence chain)

When the firewall returns an execution receipt (schema canonical in `firewall/contracts/`),
the SOC MUST:

1. Store the receipt linked to `recommendation_id` and `case_id`
2. Record the `failure_taxonomy` enum value (`applied | noop_already_present |
   validation_failed | expired_rejected | rolled_back`)
3. Propagate automatic case-state updates:
   - `applied` → case state `containment_confirmed`
   - `noop_already_present` → case state `containment_confirmed` (idempotent)
   - `validation_failed` → case state `containment_failed`; page analyst
   - `expired_rejected` → case state `containment_failed`; re-approve required
   - `rolled_back` → case state `containment_rolled_back`; mandatory analyst review

Receipt storage preserves the full evidence chain required by SP 800-61r3 §3.3
(containment decision traceability).

---

## Consequences

### Required artifacts (before Phase 1 integration code)

- [ ] `contracts/recommendation.schema.json` — versioned JSON Schema (this repo)
- [ ] `contracts/` directory added to `.gitignore` exclusions removed (must be committed)
- [ ] `firewall/contracts/execution-receipt.schema.json` — canonical in firewall repo
- [ ] `firewall/docs/ADR-T01-transport-contract.md` — canonical in firewall repo
- [ ] `firewall/docs/ADR-E01-executor-failure-taxonomy.md` — canonical in firewall repo

### Required code (Phase 1 integration)

- Receipt ingestion route and storage in `backend/api/`
- Case-state propagation from receipt `failure_taxonomy`
- Schema validation enforcement in recommendation dispatch path
- Human approval gate enforced before dispatch (not advisory)

### What this ADR does NOT govern

- The transport mechanism (TCP/TLS, UDP) — see ADR-T01 in firewall repo
- Executor failure handling on the firewall side — see ADR-E01 in firewall repo
- Malcolm/OpenSearch schema extensions — see ADR-031 (planned)
- Graph schema versioning for perimeter entities — see ADR-032 (planned)

---

## References

- NIST AI RMF 1.0 — GOVERN 1.1, MAP 1.5, MEASURE 2.5/2.6, MANAGE 4.1/4.2
- NIST SP 800-61r3 (April 2025) — §3.3 containment decision traceability
- Phase 22 plan 22-02 — confidence scoring implementation (`llm_audit_provenance`)
- Phase 22 plan 22-04 — model drift detection (`_check_model_drift()`)
- Phase 22 plan 22-07 — grounding citations in AI Copilot UI
- Phase 22 plan 22-08 — `GET /api/provenance/copilot/response/{audit_id}` endpoint
- `contracts/recommendation.schema.json` (this repo) — machine-readable artifact schema
- `firewall/contracts/execution-receipt.schema.json` — receipt schema (canonical: firewall)
