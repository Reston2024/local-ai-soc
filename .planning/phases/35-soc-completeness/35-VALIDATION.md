---
phase: 35
slug: soc-completeness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-10
---

# Phase 35 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pytest-asyncio mode: auto) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/unit/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 35-T01 | 01 | 1 | P35-T01 | unit | `uv run pytest tests/unit/test_explain.py -x` | ❌ Wave 0 | ⬜ pending |
| 35-T02 | 01 | 1 | P35-T02 | unit | `uv run pytest tests/unit/test_timeline_merge_playbooks.py -x` | ❌ Wave 0 | ⬜ pending |
| 35-T03 | 01 | 1 | P35-T03 | manual-only | — | N/A | ⬜ pending |
| 35-T04 | 01 | 1 | P35-T04 | manual-only | — | N/A | ⬜ pending |
| 35-T06 | 01 | 1 | P35-T06 | unit | `uv run pytest tests/unit/test_field_map.py -x` | ❌ Wave 0 | ⬜ pending |
| 35-T08 | 02 | 1 | P35-T08 | unit | `uv run pytest tests/unit/test_triage_store.py -x` | ❌ Wave 0 | ⬜ pending |
| 35-T09 | 02 | 2 | P35-T09 | unit | `uv run pytest tests/unit/test_triage_api.py -x` | ❌ Wave 0 | ⬜ pending |
| 35-T10 | 02 | 2 | P35-T10 | unit | `uv run pytest tests/unit/test_triage_worker.py -x` | ❌ Wave 0 | ⬜ pending |
| 35-T05 | 03 | 2 | P35-T05 | unit | `uv run pytest tests/unit/test_telemetry_summary.py -x` | ❌ Wave 0 | ⬜ pending |
| 35-T07 | 03 | 2 | P35-T07 | manual-only | — | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_explain.py` — stubs for P35-T01 (mock empty detection lookup)
- [ ] `tests/unit/test_timeline_merge_playbooks.py` — stubs for P35-T02 (merge_and_sort_timeline with playbook_rows)
- [ ] `tests/unit/test_field_map.py` — stubs for P35-T06 (dns_query, http_user_agent, tls_ja3 in SIGMA_FIELD_MAP)
- [ ] `tests/unit/test_triage_store.py` — stubs for P35-T08 (SQLite :memory: DDL + triaged_at column)
- [ ] `tests/unit/test_triage_api.py` — stubs for P35-T09 (TestClient + mock Ollama)
- [ ] `tests/unit/test_triage_worker.py` — stubs for P35-T10 (poll logic, non-fatal error handling)
- [ ] `tests/unit/test_telemetry_summary.py` — stubs for P35-T05 (mock DuckDB + SQLite, response shape)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ZEEK_CHIPS enabled (no disabled/dashed) | P35-T03 | Frontend UI change, no unit test path | Open EventsView, verify DNS/HTTP/TLS/etc. chips are clickable and active |
| BETA badges removed from 4 nav items | P35-T04 | Visual nav change | Open dashboard, verify Threat Intel/ATT&CK/Hunting/Map have no beta chip |
| End-to-end smoke test | P35-T07 | Multi-system integration | Ingest Malcolm sample → EVE chips visible → hunt returns → IOC matches → assets populate |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
