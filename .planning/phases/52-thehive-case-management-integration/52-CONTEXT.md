# Phase 52: TheHive Case Management Integration - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy TheHive 5.x + Cortex as Docker containers on the GMKtec (alongside Malcolm). Wire SOC Brain's detection pipeline to auto-create TheHive cases for High/Critical detections. Add case ID + status badge and "Open in TheHive" deep-link to DetectionsView and InvestigationView. Poll TheHive every 5 minutes to sync case closures (verdict, timestamp, analyst) back to SOC Brain SQLite. Deploy Cortex with 4 analysers (AbuseIPDB, MaxMind GeoIP, MISP, VirusTotal) running parallel to existing Phase 32 OSINT enrichment.

</domain>

<decisions>
## Implementation Decisions

### Auto-Case Threshold
- Severity trigger: **High and Critical only** — Medium/Low are noise
- Creation mode: **Immediate** — each qualifying detection fires its own case on detection, no batching
- Per-rule suppression: **Yes** — a configurable `THEHIVE_SUPPRESS_RULES` list of rule_ids in config/settings that skip auto-case creation even if severity qualifies (for tuning noisy rules)
- TheHive unreachable: **Retry queue** — store pending case creation in a SQLite table (`thehive_pending_cases`), retry on next detection cycle. Detection pipeline must never block on TheHive availability.

### Open in TheHive UX
- Button placement: **Detection expanded panel** AND **InvestigationView header** (alongside Summary/Agent/OSINT tabs)
- Button behavior: **Open existing case** — deep-links to the TheHive case URL (`http://192.168.1.22:9000/cases/{thehive_case_id}`). Does not create cases on click (auto-creation handles that)
- Inline badge: **Yes** — show `Case #N · In Progress` (or Resolved/New) as a small status badge on the detection row and in the expanded panel. Requires a lightweight status field stored in SQLite alongside `thehive_case_id`
- TheHive URL: **Hardcoded in config** — `THEHIVE_URL=http://192.168.1.22:9000` in `.env`/settings. No DNS required.

### Closure Sync
- Mechanism: **Polling** — background APScheduler task in SOC Brain polls TheHive `/api/case?status=Resolved` every **5 minutes**
- Fields synced back to SOC Brain SQLite on closure:
  - **Case status** (True Positive / False Positive / Indeterminate) → written to detection's verdict field
  - **Closure timestamp** — when the case was resolved in TheHive
  - **Assigned analyst** — who worked the case (TheHive assignee field)
- New SQLite columns on detections: `thehive_case_id`, `thehive_status`, `thehive_closed_at`, `thehive_analyst`

### Cortex Scope
- **Required in Phase 52** — deploy alongside TheHive in the same Docker Compose stack on GMKtec
- Analysers to enable: **AbuseIPDB** (reuse `ABUSEIPDB_API_KEY`), **MaxMind GeoIP** (local mmdb, no API), **MISP** (native TheHive–MISP integration), **VirusTotal** (reuse `VT_API_KEY`)
- Relationship to Phase 32 OSINT: **Parallel** — Phase 32 enrichment continues enriching detections in SOC Brain independently. Cortex enriches observables inside TheHive's case workflow. Different audiences, no sync between them.

### Claude's Discretion
- TheHive + Cortex Docker Compose specifics (image versions, volume paths, network config on GMKtec)
- TheHive case template structure (title format, tags, TLP/PAP settings)
- Cortex analyser configuration files
- SQLite migration approach for new `thehive_*` columns
- Retry queue schema details for `thehive_pending_cases`
- Polling task implementation (APScheduler vs asyncio loop)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/api/detect.py` — `case_id` field already on detections (SOC Brain investigation ID). Add `thehive_case_id` as a separate field to avoid collision.
- `backend/stores/sqlite_store.py` — ALTER TABLE migration pattern already established (idempotent `try/except` columns). Use same pattern for `thehive_*` columns.
- `backend/api/health.py` — `_check_spiderfoot()` pattern for optional service health checks. Add `_check_thehive()` and `_check_cortex()` as siblings.
- `backend/core/config.py` — Settings class with `SPIDERFOOT_BASE_URL` pattern. Add `THEHIVE_URL`, `THEHIVE_API_KEY`, `THEHIVE_SUPPRESS_RULES`.
- APScheduler already running in `backend/api/metrics.py` — reuse for 5-minute closure sync job.
- `dashboard/src/views/DetectionsView.svelte` — expanded panel already exists; `case_id` badge already shown on detection rows (line 369 "Open investigation cases"). "Open in TheHive" button slots in alongside existing actions.
- `dashboard/src/views/InvestigationView.svelte` — tab header area already has Summary/Agent/OSINT. TheHive case badge + button goes in the header, not a new tab.

### Established Patterns
- `asyncio.to_thread()` for all blocking I/O (TheHive httpx calls are async but SQLite writes are sync)
- On-demand service clients with graceful failure (`try/except` in route handlers, `503` if service unavailable)
- SSE streaming not needed here — case creation is fire-and-forget, sync is background
- Docker Compose for optional services (`infra/docker-compose.spiderfoot.yml` pattern) — mirror for TheHive+Cortex on GMKtec

### Integration Points
- `detections/matcher.py` or `backend/api/detect.py` — hook into detection save to trigger TheHive case creation for qualifying severities
- `backend/stores/sqlite_store.py` — new columns + `thehive_pending_cases` table
- `backend/main.py` — register TheHive client in lifespan (same `app.state.thehive_client` pattern as `osint_store`)
- GMKtec `docker-compose.yml` — add TheHive + Cortex services (separate file, deployed manually via SSH)

</code_context>

<specifics>
## Specific Ideas

- TheHive case title format: `[{severity}] {rule_name} — {src_ip}` (e.g., `[HIGH] Mimikatz Detected — 192.168.1.55`)
- Case badge in DetectionsView: small pill next to severity badge, same style — `#42 · In Progress` in amber, `#42 · Resolved` in green
- `thehive_pending_cases` table is the reliability backstop — TheHive going down should never lose a case or stall detection ingestion

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 52-thehive-case-management-integration*
*Context gathered: 2026-04-16*
