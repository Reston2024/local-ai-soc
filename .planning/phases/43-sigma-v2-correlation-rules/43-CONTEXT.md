# Phase 43: Sigma v2 Correlation Rules - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Add multi-event pattern detection to the existing detection pipeline. Four correlation types: port scan, brute force, beaconing (CV-based), and multi-stage rule chains. Each produces a `DetectionRecord` with `matched_event_ids` evidence. The per-event Sigma matcher is unchanged — this is an additive layer that runs after ingest.

</domain>

<decisions>
## Implementation Decisions

### Trigger Cadence
- Run correlation **after every ingest batch** — same trigger point as Sigma matching. No separate scheduler needed.
- Scan a **recent window only** (not full history). Window is configurable via `.env`.
- **Deduplicate**: suppress a new detection if the same `src_ip + rule_id + evidence window` already fired within the dedup window. Prevents alert flooding from persistent scanners.
- **Settings added to config.py:**
  - `CORRELATION_LOOKBACK_HOURS` — how far back to query events (default: 2h)
  - `CORRELATION_DEDUP_WINDOW_MINUTES` — how long to suppress repeat fires (default: 60)

### Detection Thresholds
- **Port scan:** 15+ distinct `dst_port` values from one `src_ip` within 60 seconds → `corr-portscan`, severity `medium`
- **Brute force:** 10+ failed auth events for the same target within 60 seconds → `corr-bruteforce`, severity `high`
- **Beaconing:** CV (stddev/mean of inter-connection intervals) < 0.3 over 20+ connections per `(src_ip, dst_ip, dst_port)` tuple → `corr-beacon`, severity `high`
- **Multi-stage chain:** all rules in chain fire for same `src_ip` within 15 minutes → `corr-chain-{name}`, severity `critical`

### UI Surface
- Correlation detections appear **inline in DetectionsView** — no new tab. Consistent with Phase 42 anomaly detections appearing in the same view.
- Each correlation row shows: correlation type badge (`PORT_SCAN` / `BRUTE_FORCE` / `BEACON` / `CHAIN`), source entity (`src_ip`), matched event count.
- Click row → expand to show the individual matched event IDs (not full event list inline).
- **Add `CORR` filter chip** to DetectionsView alongside existing filter chips — lets analyst isolate correlation hits.
- Severity is **fixed per type**: PORT_SCAN=medium, BRUTE_FORCE=high, BEACON=high, CHAIN=critical.

### Multi-Stage Chains
- Chains are defined in a **YAML config file**: `detections/correlation_chains.yml`
- Schema: each entry has `name`, `rule_ids` (or `rule_types`), `entity_key` (fixed to `src_ip`), `window_minutes`.
- Pre-configured chain: **recon → port scan → exploitation** (classic kill-chain: a recon-tagged Sigma rule + a `corr-portscan` correlation hit + any exploitation-tagged Sigma rule, all for same `src_ip` within 15 minutes).
- Second useful chain: **port scan → brute force** (same `src_ip` triggers both within 15 minutes — high signal for service discovery followed by credential attack).
- `rule_id` format: `corr-chain-{chain_name}` (e.g. `corr-chain-recon-to-exploit`) — filterable via `corr-` prefix.

### Claude's Discretion
- Exact DuckDB SQL for beaconing CV calculation (stddev/mean window function approach)
- How correlation dedup state is stored (SQLite table vs in-memory set with TTL)
- Whether chain YAML is hot-reloaded or requires restart
- Exact filter chip placement in DetectionsView

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `detections/matcher.py` — `SigmaMatcher.run_all()` + `save_detections()` pattern; correlation engine should follow the same async run → save flow
- `backend/models/event.py:DetectionRecord` — `id, rule_id, rule_name, severity, matched_event_ids, attack_technique, attack_tactic, explanation, case_id, created_at` — use as-is for correlation detections
- `backend/services/anomaly/scorer.py` — Phase 42 synthetic detection creation pattern (`rule_id='anomaly-*'`); correlation uses same `rule_id='corr-*'` prefix convention
- `backend/api/correlate.py` — existing correlate router already registered at `/correlate`; extend or add new endpoints here rather than a new file
- `dashboard/src/views/DetectionsView.svelte` — has existing filter chip UI; extend filter state to include `CORR` type

### Established Patterns
- Ingest pipeline trigger: `ingestion/loader.py` calls Sigma matching after batch write; same hook for correlation
- `asyncio.to_thread()` for all DuckDB reads
- `rule_id` prefix convention: `sigma-*` (Sigma rules), `anomaly-*` (Phase 42), `corr-*` (Phase 43)
- Dedup pattern: check SQLite for existing detection with same `rule_id + entity_key` within window before inserting
- Settings singleton: `from backend.core.config import settings`

### Integration Points
- `ingestion/loader.py` — add `await correlation_engine.run(stores)` call after Sigma matching in the ingest batch loop
- `backend/core/config.py` — add `CORRELATION_LOOKBACK_HOURS: int = 2` and `CORRELATION_DEDUP_WINDOW_MINUTES: int = 60`
- `dashboard/src/views/DetectionsView.svelte` — add `CORR` to filter chips; add correlation type badge to detection rows; add expand-to-events UI
- `dashboard/src/lib/api.ts` — `DetectionRecord` interface may need `correlation_type` field and `matched_event_count` for the row display

</code_context>

<specifics>
## Specific Ideas

- The `corr-` prefix on all correlation rule IDs makes them trivially filterable across DetectionsView, the API, and future analytics — same pattern as `anomaly-*` worked well in Phase 42.
- Pre-configured chains: recon→scan→exploit and scan→bruteforce. These two cover the most common automated attack sequences visible in Malcolm/Zeek data.
- YAML chain config at `detections/correlation_chains.yml` means adding a new chain is a file edit, not a code change.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.

</deferred>

---

*Phase: 43-sigma-v2-correlation-rules*
*Context gathered: 2026-04-12*
