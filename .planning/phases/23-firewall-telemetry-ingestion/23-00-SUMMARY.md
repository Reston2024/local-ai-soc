---
phase: 23-firewall-telemetry-ingestion
plan: "00"
subsystem: ingestion/testing
tags: [tdd-scaffolding, firewall, syslog, suricata, collector, wave-0]
dependency_graph:
  requires: []
  provides:
    - ingestion.jobs Python package (importable)
    - fixtures/syslog/ipfire_sample.log (6 representative syslog lines)
    - tests/unit/test_ipfire_syslog_parser.py (P23-T01 stubs)
    - tests/unit/test_suricata_eve_parser.py (P23-T02 stubs)
    - tests/unit/test_firewall_collector.py (P23-T03 + P23-T04 stubs)
  affects:
    - Wave 1 plans (23-01, 23-02) — test stubs activate when parsers are implemented
    - Wave 2 plan (23-03) — collector stubs activate when FirewallCollector is implemented
tech_stack:
  added: []
  patterns:
    - pytest.mark.skipif with ImportError guard for pre-skipped stubs
    - pytestmark module-level skip with per-method explicit skip for double protection
key_files:
  created:
    - ingestion/jobs/__init__.py
    - fixtures/syslog/ipfire_sample.log
    - tests/unit/test_ipfire_syslog_parser.py
    - tests/unit/test_suricata_eve_parser.py
    - tests/unit/test_firewall_collector.py
  modified: []
decisions:
  - "Used pytestmark.skipif(not _IMPORT_OK) + per-test @pytest.mark.skip for double protection: collection skips if module missing, individual test skips if module present but not yet complete"
  - "fixtures/syslog/ directory created as subdirectory of fixtures/ to match existing ndjson/ and evtx/ pattern"
metrics:
  duration_minutes: 2
  completed_date: "2026-04-05"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 0
---

# Phase 23 Plan 00: Wave 0 Scaffolding — TDD Stubs and Package Init Summary

**One-liner:** Pre-skipped TDD stubs for IPFire syslog, Suricata EVE, and FirewallCollector with import-guarded pytestmark and a 6-line IPFire fixture covering TCP/UDP/ICMP variants.

## What Was Built

Wave 0 scaffold for Phase 23 firewall telemetry ingestion. Established TDD RED foundation before any parser or collector implementation exists.

**ingestion/jobs/__init__.py** — New Python package enabling `from ingestion.jobs.firewall_collector import FirewallCollector` once Wave 2 creates the module.

**fixtures/syslog/ipfire_sample.log** — 6 IPFire kernel syslog lines:
1. FORWARDFW TCP (SYN, green0→red0, port 443) — ALLOW path
2. DROP_CTINVALID TCP (blue0, CT-invalid drop) — DROP path
3. REJECT_INPUT TCP (red0, SSH port 22) — REJECT path
4. INPUTFW ICMP (green0, no ports) — ICMP allow
5. DROP_INPUT ICMP (red0, no ports) — ICMP drop
6. FORWARDFW UDP (orange0→red0, DNS port 53) — UDP path

**tests/unit/test_ipfire_syslog_parser.py** — 4 classes, 5 methods for P23-T01:
- `TestIPFireParserForwardFW`: FORWARDFW fields (src_ip, dst_ip, dst_port, protocol, outcome)
- `TestIPFireParserDropReject`: DROP/REJECT outcome mapping and raw_event preservation
- `TestIPFireParserICMP`: ICMP without SPT/DPT (null port handling)
- `TestIPFireParserSingleLine`: parse_line() convenience method

**tests/unit/test_suricata_eve_parser.py** — 4 classes, 4 methods for P23-T02:
- `TestSuricataSeverityMapping`: alert.severity integer → string enum mapping
- `TestSuricataMITREExtraction`: MITRE ATT&CK tactic/technique from alert.metadata
- `TestSuricataDnsHttpFlow`: dns/http/flow event type parsing
- `TestSuricataDestIpMapping`: dest_ip → dst_ip field mapping

**tests/unit/test_firewall_collector.py** — 5 classes, 5 methods for P23-T03 + P23-T04:
- `TestFirewallCollectorIngestsLines`: tail-reads new syslog lines and calls loader
- `TestFirewallCollectorMissingFile`: absent files do not crash
- `TestFirewallCollectorBackoff`: exponential backoff (interval * 2^failures, capped 300s)
- `TestHeartbeatNormalisation`: heartbeat event stored in system_kv and ingested
- `TestFirewallStatusEndpoint`: /api/firewall/status route registered

## Verification Results

- `uv run pytest tests/unit/test_ipfire_syslog_parser.py tests/unit/test_suricata_eve_parser.py tests/unit/test_firewall_collector.py -v`: 14 skipped, 0 failures
- `uv run pytest -q` (full suite): 803 passed, 16 skipped, 0 failures
- `uv run python -c "import ingestion.jobs; print('jobs package OK')"`: jobs package OK
- `fixtures/syslog/ipfire_sample.log` has 6 lines

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 867da9d | chore(23-00): create ingestion/jobs package and IPFire syslog fixture |
| Task 2 | a6e1761 | test(23-00): add pre-skipped test stubs for Phase 23 parsers and collector |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- ingestion/jobs/__init__.py: FOUND
- fixtures/syslog/ipfire_sample.log: FOUND (6 lines)
- tests/unit/test_ipfire_syslog_parser.py: FOUND
- tests/unit/test_suricata_eve_parser.py: FOUND
- tests/unit/test_firewall_collector.py: FOUND
- Commit 867da9d: FOUND
- Commit a6e1761: FOUND
