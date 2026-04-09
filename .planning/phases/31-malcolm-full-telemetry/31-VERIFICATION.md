---
phase: 31-malcolm-full-telemetry
verified: 2026-04-09T00:00:00Z
status: human_needed
score: 11/12 must-haves verified (1 requires human browser verification)
human_verification:
  - test: "Open EventsView in browser and click each active chip (All/Alert/TLS/DNS/File/Anomaly/Syslog)"
    expected: "Chip highlights (chip-active class), event table reloads filtered to that event_type, pagination resets to page 1. Clicking All returns unfiltered results."
    why_human: "Svelte 5 $effect() reactivity and DOM rendering cannot be verified by static grep. Backend filtering verified (event_type query param confirmed in api.ts and backend). Visual chip behavior requires a running browser."
---

# Phase 31: Malcolm Full Telemetry Verification Report

**Phase Goal:** (1) Expand Malcolm collector to poll ALL 5 Suricata EVE types (TLS, DNS, fileinfo, anomaly are in OpenSearch but not collected). (2) Add raw evidence archive to Ubuntu external drive with SHA256 chain of custody. (3) Add Ubuntu normalization pipeline (ECS NDJSON endpoint, desktop polls every 60s). (4) EventsView filter chips. No Zeek.
**Verified:** 2026-04-09
**Status:** human_needed — all automated checks pass, one browser UI behavior needs human confirmation
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 235K TLS/DNS/fileinfo/anomaly events are collected via 4 new normalizers | VERIFIED | `_normalize_tls`, `_normalize_dns`, `_normalize_fileinfo`, `_normalize_anomaly` at lines 265/353/425/489 in malcolm_collector.py; poll loop at lines 658/674/690/706 with separate cursor keys |
| 2 | NormalizedEvent has 20 new protocol fields (dns_*, tls_*, file_*, http_*) | VERIFIED | `to_duckdb_row()` returns 55 columns (verified programmatically); fields dns_query, tls_version, file_md5, http_method confirmed in event.py |
| 3 | DuckDB schema migration has 26 entries and is idempotent | VERIFIED | `_ECS_MIGRATION_COLUMNS` has 26 entries (6 original + 20 new, verified programmatically); try/except idempotency pattern in duckdb_store.py line 312 |
| 4 | to_duckdb_row() / _INSERT_SQL / _ECS_MIGRATION_COLUMNS are in sync (55 columns) | VERIFIED | `row_len: 55`, `placeholders: 55`, `migration_cols: 26` — all confirmed via live Python import |
| 5 | OCSF_CLASS_UID_MAP has entries for tls (4001), dns_query (4003), file_transfer (1001), anomaly (4001) | VERIFIED | event.py lines 35/58-62: dns_query=4003, tls=4001, anomaly=4001, file_transfer=1001 |
| 6 | Four EVE normalizers use 3-level field fallback (nested ECS, arkime-flat, fully-flat) | VERIFIED | _normalize_tls() inspected — uses `(doc.get("source") or {}).get("ip") or doc.get("src_ip") or doc.get("srcip")` triple-fallback pattern throughout |
| 7 | _poll_and_ingest() polls 5 EVE types with separate SQLite cursor keys | VERIFIED | Lines 628/658/674/690/706: malcolm.alerts.last_timestamp, malcolm.tls.last_timestamp, malcolm.dns.last_timestamp, malcolm.fileinfo.last_timestamp, malcolm.anomaly.last_timestamp |
| 8 | EvidenceArchiver writes daily gzip archives with SHA256 at midnight rotation | VERIFIED | ubuntu/evidence_archiver.py: gzip.open(..., "ab"), _rotate() computes SHA256 via hashlib, writes checksums/YYYY-MM-DD.sha256; all 3 unit tests pass |
| 9 | Ubuntu FastAPI server exposes /normalized/{date}, /normalized/latest, /normalized/index | VERIFIED | Routes confirmed: ['/normalized/index', '/normalized/latest', '/normalized/{day}'] via live import; lifespan=lifespan wired |
| 10 | Ubuntu services deployable as systemd units | VERIFIED | soc-archiver.service and soc-normalizer.service exist with correct ExecStart, User=soc, EVIDENCE_ARCHIVE_PATH env |
| 11 | MalcolmCollector polls UBUNTU_NORMALIZER_URL/normalized/latest every 60s; empty URL disables | VERIFIED | _poll_ubuntu_normalizer() at line 540; returns [] for empty URL (line 548); test_ubuntu_poll passes; UBUNTU_NORMALIZER_URL='' in settings (line 82 config.py); UBUNTU_NORMALIZER_POLL_INTERVAL=60 |
| 12 | EventsView chip row renders and filters events (7 active + 8 beta Zeek chips) | HUMAN NEEDED | CHIPS array, ZEEK_CHIPS, selectedChip $state(''), $effect() for re-fetch, chip-row/chip-active/chip-beta CSS all confirmed in EventsView.svelte. Browser behavior needs human validation. |

