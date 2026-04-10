---
phase: 33
slug: real-threat-intelligence
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (auto mode set in pyproject.toml) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/unit/test_intel_feeds.py tests/unit/test_ioc_store.py -x` |
| **Full suite command** | `uv run pytest tests/unit/ -x` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/unit/ -x`
- **Before `/gsd:verify-work`:** Full unit suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| P33-T01-feodo-parse | 01 | 0 | P33-T01 | unit | `uv run pytest tests/unit/test_intel_feeds.py::test_feodo_csv_parse -x` | Wave 0 | ⬜ pending |
| P33-T01-feodo-sync | 01 | 0 | P33-T01 | unit | `uv run pytest tests/unit/test_intel_feeds.py::test_feodo_sync_success -x` | Wave 0 | ⬜ pending |
| P33-T02-cisa-parse | 01 | 0 | P33-T02 | unit | `uv run pytest tests/unit/test_intel_feeds.py::test_cisa_kev_parse -x` | Wave 0 | ⬜ pending |
| P33-T03-threatfox-parse | 01 | 0 | P33-T03 | unit | `uv run pytest tests/unit/test_intel_feeds.py::test_threatfox_csv_parse -x` | Wave 0 | ⬜ pending |
| P33-T04-upsert-new | 01 | 0 | P33-T04 | unit | `uv run pytest tests/unit/test_ioc_store.py::test_upsert_ioc_new -x` | Wave 0 | ⬜ pending |
| P33-T04-match-hit | 01 | 0 | P33-T04 | unit | `uv run pytest tests/unit/test_ioc_store.py::test_check_ioc_match_hit -x` | Wave 0 | ⬜ pending |
| P33-T04-match-miss | 01 | 0 | P33-T04 | unit | `uv run pytest tests/unit/test_ioc_store.py::test_check_ioc_match_miss -x` | Wave 0 | ⬜ pending |
| P33-T05-duckdb-cols | 01 | 0 | P33-T05 | unit | `uv run pytest tests/unit/test_duckdb_migration.py -x -k ioc` | Wave 0 extend | ⬜ pending |
| P33-T06-ingest-match | 02 | 0 | P33-T06 | unit | `uv run pytest tests/unit/test_ioc_matching.py::test_at_ingest_match -x` | Wave 0 | ⬜ pending |
| P33-T06-ingest-miss | 02 | 0 | P33-T06 | unit | `uv run pytest tests/unit/test_ioc_matching.py::test_at_ingest_no_match -x` | Wave 0 | ⬜ pending |
| P33-T07-retroactive | 02 | 0 | P33-T07 | unit | `uv run pytest tests/unit/test_ioc_matching.py::test_retroactive_scan -x` | Wave 0 | ⬜ pending |
| P33-T08-decay | 01 | 0 | P33-T08 | unit | `uv run pytest tests/unit/test_ioc_store.py::test_confidence_decay -x` | Wave 0 | ⬜ pending |
| P33-T09-hits-endpoint | 03 | 0 | P33-T09 | unit | `uv run pytest tests/unit/test_api_intel.py::test_ioc_hits_endpoint -x` | Wave 0 | ⬜ pending |
| P33-T09-feeds-endpoint | 03 | 0 | P33-T09 | unit | `uv run pytest tests/unit/test_api_intel.py::test_feeds_endpoint -x` | Wave 0 | ⬜ pending |
| P33-T14-event-fields | 02 | 0 | P33-T14 | unit | `uv run pytest tests/unit/test_ioc_matching.py::test_normalized_event_fields -x` | Wave 0 | ⬜ pending |
| P33-T16-auth | 03 | 0 | P33-T16 | unit | `uv run pytest tests/unit/test_api_intel.py::test_intel_requires_auth -x` | Wave 0 | ⬜ pending |
| P33-T10-ui-empty | 03 | 1 | P33-T10 | manual | open /app → ThreatIntelView in browser | N/A | ⬜ pending |
| P33-T10-ui-sort | 03 | 1 | P33-T10 | manual | verify hit list sorts by risk_score desc | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_intel_feeds.py` — stubs for P33-T01, P33-T02, P33-T03 (mock httpx with `unittest.mock.patch`)
- [ ] `tests/unit/test_ioc_store.py` — stubs for P33-T04, P33-T08 (in-memory `:memory:` SQLite)
- [ ] `tests/unit/test_ioc_matching.py` — stubs for P33-T06, P33-T07, P33-T14 (seed ioc_store, run loader)
- [ ] `tests/unit/test_api_intel.py` — stubs for P33-T09, P33-T16 (FastAPI TestClient + mock SQLite)
- [ ] `tests/unit/test_duckdb_migration.py` — extend with ioc column test cases for P33-T05

**Mock strategy:** Use `unittest.mock.patch` on `httpx.get` / `httpx.AsyncClient.get` to return fixture CSV/JSON strings. No real network calls in unit tests.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ThreatIntelView renders feed health strip + empty state | P33-T10 | Svelte UI — no browser test framework in scope | Open /app, navigate to Threat Intel, verify feed strip shows 3 feeds with sync status, verify "No IOC matches yet" empty state |
| ThreatIntelView hit list sorts by risk_score desc | P33-T10 | Requires live data in ioc_store | Wait for feed sync, verify highest risk events appear first |
| Inline row expansion shows IOC detail | P33-T10 | Interactive UI behavior | Click a hit row, verify expanded card shows feed source, actor_tag, malware_family, confidence |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
