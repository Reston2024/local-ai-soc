---
phase: 11
slug: cleanup-coverage
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/unit/ tests/security/ -q` |
| **Full suite command** | `uv run pytest tests/unit/ tests/security/ --cov=backend --cov=ingestion --cov=detections --cov-fail-under=70 -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ tests/security/ -q`
- **After every plan wave:** Run `uv run pytest tests/unit/ tests/security/ --cov=backend --cov=ingestion --cov=detections --cov-fail-under=70 -q`
- **Before `/gsd:verify-work`:** Full suite must be green with ≥70% coverage
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 0 | P11-T03 | stub | `uv run pytest tests/unit/test_matcher.py --collect-only -q` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 0 | P11-T03 | stub | `uv run pytest tests/unit/test_duckdb_store.py --collect-only -q` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 0 | P11-T03 | stub | `uv run pytest tests/unit/test_csv_parser.py --collect-only -q` | ❌ W0 | ⬜ pending |
| 11-01-04 | 01 | 0 | P11-T03 | stub | `uv run pytest tests/unit/test_loader.py --collect-only -q` | ❌ W0 | ⬜ pending |
| 11-01-05 | 01 | 0 | P11-T03 | stub | `uv run pytest tests/unit/test_timeline_builder.py --collect-only -q` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 1 | P11-T01 | smoke | `uv run python -c "from backend.causality.engine import build_alert_chain; print('OK')"` | N/A | ⬜ pending |
| 11-02-02 | 02 | 1 | P11-T01 | smoke | `uv run pytest tests/unit/ tests/security/ --collect-only -q` | N/A | ⬜ pending |
| 11-02-03 | 02 | 1 | P11-T02 | shell | `grep "sha256:" docker-compose.yml` | ✅ | ⬜ pending |
| 11-03-01 | 03 | 2 | P11-T03 | unit | `uv run pytest tests/unit/test_matcher.py -x -q` | ❌ W0 | ⬜ pending |
| 11-03-02 | 03 | 2 | P11-T03 | unit | `uv run pytest tests/unit/test_duckdb_store.py -x -q` | ❌ W0 | ⬜ pending |
| 11-03-03 | 03 | 2 | P11-T03 | unit | `uv run pytest tests/unit/test_csv_parser.py -x -q` | ❌ W0 | ⬜ pending |
| 11-03-04 | 03 | 2 | P11-T03 | unit | `uv run pytest tests/unit/test_loader.py -x -q` | ❌ W0 | ⬜ pending |
| 11-03-05 | 03 | 2 | P11-T03 | unit | `uv run pytest tests/unit/test_timeline_builder.py -x -q` | ❌ W0 | ⬜ pending |
| 11-03-06 | 03 | 2 | P11-T03 | suite | `uv run pytest tests/unit/ tests/security/ --cov=backend --cov=ingestion --cov=detections --cov-fail-under=70 -q` | ✅ | ⬜ pending |
| 11-04-01 | 04 | 3 | P11-T04 | shell | `grep -c "backend/src" docs/manifest.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_matcher.py` — stubs for P11-T03 (detections/matcher.py, currently 5% coverage)
- [ ] `tests/unit/test_duckdb_store.py` — stubs for P11-T03 (backend/stores/duckdb_store.py, currently 28%)
- [ ] `tests/unit/test_csv_parser.py` — stubs for P11-T03 (ingestion/parsers/csv_parser.py, currently 33%)
- [ ] `tests/unit/test_loader.py` — stubs for P11-T03 (ingestion/loader.py, currently 22%)
- [ ] `tests/unit/test_timeline_builder.py` — stubs for P11-T03 (backend/investigation/timeline_builder.py, currently 16%)
- [ ] Register `unit` marker in `pyproject.toml` to eliminate PytestUnknownMarkWarning

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Caddy digest pin | P11-T02 | Requires Docker Desktop running | Run `docker inspect caddy:2.9-alpine --format '{{index .RepoDigests 0}}'`; confirm digest string matches docker-compose.yml |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
