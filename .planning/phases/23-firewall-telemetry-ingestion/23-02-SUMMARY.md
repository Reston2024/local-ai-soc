---
phase: 23-firewall-telemetry-ingestion
plan: "02"
subsystem: ingestion/parsers
tags: [suricata, eve, ndjson, parser, mitre, firewall-telemetry]
dependency_graph:
  requires: [23-00]
  provides: [SuricataEveParser, P23-T02]
  affects: [ingestion/loader.py, backend/api/ingest.py]
tech_stack:
  added: []
  patterns: [BaseParser, NormalizedEvent, parse_record convenience method, NDJSON streaming]
key_files:
  created:
    - ingestion/parsers/suricata_eve_parser.py
  modified:
    - tests/unit/test_suricata_eve_parser.py
decisions:
  - "SuricataEveParser uses supported_extensions=[] (programmatic use only, not extension-based registry)"
  - "Non-alert event types default severity to 'info' (matches NormalizedEvent default)"
  - "flow.state='closed' maps to event_outcome='success'; other states leave event_outcome=None"
  - "MITRE metadata values are always lists — take [0] or None pattern from RESEARCH.md"
metrics:
  duration_seconds: 113
  completed_date: "2026-04-05"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
requirements_completed: [P23-T02]
---

# Phase 23 Plan 02: SuricataEveParser Summary

SuricataEveParser — Suricata EVE JSON NDJSON parser mapping alert/flow/dns/http/tls records to NormalizedEvent with severity inversion and MITRE ATT&CK extraction.

## What Was Built

`ingestion/parsers/suricata_eve_parser.py` implements `SuricataEveParser(BaseParser)` with:

- `parse(file_path, case_id=None)` — streams NormalizedEvent objects from a Suricata EVE NDJSON file
- `parse_record(record, source_file, case_id)` — convenience method for in-memory dict conversion

Key field mappings:
- `dest_ip` (EVE) → `dst_ip` (NormalizedEvent)
- `dest_port` (EVE) → `dst_port` (NormalizedEvent)
- `proto` → `network_protocol`
- `host` → `hostname`
- Alert severity: EVE 1→"critical", 2→"high", 3→"medium", 4→"low"
- Non-alert severity: "info" (default)
- Alert action: "allowed"→"success", "blocked"→"failure" → `event_outcome`
- MITRE: `alert.metadata.mitre_attack_id[0]` → `attack_technique`; `alert.metadata.mitre_tactic_name[0]` → `attack_tactic`

EVE event_type mapping:
- alert → "detection"
- flow → "network_connect"
- dns → "dns_query"
- http → "network_connect"
- tls → "network_connect"
- Unknown → passed through as-is

Tags constructed per event type: `sid:N,category:X` for alerts; `dns_type:A` for DNS; `method:GET` for HTTP; `flow_id:N` for all.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement SuricataEveParser | c4d0a50 | ingestion/parsers/suricata_eve_parser.py (created) |
| 2 | Activate test stubs and verify full suite | b72621e | tests/unit/test_suricata_eve_parser.py (4 skips removed) |

## Verification

- `uv run pytest tests/unit/test_suricata_eve_parser.py -v` — **4 PASSED**
- `python -c "...p.parse('fixtures/suricata_eve_sample.ndjson')..."` — **5 events** parsed
- `uv run pytest -q` — **809 passed, 0 failures** (full suite)

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- `ingestion/parsers/suricata_eve_parser.py` exists
- Commits c4d0a50 and b72621e both present
- 4 tests pass, 809 total passing