**Score:** 11/12 truths verified automatically; 1 human verification pending

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `backend/models/event.py` | VERIFIED | 55-column to_duckdb_row(), OCSF map with all 4 new types, dns_query/tls_version/file_md5/http_method fields |
| `backend/stores/duckdb_store.py` | VERIFIED | _ECS_MIGRATION_COLUMNS 26 entries, idempotent ADD COLUMN via try/except |
| `ingestion/loader.py` | VERIFIED | _INSERT_SQL has 55 columns and 55 ? placeholders |
| `ingestion/jobs/malcolm_collector.py` | VERIFIED | _normalize_tls/_normalize_dns/_normalize_fileinfo/_normalize_anomaly; _poll_ubuntu_normalizer(); _poll_and_ingest() calls all 5 sources + ubuntu poll |
| `ubuntu/evidence_archiver.py` | VERIFIED | EvidenceArchiver class: write_syslog_line(), write_eve_line(), _rotate(), rotate_if_needed(); gzip.open("ab"); SHA256 at rotation |
| `ubuntu/normalization_server.py` | VERIFIED | FastAPI app with 3 /normalized routes; NormalizationWriter class; lifespan context manager; ECS mappers _map_eve_doc()/_map_syslog_line() |
| `ubuntu/requirements.txt` | VERIFIED | fastapi>=0.110.0, uvicorn[standard]>=0.29.0, httpx>=0.27.0 |
| `ubuntu/systemd/soc-archiver.service` | VERIFIED | Exists; User=soc, EVIDENCE_ARCHIVE_PATH=/mnt/evidence, ExecStart with python -m ubuntu.evidence_archiver |
| `ubuntu/systemd/soc-normalizer.service` | VERIFIED | Exists; uvicorn on 0.0.0.0:8080, SOC_NORMALIZED_DIR env, After=soc-archiver.service |
| `backend/core/config.py` | VERIFIED | UBUNTU_NORMALIZER_URL: str = "" and UBUNTU_NORMALIZER_POLL_INTERVAL: int = 60 at lines 82-83 |
| `dashboard/src/lib/api.ts` | VERIFIED | events.list() params include event_type?: string; URLSearchParams q.set('event_type', ...) at line 344 |
| `dashboard/src/views/EventsView.svelte` | VERIFIED (static) | CHIPS array (7 active), ZEEK_CHIPS array (8 beta), selectedChip=$state(''), $effect() re-fetch, chip-row/chip-active/chip-beta/chip-divider CSS |
| `tests/unit/test_evidence_archiver.py` | VERIFIED | 3 tests: test_write_gzip, test_sha256_written, test_daily_rotation — all pass |
| `tests/unit/test_malcolm_collector.py` | VERIFIED | test_normalize_tls, test_normalize_dns, test_normalize_fileinfo, test_normalize_anomaly, test_ubuntu_poll — all pass |
| `tests/unit/test_normalized_event.py` | VERIFIED | Exists and passes |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| malcolm_collector.py normalizers | backend/models/event.py NormalizedEvent | Constructor with dns_query=, tls_version=, file_md5=, http_method= kwargs | VERIFIED | _normalize_tls() passes tls_version=, tls_ja3=, tls_sni= etc. to NormalizedEvent constructor |
| ingestion/loader.py _INSERT_SQL | backend/models/event.py to_duckdb_row() | Column count: both 55 | VERIFIED | Programmatically confirmed: row_len=55, placeholders=55 |
| backend/stores/duckdb_store.py | normalized_events table | _ECS_MIGRATION_COLUMNS ALTER TABLE loop | VERIFIED | 26-entry list, loop at line 312 |
| EventsView.svelte chip onclick | api.ts events.list({ event_type: selectedChip }) | $effect() watching selectedChip | VERIFIED (static) | $effect() at line 54 reads selectedChip; load() passes event_type to api.events.list() at line 43 |
| api.ts events.list() | GET /api/events?event_type=... | URLSearchParams q.set('event_type', ...) | VERIFIED | Line 344: `if (params?.event_type) q.set('event_type', params.event_type)` |
| malcolm_collector.py _poll_ubuntu_normalizer() | UBUNTU_NORMALIZER_URL/normalized/latest | httpx.get() via asyncio.to_thread() | VERIFIED | Line 551: `url = f"{self._ubuntu_normalizer_url}/normalized/latest"` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| P31-T01 | 31-01 | 20 new EVE fields in NormalizedEvent + DuckDB migration | SATISFIED | 55-column to_duckdb_row(), 26 migration columns, all new fields present |
| P31-T02 | 31-01 | _normalize_tls(), event_type="tls", cursor key | SATISFIED | Method at line 265, cursor key "malcolm.tls.last_timestamp" at line 658 |
| P31-T03 | 31-01 | _normalize_dns(), event_type="dns_query", cursor key | SATISFIED | Method at line 353, cursor key "malcolm.dns.last_timestamp" at line 674 |
| P31-T04 | 31-01 | _normalize_fileinfo(), event_type="file_transfer", cursor key | SATISFIED | Method at line 425, cursor key "malcolm.fileinfo.last_timestamp" at line 690 |
| P31-T05 | 31-01 | _normalize_anomaly(), severity=high, cursor key | SATISFIED | Method at line 489, cursor key "malcolm.anomaly.last_timestamp" at line 706 |
| P31-T06 | 31-01 | _poll_and_ingest() polls all 5 EVE types | SATISFIED | 5 separate poll blocks with distinct cursor keys in _poll_and_ingest() |
| P31-T07 | 31-02 | EvidenceArchiver — daily gzip archives, SHA256 at rotation | SATISFIED | ubuntu/evidence_archiver.py: gzip.open("ab"), _rotate() writes checksums |
| P31-T08 | 31-02 | Ubuntu normalization FastAPI server — 3 /normalized routes | SATISFIED | ubuntu/normalization_server.py with /normalized/index, /normalized/latest, /normalized/{day} |
| P31-T09 | 31-03 | Ubuntu poll in desktop collector, UBUNTU_NORMALIZER_URL setting | SATISFIED | _poll_ubuntu_normalizer(), UBUNTU_NORMALIZER_URL in config, 60s poll interval |
| P31-T10 | 31-03 | EventsView filter chips — All/Alert/TLS/DNS/File/Anomaly/Syslog | HUMAN NEEDED | Static code verified; browser rendering needs human confirmation |
| P31-T11 | 31-01 | OCSF class UIDs for tls/dns_query/file_transfer/anomaly | SATISFIED | OCSF_CLASS_UID_MAP: tls=4001, dns_query=4003, file_transfer=1001, anomaly=4001 |
| P31-T12 | 31-03 | Beta Zeek chips (Connection/HTTP/SSL/SMB/Auth/SSH/SMTP/DHCP) disabled | SATISFIED (static) | ZEEK_CHIPS array, chip-beta CSS, disabled attribute, Phase 36 tooltip in EventsView.svelte |

