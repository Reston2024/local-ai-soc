---
phase: 9
slug: intelligence-analyst-augmentation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via uv run pytest) |
| **Config file** | pyproject.toml (pytest-asyncio mode=auto) |
| **Quick run command** | `uv run pytest tests/unit/ -x -q` |
| **Full suite command** | `uv run pytest -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -x -q`
- **After every plan wave:** Run `uv run pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green + `cd dashboard && npm run build` exits 0
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 9-00-01 | 00 | 0 | P9-T01 | unit | `uv run pytest tests/unit/test_risk_scorer.py -x` | ❌ W0 | ⬜ pending |
| 9-00-02 | 00 | 0 | P9-T02 | unit | `uv run pytest tests/unit/test_risk_scorer.py::TestMitreWeights -x` | ❌ W0 | ⬜ pending |
| 9-00-03 | 00 | 0 | P9-T03 | unit | `uv run pytest tests/unit/test_anomaly_rules.py -x` | ❌ W0 | ⬜ pending |
| 9-00-04 | 00 | 0 | P9-T04 | unit | `uv run pytest tests/unit/test_score_api.py -x` | ❌ W0 | ⬜ pending |
| 9-00-05 | 00 | 0 | P9-T05 | unit | `uv run pytest tests/unit/test_explain_api.py -x` | ❌ W0 | ⬜ pending |
| 9-00-06 | 00 | 0 | P9-T06 | unit | `uv run pytest tests/unit/test_top_threats_api.py -x` | ❌ W0 | ⬜ pending |
| 9-00-07 | 00 | 0 | P9-T07 | unit | `uv run pytest tests/unit/test_explain_engine.py -x` | ❌ W0 | ⬜ pending |
| 9-00-08 | 00 | 0 | P9-T08 | unit | `uv run pytest tests/unit/test_risk_scorer.py::TestNodeData -x` | ❌ W0 | ⬜ pending |
| 9-00-09 | 00 | 0 | P9-T10 | unit | `uv run pytest tests/unit/test_sqlite_store.py::TestSavedInvestigations -x` | ❌ W0 | ⬜ pending |
| 9-01-xx | 01 | 1 | P9-T01,T02,T03,T08 | unit | `uv run pytest tests/unit/test_risk_scorer.py tests/unit/test_anomaly_rules.py -x` | ❌ W0 | ⬜ pending |
| 9-02-xx | 02 | 1 | P9-T04,T06 | unit | `uv run pytest tests/unit/test_score_api.py tests/unit/test_top_threats_api.py -x` | ❌ W0 | ⬜ pending |
| 9-03-xx | 03 | 2 | P9-T05,T07 | unit | `uv run pytest tests/unit/test_explain_api.py tests/unit/test_explain_engine.py -x` | ❌ W0 | ⬜ pending |
| 9-04-xx | 04 | 2 | P9-T09 | build | `cd dashboard && npm run build` | ✅ | ⬜ pending |
| 9-05-xx | 05 | 3 | P9-T10 | unit | `uv run pytest tests/unit/test_sqlite_store.py::TestSavedInvestigations -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_risk_scorer.py` — stubs for P9-T01, P9-T02, P9-T08
- [ ] `tests/unit/test_anomaly_rules.py` — stubs for P9-T03
- [ ] `tests/unit/test_explain_engine.py` — stubs for P9-T07 (mock OllamaClient)
- [ ] `tests/unit/test_score_api.py` — stubs for P9-T04 (FastAPI TestClient)
- [ ] `tests/unit/test_explain_api.py` — stubs for P9-T05 (FastAPI TestClient, mock Ollama)
- [ ] `tests/unit/test_top_threats_api.py` — stubs for P9-T06
- [ ] `tests/unit/test_sqlite_store.py` — extend with `TestSavedInvestigations` class for P9-T10

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard risk score badges visible on Cytoscape nodes | P9-T09 (dashboard) | Visual/UI — no headless test | Load APT scenario in browser, call /api/score, verify nodes show colored badges |
| AI explanation panel shows grounded text | P9-T05 | Requires live Ollama + real qwen3:14b model | POST /api/explain with apt_scenario detection_id, verify response references actual entities |
| Highest-risk node auto-identified as svchosts.exe or 185.220.101.45 | P9-T10 | Integration with live stores | Ingest apt_scenario.ndjson, run /api/detect/run, call /api/top-threats, check top entity |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
