---
phase: 23-firewall-telemetry-ingestion
verified_by: gsd-verifier (29-03)
verified_date: "2026-04-08"
status: human_needed
requirements: [P23-T01, P23-T02, P23-T03, P23-T04]
---

# Phase 23 Verification: Firewall Telemetry Ingestion

**Status: human_needed** — All automated checks pass. Live validation requires a physical/VM IPFire appliance and Suricata sensor (not available in CI).

## Summary

Phase 23 delivered IPFire syslog ingestion and Suricata EVE JSON parsing via a scheduled collector job, plus a `/api/firewall/status` health endpoint. All four requirements (P23-T01 through P23-T04) are satisfied by the automated test suite (18 passing tests, 0 failures).

## Automated Checks

| Check | Command / Evidence | Result |
|---|---|---|
| `IPFireSyslogParser` import | `from ingestion.parsers.ipfire_syslog_parser import IPFireSyslogParser` | PASS |
| `SuricataEveParser` import | `from ingestion.parsers.suricata_eve_parser import SuricataEveParser` | PASS |
| `FirewallCollector` import | `from ingestion.jobs.firewall_collector import FirewallCollector` | PASS |
| Phase 23 unit tests | `uv run pytest tests/ -k "ipfire or suricata or firewall" -x -q` | **18 passed, 0 failed** |
| Fixture: IPFire syslog | `fixtures/syslog/ipfire_sample.log` | EXISTS |
| Fixture: Suricata EVE JSON | `fixtures/suricata_eve_sample.ndjson` | EXISTS |
| Firewall API route | `backend/api/firewall.py` — `GET /api/firewall/status` registered | EXISTS |

*Automated checks run: 2026-04-08T17:12:49Z*

## Artifact Inventory

| Artifact | Path | Status |
|---|---|---|
| IPFire syslog parser | `ingestion/parsers/ipfire_syslog_parser.py` | PRESENT |
| Suricata EVE parser | `ingestion/parsers/suricata_eve_parser.py` | PRESENT |
| Firewall collector job | `ingestion/jobs/firewall_collector.py` | PRESENT |
| Firewall API endpoint | `backend/api/firewall.py` | PRESENT |
| Jobs package marker | `ingestion/jobs/__init__.py` | PRESENT |
| IPFire fixture log | `fixtures/syslog/ipfire_sample.log` | PRESENT |
| Suricata fixture NDJSON | `fixtures/suricata_eve_sample.ndjson` | PRESENT |

## Parser Behavior Verified

### IPFireSyslogParser (`ingestion/parsers/ipfire_syslog_parser.py`)
- Class name: `IPFireSyslogParser` (note: plan referenced `IpfireSyslogParser` — actual name uses uppercase acronym)
- 23-04 SUMMARY confirms: **6 events from 6 fixture lines**, both success and failure outcomes present
- Normalizes raw IPFire syslog lines to `NormalizedEvent`
- Links to: `ingestion/normalizer.py` via standard BaseParser interface

### SuricataEveParser (`ingestion/parsers/suricata_eve_parser.py`)
- 23-04 SUMMARY confirms: **5 events produced from fixture**, MITRE extraction working, severity inversion working (1=critical, 4=low)
- Normalizes Suricata EVE JSON to `NormalizedEvent`

### FirewallCollector (`ingestion/jobs/firewall_collector.py`)
- File-tail loop, exponential backoff, and heartbeat via `system_kv` all verified by unit tests
- Activated via `FIREWALL_ENABLED=True` environment variable (default: False)

## Known Tech Debt

**Parser registry exclusion (collector-only access):**

`IPFireSyslogParser` and `SuricataEveParser` have `supported_extensions = []` (intentionally empty). Neither parser is registered in `ingestion/registry.py` (the file-upload parser registry, which contains only `EvtxParser`, `JsonParser`, `CsvParser`).

These parsers are **only accessible via `FirewallCollector` scheduled jobs** — not via the `/api/ingest` file-upload endpoint.

- **Impact:** Users cannot upload `.log` or `.json` firewall files through the standard ingest UI and have them parsed by these parsers.
- **Workaround:** Use the FirewallCollector with `FIREWALL_ENABLED=True` for live streaming ingestion.
- **Classification:** Known design decision (collector-first pattern), not a defect. Documented as tech debt for future enhancement if ad-hoc firewall file upload is desired.

## Requirements Traceability

| Requirement | Description | Evidence | Status |
|---|---|---|---|
| P23-T01 | IPFireSyslogParser | `ipfire_syslog_parser.py` + 18 tests pass | SATISFIED |
| P23-T02 | SuricataEveParser | `suricata_eve_parser.py` + 18 tests pass | SATISFIED |
| P23-T03 | FirewallCollector scheduled ingestion | `firewall_collector.py` + unit tests | SATISFIED |
| P23-T04 | GET /api/firewall/status | `backend/api/firewall.py` | SATISFIED |

## Deferred Items (Human Validation Needed)

The following checks require live infrastructure not available in CI. This is why status is `human_needed` rather than `passed`:

1. **Live IPFire connectivity** — Requires a physical or VM IPFire appliance sending syslog to `FIREWALL_SYSLOG_PATH`. Cannot be automated in CI.
2. **Live Suricata EVE tail** — Requires a running Suricata sensor writing to `FIREWALL_EVE_PATH`. Cannot be automated in CI.
3. **Collector live file-tail behaviour** — Live writes to tail path required to validate `FirewallCollector` in production conditions.

To activate in a live environment, add to `.env`:

```
FIREWALL_ENABLED=True
FIREWALL_SYSLOG_PATH=/var/log/remote/ipfire/messages
FIREWALL_EVE_PATH=/var/log/remote/ipfire/suricata/eve.json
```

## Prior Phase Sign-off (23-04-SUMMARY.md)

The 23-04-SUMMARY.md records a prior verification checkpoint result:

- Full pytest suite at time of delivery: **817 passed, 0 failures**
- 14 Phase 23 unit tests: all passing
- Human checkpoint approved externally on 2026-04-05

Current re-run (2026-04-08): **18 Phase 23 tests, 0 failures** (4 additional tests added since original delivery).

## Conclusion

Phase 23 is **fully implemented** and all automated checks pass. The `human_needed` status reflects that live firewall hardware validation has not been performed in CI — this is expected and was documented in the original checkpoint plan (23-04). All code-level requirements are met.
