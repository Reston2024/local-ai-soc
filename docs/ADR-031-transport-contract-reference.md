# ADR-031: Transport Contract Reference

**Status:** Reference only
**Date:** 2026-04-03
**Canonical location:** `firewall/docs/ADR-T01-transport-contract.md`
**Canonical owner:** firewall repo

---

## Purpose

This document is a **reference stub** maintained in `local-ai-soc` to record the
transport contract obligations that the SOC system must satisfy as a consumer.

The authoritative specification lives in the firewall repo. If this document and
the firewall canonical disagree, the firewall canonical prevails.

---

## SOC Obligations (consumer side)

### Telemetry receipt (inbound — SOC as consumer)

The SOC MUST accept telemetry from the firewall via the agreed transport channel:

1. **IPFire syslog** — parsed by `ingestion/parsers/ipfire_syslog_parser.py`
2. **Suricata EVE JSON** — parsed by `ingestion/parsers/suricata_eve_parser.py`
3. **Config-change events** — parsed and stored as `NormalizedEvent` with type `config_change`
4. **Heartbeat** — stored as `NormalizedEvent` with type `heartbeat`; missed heartbeats
   trigger a connectivity alert in the SOC

All inbound telemetry MUST be normalised to `NormalizedEvent` schema before storage.
The SOC MUST NOT assume delivery ordering or completeness — telemetry loss is possible
depending on the transport agreed in ADR-T01.

### Recommendation dispatch (outbound — SOC as producer)

The SOC dispatches recommendation artifacts to the firewall's inbound transport endpoint.
Before dispatch the SOC MUST:

1. Validate the artifact against `contracts/recommendation.schema.json` (schema version pinned)
2. Enforce the human-in-the-loop gate (ADR-030 §2)
3. Record the dispatch attempt in the `recommendation_dispatch_log` store
4. Await the execution receipt and process it per ADR-030 §6

The SOC MUST NOT dispatch to an unreachable endpoint silently — transport failures MUST
surface as case state updates.

### Clock trust

The SOC clock is the authority for `generated_at` and `expires_at` on recommendation
artifacts. The firewall clock is the authority for receipt `received_at`. Clock skew of
up to 60 seconds between the two systems MUST be tolerated.

---

## References

- `firewall/docs/ADR-T01-transport-contract.md` — canonical specification
- `docs/ADR-030-ai-recommendation-governance.md` — recommendation artifact governance
- `docs/ADR-032-executor-failure-reference.md` — executor failure taxonomy reference
