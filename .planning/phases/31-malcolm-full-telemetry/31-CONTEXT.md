# Phase 31: Malcolm Real Telemetry + Evidence Archive — Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 31 delivers three things:

1. **Expand EVE collection** — Malcolm collector now polls ALL 5 Suricata EVE event types in OpenSearch (currently only alerts + syslog are collected; 235K TLS/DNS/file/anomaly events are ignored). No hardware required — these docs are already indexed.

2. **Raw evidence archive on Ubuntu (supportTAK-server)** — Daily gzip archives of raw syslog and EVE JSON written to external drive with SHA256 checksums at write time. Forensic chain of custody. Ubuntu writes, desktop never touches raw files.

3. **Ubuntu normalization pipeline** — Lightweight Python process on the N150: reads incoming syslog + EVE → writes ECS-normalized NDJSON to a local HTTP endpoint → desktop polls every 60s. No AI. No interpretation. Pure format conversion to take parsing load off the desktop.

**Out of scope (Phase 36):** Zeek log normalizers — deferred pending managed switch (Cisco SG350-8 or Netgear GS308E, ~$50-80). Zeek containers currently produce zero data without a SPAN port.

**Also out of scope:** Removing Ollama/theater containers from Ubuntu — that's a separate cleanup task (infrastructure, not code).

</domain>

<decisions>
## Implementation Decisions

### EVE Event Type Expansion
- Expand `_poll_and_ingest()` in `ingestion/jobs/malcolm_collector.py` to poll all 5 EVE types from `arkime_sessions3-*`:
  - `alert` (already collected) — keep as-is
  - `tls` — 156,933 docs in OpenSearch today
  - `dns` — 70,883 docs in OpenSearch today
  - `fileinfo` — 6,416 docs in OpenSearch today
  - `anomaly` — 1,280 docs in OpenSearch today
- Each EVE type gets its own `_normalize_<type>()` method mirroring `_normalize_alert()` pattern
- Each EVE type gets its own SQLite cursor key (e.g., `malcolm.tls.last_timestamp`, `malcolm.dns.last_timestamp`)
- `event_type` field values: `"tls"`, `"dns_query"`, `"file_transfer"`, `"anomaly"` (mapped to OCSF class UIDs)

### NormalizedEvent Schema Expansion (~20 new fields)
- Add fields to `NormalizedEvent` and run DuckDB migration via `_ECS_MIGRATION_COLUMNS` pattern (try/except ADD COLUMN — idempotent):
  - DNS: `dns_query` (TEXT), `dns_query_type` (TEXT), `dns_rcode` (TEXT), `dns_answers` (TEXT), `dns_ttl` (INTEGER)
  - TLS: `tls_version` (TEXT), `tls_ja3` (TEXT), `tls_ja3s` (TEXT), `tls_sni` (TEXT), `tls_cipher` (TEXT), `tls_cert_subject` (TEXT), `tls_validation_status` (TEXT)
  - File: `file_md5` (TEXT), `file_sha256_eve` (TEXT), `file_mime_type` (TEXT), `file_size_bytes` (INTEGER)
  - HTTP: `http_method` (TEXT), `http_uri` (TEXT), `http_status_code` (INTEGER), `http_user_agent` (TEXT)
- `to_duckdb_row()` extended with these fields appended at the end (same additive pattern as Phase 20 ECS fields)

### Raw Evidence Archive (Ubuntu box)
- **Format:** Daily gzip per log type, named `{YYYY-MM-DD}.log.gz` / `{YYYY-MM-DD}.json.gz`
- **Rotation:** At midnight UTC, close and compress current day's file, compute SHA256, write to `checksums/{YYYY-MM-DD}.sha256`
- **Archive root:** `EVIDENCE_ARCHIVE_PATH` env var (default `/mnt/evidence`) — exact path set by hardware spec session
- **Structure:**
  ```
  $EVIDENCE_ARCHIVE_PATH/
    raw/
      syslog/YYYY-MM-DD.log.gz
      eve/YYYY-MM-DD.json.gz
    checksums/
      YYYY-MM-DD.sha256
  ```
- **Write rule:** Raw bytes only. Never parsed, never modified. Desktop never writes to this path.
- **Implemented as:** Python `EvidenceArchiver` class on Ubuntu, runs as systemd service alongside Malcolm

### Ubuntu Normalization Pipeline
- **Input:** Tails live syslog (received on :5514) and EVE JSON from SCP'd files
- **Output:** ECS-normalized NDJSON written to `/var/lib/soc-pipeline/normalized/{YYYY-MM-DD}.ndjson.gz`
- **HTTP endpoint:** Lightweight FastAPI (or Flask) on Ubuntu exposes:
  - `GET /normalized/{date}` → streams the day's gzip NDJSON
  - `GET /normalized/latest` → today's partial file (live)
  - `GET /normalized/index` → list of available dates with doc counts