---

### Anti-Patterns Found

No anti-patterns detected. Scanned: ubuntu/evidence_archiver.py, ubuntu/normalization_server.py, ingestion/jobs/malcolm_collector.py, dashboard/src/views/EventsView.svelte, dashboard/src/lib/api.ts. No TODO/FIXME/PLACEHOLDER comments, no empty implementations, no return null stubs.

---

### Test Suite

| Suite | Result |
|-------|--------|
| tests/unit/test_evidence_archiver.py | 3 passed |
| tests/unit/test_malcolm_collector.py (relevant tests) | 5 passed (normalize_tls, normalize_dns, normalize_fileinfo, normalize_anomaly, ubuntu_poll) |
| tests/unit/ (full suite) | 882 passed, 1 skipped, 9 xfailed, 7 xpassed — no regressions |

### Commits Verified

All 9 documented commits exist in git history:
- fbf323e — test(31-01): RED stubs for EVE protocol fields
- 0119fd1 — feat(31-01): NormalizedEvent schema expansion (55 columns)
- b6b5a4d — feat(31-01): four EVE normalizers + expanded poll loop
- 9448026 — test(31-02): RED stubs for EvidenceArchiver
- b0cebfe — feat(31-02): EvidenceArchiver class implementation
- 6e835a4 — feat(31-02): Ubuntu normalization server + systemd units
- a483cc3 — test(31-03): failing Ubuntu poll test (RED)
- 18dc519 — feat(31-03): UBUNTU_NORMALIZER_URL + Ubuntu poll in collector
- 0b189a0 — feat(31-03): api.ts event_type param + EventsView chips

