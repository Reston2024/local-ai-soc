---
phase: 23-firewall-telemetry-ingestion
plan: "01"
subsystem: ingestion/parsers
tags: [firewall, syslog, ipfire, parser, tdd, network]
dependency_graph:
  requires: [23-00]
  provides: [IPFireSyslogParser, ipfire_syslog events]
  affects: [ingestion/loader.py, detections/matcher.py]
tech_stack:
  added: []
  patterns: [RFC-3164-syslog-parsing, kv-extraction, year-inference]
key_files:
  created:
    - ingestion/parsers/ipfire_syslog_parser.py
  modified:
    - tests/unit/test_ipfire_syslog_parser.py
decisions:
  - "IPFireSyslogParser.supported_extensions=[] (programmatic use, not extension-based) — matches OsqueryParser pattern"
  - "Year inference: subtract 1 year if parsed date >30 days in future — handles Dec->Jan log rollover without storing state"
  - "Severity 'medium' for DROP_*/REJECT_* (security-relevant drops) vs 'info' for FORWARDFW/INPUTFW (normal permit traffic)"
  - "tags field encodes both in:/out: interface names and zone: labels (e.g. 'in:green0,out:red0,zone:green,zone:red') for downstream filtering"
metrics:
  duration_seconds: 140
  completed_date: "2026-04-05"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
requirements_satisfied: [P23-T01]
---

# Phase 23 Plan 01: IPFireSyslogParser Implementation Summary

IPFireSyslogParser(BaseParser) parsing RFC 3164 iptables syslog lines into NormalizedEvent with network telemetry fields, outcome mapping, and zone tagging.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement IPFireSyslogParser | f483a4b | ingestion/parsers/ipfire_syslog_parser.py (created) |
| 2 | Activate test stubs and verify full suite | f4980e6 | tests/unit/test_ipfire_syslog_parser.py (5 skips removed) |

## What Was Built

`ingestion/parsers/ipfire_syslog_parser.py` implements `IPFireSyslogParser(BaseParser)` with:

- `parse(file_path, case_id) -> Iterator[NormalizedEvent]` — streams events from a syslog file
- `parse_line(raw_line, source_file, case_id) -> NormalizedEvent | None` — single-line convenience method

Key implementation details:
- `_RFC3164_RE` regex parses syslog header to extract month/day/time/host/body
- `_KV_RE` extracts all `KEY=VALUE` pairs from the iptables body
- `_PREFIX_RE` extracts the log prefix (FORWARDFW, DROP_CTINVALID, REJECT_INPUT, etc.)
- `_parse_timestamp()` infers year with 30-day future guard for Dec->Jan rollover
- FORWARDFW/INPUTFW -> `event_outcome="success"`, severity `"info"`
- DROP_*/REJECT_* -> `event_outcome="failure"`, severity `"medium"`
- ICMP lines: `src_port=None`, `dst_port=None` (no SPT/DPT keys present)
- `tags` encodes `in:<iface>`, `out:<iface>`, and `zone:<zone>` for IN/OUT interfaces

## Verification Results

- `uv run pytest tests/unit/test_ipfire_syslog_parser.py -v` — **5 PASSED**
- Parser produces **6 events** from `fixtures/syslog/ipfire_sample.log`
- Full suite: **812 passed, 0 failures**

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- ingestion/parsers/ipfire_syslog_parser.py: FOUND
- tests/unit/test_ipfire_syslog_parser.py: FOUND (5 skip decorators removed)
- Commit f483a4b: FOUND
- Commit f4980e6: FOUND
- 5 tests passing: CONFIRMED
- 6 events from fixture: CONFIRMED
- Full suite 0 failures: CONFIRMED
