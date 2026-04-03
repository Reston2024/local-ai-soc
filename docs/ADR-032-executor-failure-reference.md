# ADR-032: Executor Failure Taxonomy Reference

**Status:** Reference only
**Date:** 2026-04-03
**Canonical location:** `firewall/docs/ADR-E01-executor-failure-taxonomy.md`
**Canonical owner:** firewall repo

---

## Purpose

This document is a **reference stub** maintained in `local-ai-soc` to record how the
SOC must interpret execution receipts returned by the firewall executor.

The authoritative failure taxonomy lives in the firewall repo. If this document and
the firewall canonical disagree, the firewall canonical prevails.

---

## Receipt Failure Taxonomy (SOC interpretation)

The firewall executor returns an execution receipt for every processed recommendation.
The `failure_taxonomy` field carries one of the following values. The SOC MUST react
as specified:

| `failure_taxonomy` value | SOC case-state transition | Analyst action required |
|--------------------------|--------------------------|------------------------|
| `applied` | `containment_confirmed` | None — record and close containment task |
| `noop_already_present` | `containment_confirmed` | None — rule already existed; idempotent success |
| `validation_failed` | `containment_failed` | Page analyst; rule could not be applied |
| `expired_rejected` | `containment_failed` | Re-approve required; create new recommendation |
| `rolled_back` | `containment_rolled_back` | Mandatory analyst review before retry |

### `validation_failed` handling

The SOC MUST NOT attempt automatic re-dispatch when a receipt returns `validation_failed`.
The recommendation artifact is held in `pending_human_review` state. The analyst must
review the failure detail in the receipt and either:
- Create a corrected recommendation (new `recommendation_id`)
- Determine no further action is needed and close the case

Automatic retry without human review is **not permitted** (NIST AI RMF GOVERN 1.1).

### `expired_rejected` handling

If the firewall rejects an artifact as expired, the SOC MUST:
1. Record the rejection in the `recommendation_dispatch_log`
2. Set case state to `containment_failed`
3. Prompt the analyst to re-approve (which creates a new artifact with new `expires_at`)

The original expired artifact is preserved in the audit log unchanged.

### `rolled_back` handling

Rollback indicates a post-apply validation failure on the firewall. This is the most
consequential failure mode. The SOC MUST:
1. Set case state to `containment_rolled_back`
2. Trigger a mandatory analyst review notification
3. Preserve the full receipt including any rollback detail provided by the executor

No automatic re-dispatch is permitted after a rollback. The analyst must explicitly
create a new recommendation with documented rationale.

---

## Receipt Schema

The receipt JSON Schema is canonical in the firewall repo:
`firewall/contracts/execution-receipt.schema.json`

The SOC MUST validate received receipts against a pinned local copy of this schema.
Receipt schema version compatibility is the transport contract's responsibility (ADR-T01).

---

## References

- `firewall/docs/ADR-E01-executor-failure-taxonomy.md` — canonical specification
- `firewall/contracts/execution-receipt.schema.json` — receipt schema (canonical: firewall)
- `docs/ADR-030-ai-recommendation-governance.md` — §6: receipt ingestion obligations
- `docs/ADR-031-transport-contract-reference.md` — transport obligations