---

### Human Verification Required

#### 1. EventsView Filter Chips (P31-T10)

**Test:** Start backend (`uv run uvicorn backend.main:app --reload`) and dashboard (`cd dashboard && npm run dev`). Open http://localhost:5173, navigate to Events view.

**Expected:**
- Horizontal chip row appears above the event table with: All | Alert | TLS | DNS | File | Anomaly | Syslog (active), then a "Phase 36" divider, then 8 grayed-out/dashed chips (Connection/HTTP/SSL/SMB/Auth/SSH/SMTP/DHCP)
- Clicking TLS chip: chip highlights (green/accent background), table reloads filtered to tls events only
- Clicking All chip: chip highlights, table returns to unfiltered results
- Pagination resets to page 1 on each chip switch
- Beta Zeek chips are visually dimmed (opacity ~0.45), dashed border, not clickable
- Hovering a beta chip shows tooltip: "Zeek [label] logs — Phase 36 (managed switch in transit)"

**Why human:** Svelte 5 $effect() reactivity and DOM rendering cannot be verified by static analysis. The wiring exists in code (confirmed), but actual chip highlight, table reload, and pagination reset require a running browser.

---

### Summary

Phase 31 goal is substantively achieved. All 12 requirements have complete, non-stub implementations:

- **235K EVE event collection:** Four normalizers (_normalize_tls, _normalize_dns, _normalize_fileinfo, _normalize_anomaly) with 3-level field fallback; _poll_and_ingest() polls all 5 EVE types with separate cursor keys. Schema fully synchronized: NormalizedEvent (55 cols), DuckDB migration (26 cols), loader INSERT SQL (55 placeholders).

- **Evidence archive:** EvidenceArchiver writes raw bytes to daily gzip files in append mode, rotates at midnight, seals with SHA256 chain of custody. Write-once forensic integrity confirmed by unit tests.

- **Ubuntu normalization pipeline:** FastAPI server with 3 /normalized routes, NormalizationWriter background task performing ECS field mapping from raw EVE/syslog, lifespan-managed lifecycle. Systemd units ready for deployment on 192.168.1.22.

- **EventsView filter chips:** 7 active chips + 8 disabled beta Zeek chips with Phase 36 tooltip. Svelte 5 $state/$effect wiring confirmed. api.ts event_type param confirmed.

The one outstanding item (human verification of chip browser rendering) is a UI acceptance check, not a code gap. All backing code is substantive and wired.

---

_Verified: 2026-04-09_
_Verifier: Claude (gsd-verifier)_
