---
phase: 8
slug: 8
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.5 + pytest-asyncio 0.25.0 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/unit/ -q --tb=short` |
| **Full suite command** | `uv run pytest -q --tb=short` |
| **Estimated runtime** | ~15 seconds (unit), ~45 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -q --tb=short`
- **After every plan wave:** Run `uv run pytest -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green (0 failed — baseline 4 failures must be fixed in Wave 0)
- **Max feedback latency:** 15 seconds (unit), 45 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| P8-T01 | 01 | 0 | Fix integration tests | integration | `uv run pytest tests/integration/test_backend_health.py -x` | Fix existing | ⬜ pending |
| P8-T02 | 01 | 0 | OsqueryCollector unit stubs | unit | `uv run pytest tests/unit/test_osquery_collector.py -x` | ❌ W0 create | ⬜ pending |
| P8-T03 | 01 | 0 | Pipeline integration stubs | integration | `uv run pytest tests/integration/test_osquery_pipeline.py -x` | ❌ W0 create | ⬜ pending |
| P8-T04 | 02 | 1 | Collector reads + parses lines | unit | `uv run pytest tests/unit/test_osquery_collector.py::test_reads_lines -x` | ✅ W0 | ⬜ pending |
| P8-T05 | 02 | 1 | Collector skips missing file | unit | `uv run pytest tests/unit/test_osquery_collector.py::test_missing_log_graceful -x` | ✅ W0 | ⬜ pending |
| P8-T06 | 02 | 1 | Collector uses write queue | unit | `uv run pytest tests/unit/test_osquery_collector.py::test_uses_write_queue -x` | ✅ W0 | ⬜ pending |
| P8-T07 | 02 | 1 | OSQUERY_ENABLED=False → not started | unit | `uv run pytest tests/unit/test_osquery_collector.py::test_disabled_no_start -x` | ✅ W0 | ⬜ pending |
| P8-T08 | 02 | 1 | Full osquery pipeline round-trip | integration | `uv run pytest tests/integration/test_osquery_pipeline.py -x` | ✅ W0 | ⬜ pending |
| P8-T09 | 03 | 2 | Telemetry status API 200 | integration | `uv run pytest tests/integration/test_backend_health.py::TestTelemetryAPI -x` | ✅ W0 | ⬜ pending |
| P8-T10 | 04 | 3 | Smoke test: HTTPS health 200 | smoke | `pwsh -File scripts/smoke-test-phase8.ps1` | ❌ W0 create | ⬜ pending |
| P8-T11 | 04 | 3 | Smoke test: Ollama GPU layers > 0 | smoke | `pwsh -File scripts/smoke-test-phase8.ps1` | ❌ W0 create | ⬜ pending |
| P8-T12 | ALL | gate | Regression: Phases 1–7 still pass | regression | `uv run pytest -q --tb=short` | Existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Fix `tests/integration/test_backend_health.py` — pagination field assertions (`offset`/`limit` → `page`/`page_size`)
- [ ] Create `tests/unit/test_osquery_collector.py` — xfail stubs for P8-T01 through P8-T04
- [ ] Create `tests/integration/test_osquery_pipeline.py` — xfail stub for P8-T08
- [ ] Create `ingestion/osquery_collector.py` — empty stub (import guard only)
- [ ] Create `scripts/smoke-test-phase8.ps1` — stub with TODO markers

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| osquery daemon collecting live on Windows | Live collection | Requires osquery installed + running as service | `winget install osquery.osquery` → start daemon → verify log file grows → check DuckDB row count |
| RTX 5080 GPU utilization during inference | GPU acceleration | Requires physical GPU + nvidia-smi | `ollama run qwen3:14b "test"` while `nvidia-smi` shows GPU util > 0 |
| Dashboard accessible at https://localhost/app/ | HTTPS UI | Browser required | Open Chrome → https://localhost/app/ → verify 5-tab nav loads |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
