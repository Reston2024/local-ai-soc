---
phase: 36
slug: zeek-full-telemetry
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-11
---

# Phase 36 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (asyncio mode: auto) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/unit/ -q` |
| **Full suite command** | `uv run pytest tests/unit/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -q`
- **After every plan wave:** Run `uv run pytest tests/unit/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 36-01-01 | 01 | 1 | P36-T01 | manual+unit | `uv run pytest tests/unit/test_zeek_fields.py -q` | ❌ W0 | ⬜ pending |
| 36-01-02 | 01 | 1 | P36-T09 | unit | `uv run pytest tests/unit/test_zeek_fields.py -q` | ❌ W0 | ⬜ pending |
| 36-01-03 | 01 | 1 | P36-T02,T03 | unit | `uv run pytest tests/unit/test_zeek_normalizers.py -q` | ❌ W0 | ⬜ pending |
| 36-02-01 | 02 | 1 | P36-T04,T05 | unit | `uv run pytest tests/unit/test_zeek_normalizers.py -q` | ❌ W0 | ⬜ pending |
| 36-02-02 | 02 | 1 | P36-T06,T07,T08 | unit | `uv run pytest tests/unit/test_zeek_normalizers.py -q` | ❌ W0 | ⬜ pending |
| 36-03-01 | 03 | 2 | P36-T10 | unit | `uv run pytest tests/unit/ -q` | ✅ | ⬜ pending |
| 36-03-02 | 03 | 2 | P36-T11 | unit | `uv run pytest tests/unit/test_field_map.py -q` | ✅ | ⬜ pending |
| 36-03-03 | 03 | 2 | P36-T12 | manual | see Manual-Only below | N/A | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/unit/test_zeek_fields.py` — stubs for NormalizedEvent field expansion + DuckDB migration
- [ ] `tests/unit/test_zeek_normalizers.py` — stubs for all Zeek normalizer methods

*Existing infrastructure (conftest, pytest-asyncio auto mode) covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Zeek log types appear in DuckDB | P36-T12 | Requires live Malcolm + ingest cycle | Query DuckDB: `SELECT event_type, count(*) FROM events WHERE event_type IN ('conn','weird','http','ssl','x509','file_transfer','notice','kerberos_tgs_request','ntlm_auth','ssh_auth','smb_mapping','smb_files','rdp','dhcp','dns_query') GROUP BY event_type` |
| SPAN delivering packets | P36-T01 | Requires live OpenSearch | Run: `curl -sk -u malcolm_internal:... "https://192.168.1.22:9200/arkime_sessions3-*/_count?q=event.dataset:zeek*"` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
