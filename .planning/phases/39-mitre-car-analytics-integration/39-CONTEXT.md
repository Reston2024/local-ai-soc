# Phase 39: MITRE CAR Analytics Integration - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Enrich existing detections with MITRE CAR (Cyber Analytics Repository) analytics. When a Sigma rule fires and has an ATT&CK technique ID, surface the matching CAR analytic(s) — detection rationale, log-source requirements, analyst guidance, implementation pseudocode — in the DetectionsView expanded row and the investigation evidence panel. No new detection logic. No new alert sources. Pure enrichment layer on top of what already fires.

</domain>

<decisions>
## Implementation Decisions

### CAR data source
- Bundle a full JSON snapshot of the CAR catalog in `backend/data/car_analytics.json` — committed to repo, no GitHub dependency at runtime
- Full catalog (~130 analytics), not a curated subset — covers any Sigma rule that fires, not just CISA playbook techniques
- Seed into DB at startup (same startup-seed pattern as STIX/playbooks/IOC store)
- CAR catalog refresh is a future phase — one-time bundle is fine for v1

### Storage
- SQLite table, not DuckDB — consistent with all other reference/catalog data (STIX, IOC store, playbooks)
- P39-T01 requirement text says DuckDB — override to SQLite per established pattern
- DuckDB remains for time-series events only

### Enrichment timing
- CAR lookup happens synchronously at detection time — same pattern as Phase 33 IOC matching
- `attack_technique` ID from the fired Sigma rule → SQLite SELECT → matched analytics attached to detection record
- If no `attack_technique` on the detection → `car_analytics` field is null/omitted (not a placeholder, just absent)
- CAR analytic data embedded as nested object(s) directly in the GET /api/detections response — no separate endpoint

### CAR analytic panel in DetectionsView
- Expandable row — click a detection row to expand inline panel below the row (not a side drawer, not a separate tab)
- All four CAR fields shown: ID + title + description, log sources required, analyst guidance/notes, implementation pseudocode
- Two outbound links: CAR analytic link (car.mitre.org/analytics/CAR-XXXX-XX-XXX) + ATT&CK technique link (attack.mitre.org/techniques/TXXXX) — consistent with Phase 38 chip pattern

### Match scope
- Show all CAR analytics that match the technique, not just one — some techniques (e.g. T1059) have 4+ CAR entries
- Each analytic displayed as a separate card/section within the expanded row panel, ordered by analytic ID
- P39-T05 included: CAR analytics also appear in the investigation evidence panel (not DetectionsView only)

### Claude's Discretion
- Exact SQLite schema for the car_analytics table (columns, indexes)
- Exact JSON structure of the bundled snapshot (may need transformation from raw CAR YAML/JSON format)
- How to display multiple CAR analytics in the expanded row (stacked cards vs tabs vs accordion)
- How CAR analytics surface in the investigation evidence panel (new section, or appended to existing technique evidence)
- Whether to add a `car_analytic_ids` TEXT column to the detections table or compute at query time via JOIN

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/stores/sqlite_store.py`: All reference-data stores live here. IocStore and AttackStore patterns to follow for CARStore.
- `backend/data/builtin_playbooks.py`: Seeding pattern at startup via `seed_builtin_playbooks()` — same approach for CAR.
- `backend/api/detect.py` line 43/190: `attack_technique` already stored on detection — the JOIN key for CAR lookup is already there.
- `detections/matcher.py` + `backend/stores/sqlite_store.py` `save_detection()`: Where ATT&CK tagging happens — CAR lookup plugs in alongside existing technique enrichment.
- Phase 33 IOC matching (`_apply_ioc_matching()` in loader.py): Sync enrichment pattern to replicate for CAR.
- Phase 34 ATT&CK store (`AttackStore`): `sqlite_store.py` SQLite reference table pattern to copy for `CARStore`.

### Established Patterns
- Reference data → SQLite (IocStore, AttackStore, PlaybookStore). Not DuckDB.
- Sync enrichment at detection time → `asyncio.to_thread` wrapper if needed for SQLite reads.
- Startup seed → check if table populated, if empty seed from bundled data file.
- Nested enrichment in API response → Phase 33 IOC hit fields already embedded in NormalizedEvent responses.
- Svelte 5 runes: `$state`, `$derived`, `$effect` — no stores.

### Integration Points
- `backend/stores/sqlite_store.py`: Add `CARStore` class (or extend `AttackStore`) with `get_analytics_for_technique(technique_id) -> list[dict]`
- `detections/matcher.py` or `backend/stores/sqlite_store.py` `save_detection()`: Call `car_store.get_analytics_for_technique()` after technique ID is known, store result
- `backend/api/detect.py` or `backend/api/detections.py`: Include `car_analytics` field in detection response shape
- `dashboard/src/lib/api.ts`: Extend `Detection` interface with `car_analytics?: CARAnalytic[]`
- `dashboard/src/views/DetectionsView.svelte`: Add expandable row (no existing expansion pattern — new pattern)
- `backend/api/investigate.py` or `backend/api/investigations.py`: Add CAR analytic section to investigation evidence (P39-T05)

</code_context>

<specifics>
## Specific Ideas

- The expandable row pattern in DetectionsView is new — no prior expansion exists. Should feel natural/compact: click anywhere on the row (or a chevron icon) to expand. Collapsed state keeps the table dense.
- Multiple CAR analytics per technique should stack vertically, each as a distinct card with its own ID badge, not tabs — tabs would hide content that analysts need to compare.
- The CAR analytic ID (e.g. "CAR-2020-09-001") should be displayed as a monospace badge, similar to ATT&CK technique chips in PlaybooksView — consistent visual language across MITRE content.

</specifics>

<deferred>
## Deferred Ideas

- CAR catalog refresh/update mechanism (scripts/update_car.py) — future phase
- CAR analytics in HuntingView (surface analyticsfor active hunt queries) — future phase
- CAR pseudocode → Sigma rule auto-generation — separate, complex phase
- CAR coverage heatmap (which techniques have CAR coverage vs just Sigma) — could extend AttackCoverageView, future phase

</deferred>

---

*Phase: 39-mitre-car-analytics-integration*
*Context gathered: 2026-04-11*
