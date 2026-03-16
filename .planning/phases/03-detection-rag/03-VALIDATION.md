---
phase: 3
slug: detection-rag
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (via uv) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest backend/src/tests/ -x -q` |
| **Full suite command** | `uv run pytest backend/src/tests/ -v` |
| **Estimated runtime** | ~1–2 seconds (TestClient, no I/O) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest backend/src/tests/ -x -q`
- **After every plan wave:** Run `uv run pytest backend/src/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green (32 + new tests)
- **Max feedback latency:** ~3 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | OpenSearch sink unconditional | unit | `uv run pytest backend/src/tests/test_phase3.py::TestOpenSearch -x -q` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | docker-compose OPENSEARCH_URL | manual | `docker compose config` | ✅ | ⬜ pending |
| 3-01-03 | 01 | 1 | GET /search?q= endpoint | unit | `uv run pytest backend/src/tests/test_phase3.py::TestSearchRoute -x -q` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 2 | sigma_loader loads YAML | unit | `uv run pytest backend/src/tests/test_phase3.py::TestSigmaLoader -x -q` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 2 | suspicious_dns.yml fires alert | unit | `uv run pytest backend/src/tests/test_phase3.py::TestSigmaDetection -x -q` | ❌ W0 | ⬜ pending |
| 3-02-03 | 02 | 2 | Sigma alerts appear in /alerts | unit | `uv run pytest backend/src/tests/test_phase3.py::TestSigmaAlerts -x -q` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 3 | All 32 regression tests pass | regression | `uv run pytest backend/src/tests/ -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/src/tests/test_phase3.py` — stubs for OpenSearch, search endpoint, sigma loader, sigma detection, sigma alerts

*Existing pytest infrastructure from Phase 2 covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Vector → OpenSearch sink | docker-compose stack | Requires live Docker stack | `docker compose up -d --build && curl -s http://localhost:9200/soc-events/_count` |
| OpenSearch index created on first ingest | Live integration | Requires running stack | `curl -X POST http://localhost:8000/ingest -d '...' && curl http://localhost:9200/soc-events/_count` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 3s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