- **Desktop consumption:** Malcolm collector polls `GET /normalized/latest` every 60s for incremental updates. Uses cursor tracking (same SQLite pattern as OpenSearch polling).
- **No AI on Ubuntu** — pure format conversion: field rename, type coerce, severity map. Nothing inferred.

### EventsView Filter Chips
- Add horizontal chip row above event table in `EventsView.svelte`
- Chips: All | Alert | TLS | DNS | File | Anomaly | Syslog
- Filter maps to `event_type` field in DuckDB query (backend `GET /api/events` gets `?event_type=dns_query` param)
- Single-select (one active chip at a time)
- "All" chip selected by default

### Claude's Discretion
- Exact FastAPI route structure for Ubuntu normalization HTTP server
- Whether to run EvidenceArchiver as asyncio task within the same process or separate systemd unit
- NDJSON batch size and flush interval for the Ubuntu endpoint
- How to handle gaps in EVE SCP delivery (skip silently vs backfill)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ingestion/jobs/malcolm_collector.py` — `_normalize_alert()` and `_normalize_syslog()` are the exact pattern to clone for 4 new EVE normalizers. `_fetch_index()` with cursor key already handles per-index timestamp tracking.
- `backend/stores/duckdb_store.py` — `_ECS_MIGRATION_COLUMNS` list + try/except ADD COLUMN loop is the migration pattern. Append new columns to this list.
- `backend/models/event.py` — `to_duckdb_row()` already appends ECS fields at positions 29-34. New EVE fields go at positions 35-54 using same pattern.
- `dashboard/src/views/EventsView.svelte` — table already renders `event_type` column. Filter chips wire to `?event_type=` query param on the existing `GET /api/events` endpoint.
- `backend/api/events.py` — add optional `event_type` query param, pass to DuckDB WHERE clause.

### Established Patterns
- **Cursor tracking:** SQLite `system_kv` table, key = `malcolm.{type}.last_timestamp`, value = ISO timestamp. One key per polled index/type.
- **Normalization:** Each normalizer returns `NormalizedEvent | None` (None = drop silently). All return immediately, no async.
- **Migration:** `ALTER TABLE normalized_events ADD COLUMN {name} {type}` wrapped in try/except. DuckDB raises if column exists — catch and continue.
- **Svelte 5:** `$state()` for filter chip selection, `$effect()` to re-fetch when chip changes.

### Integration Points
- **Ubuntu → Desktop:** Desktop Malcolm collector adds a new poll source alongside OpenSearch: `GET http://192.168.1.22:{PORT}/normalized/latest` every 60s
- **DuckDB:** New columns added via migration; existing rows get NULL for new fields (correct behavior)
- **EventsView:** New `?event_type` param on `GET /api/events` — backend adds optional WHERE clause

### What Doesn't Exist Yet
- Ubuntu normalization HTTP server (new service, Python)
- `EvidenceArchiver` class (new, Ubuntu-side)
- EVE normalizers for TLS, DNS, fileinfo, anomaly (new methods in malcolm_collector.py)
- EventsView chip UI (new Svelte component)

</code_context>

<specifics>
## Specific Requirements

- **No AI on Ubuntu** — explicit constraint. Ubuntu is a dumb pipe. No inference, no summarization, no interpretation.
- **Forensic integrity** — SHA256 at write time, not at read time. The checksum proves the file was not modified after archival.
- **Evidence archive is write-once** — the Python archiver appends raw bytes, never overwrites. Desktop has read-only access.
- **235K ignored events** — TLS (156K), DNS (71K), files (6K), anomalies (1K) are already in OpenSearch. This is the immediate gain with zero hardware.
- **Zeek is theater** — Malcolm's zeek-1, zeek-live-1 containers produce zero logs without SPAN. Zeek normalizers deferred to Phase 36.
- **Theater containers** (17 idle Malcolm containers, Ollama on Ubuntu) — infrastructure cleanup, not in Phase 31 code scope.

</specifics>

<deferred>
## Deferred Ideas

- **Zeek full telemetry (Phase 36)** — All 40+ Zeek log types. Requires managed switch with SPAN port (Cisco SG350-8 or Netgear GS308E, ~$50-80). Phase 36 starts when hardware is installed and Zeek containers are producing data.
- **Remove theater containers from Ubuntu** — kill 17 idle Malcolm containers + Ollama. Infrastructure task, not Phase 31 code. Do this manually or in a dedicated infra cleanup session.
- **Bidirectional archive sync** — replicating Ubuntu evidence archive to desktop for local forensics. Future.
- **Malcolm WebSocket real-time feed** — replace polling with push. Future optimization.

</deferred>

---

*Phase: 31-malcolm-full-telemetry*
*Context gathered: 2026-04-09*
