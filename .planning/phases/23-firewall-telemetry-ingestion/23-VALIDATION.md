---
phase: 23
slug: firewall-telemetry-ingestion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-03
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (auto mode) |
| **Config file** | `pyproject.toml` (pytest-asyncio mode = auto) |
| **Quick run command** | `uv run pytest tests/unit/test_ipfire_syslog_parser.py tests/unit/test_suricata_eve_parser.py tests/unit/test_firewall_collector.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30 seconds (unit only), ~90 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_ipfire_syslog_parser.py tests/unit/test_suricata_eve_parser.py tests/unit/test_firewall_collector.py -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| IPFire NormalizedEvent output | 01 | 1 | P23-T01 | unit | `uv run pytest tests/unit/test_ipfire_syslog_parser.py -x` | Wave 0 | ⬜ pending |
| IPFire field mapping | 01 | 1 | P23-T01 | unit | same | Wave 0 | ⬜ pending |
| IPFire DROP/REJECT variants | 01 | 1 | P23-T01 | unit | same | Wave 0 | ⬜ pending |
| IPFire raw_event preservation | 01 | 1 | P23-T01 | unit | same | Wave 0 | ⬜ pending |
| IPFire ICMP (no SPT/DPT) | 01 | 1 | P23-T01 | unit | same | Wave 0 | ⬜ pending |
| Suricata severity mapping | 02 | 1 | P23-T02 | unit | `uv run pytest tests/unit/test_suricata_eve_parser.py -x` | Wave 0 | ⬜ pending |
| Suricata MITRE extraction | 02 | 1 | P23-T02 | unit | same | Wave 0 | ⬜ pending |
| Suricata dns/flow/http events | 02 | 1 | P23-T02 | unit | same | Wave 0 | ⬜ pending |
| Suricata dest_ip → dst_ip | 02 | 1 | P23-T02 | unit | same | Wave 0 | ⬜ pending |
| Collector ingests new lines | 03 | 2 | P23-T03 | unit (async, mock) | `uv run pytest tests/unit/test_firewall_collector.py -x` | Wave 0 | ⬜ pending |
| Collector absent file skip | 03 | 2 | P23-T03 | unit (async, mock) | same | Wave 0 | ⬜ pending |
| Collector exponential backoff | 03 | 2 | P23-T03 | unit (async, mock) | same | Wave 0 | ⬜ pending |
| Heartbeat event_type field | 03 | 2 | P23-T04 | unit | same | Wave 0 | ⬜ pending |
| Status endpoint connected/degraded/offline | 04 | 2 | P23-T04 | unit | same | Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_ipfire_syslog_parser.py` — stubs for P23-T01 (new file)
- [ ] `tests/unit/test_suricata_eve_parser.py` — stubs for P23-T02 (new file)
- [ ] `tests/unit/test_firewall_collector.py` — stubs for P23-T03 + P23-T04 (new file)
- [ ] `ingestion/jobs/__init__.py` — package init (new directory)
- [ ] `fixtures/syslog/ipfire_sample.log` — syslog fixture lines (directory exists, is empty)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Firewall connectivity with real IPFire device | P23-T03 | Requires live firewall; not available in CI | Run `GET /api/firewall/status` with real device connected; verify connected state returned |
| UDP syslog delivery (if deployed with rsyslog) | P23-T03 | Transport-layer; environment-specific | Verify syslog lines appear in configured log file within 30s of firewall event |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
