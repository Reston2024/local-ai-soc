---
phase: 6
slug: hardening-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + fastapi.testclient (existing, auto mode) |
| **Config file** | pyproject.toml (pytest-asyncio mode: auto) |
| **Quick run command** | `uv run pytest backend/src/tests/test_phase6.py -v` |
| **Full suite command** | `uv run pytest backend/src/tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest backend/src/tests/test_phase6.py -v`
- **After every plan wave:** Run `uv run pytest backend/src/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green + `cd dashboard && npm run build` exits 0
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-00-stubs | 00 | 0 | xfail stubs | unit | `pytest test_phase6.py -v` | ❌ W0 | ⬜ pending |
| 06-01-entity | 01 | 1 | entity resolution | unit | `pytest test_phase6.py::TestEntityResolver` | ❌ W0 | ⬜ pending |
| 06-01-casef | 01 | 1 | case folding | unit | `pytest test_phase6.py::TestEntityResolverCaseFolding` | ❌ W0 | ⬜ pending |
| 06-02-chain | 02 | 1 | causal chain | unit | `pytest test_phase6.py::TestAttackChainBuilder` | ❌ W0 | ⬜ pending |
| 06-02-depth | 02 | 1 | depth cap BFS | unit | `pytest test_phase6.py::TestAttackChainDepthCap` | ❌ W0 | ⬜ pending |
| 06-02-cycle | 02 | 1 | cycle detection | unit | `pytest test_phase6.py::TestAttackChainCycleDetection` | ❌ W0 | ⬜ pending |
| 06-03-mitre | 03 | 2 | MITRE mapper | unit | `pytest test_phase6.py::TestMitreMapper` | ❌ W0 | ⬜ pending |
| 06-03-grace | 03 | 2 | graceful unknown | unit | `pytest test_phase6.py::TestMitreMapperGraceful` | ❌ W0 | ⬜ pending |
| 06-03-score | 03 | 2 | scoring 0-100 | unit | `pytest test_phase6.py::TestScoring` | ❌ W0 | ⬜ pending |
| 06-04-eng | 04 | 2 | engine integration | unit | `pytest test_phase6.py::TestCausalityEngine` | ❌ W0 | ⬜ pending |
| 06-05-api1 | 05 | 3 | GET /graph/{id} | integration | `pytest test_phase6.py::TestGraphEndpoint` | ❌ W0 | ⬜ pending |
| 06-05-api2 | 05 | 3 | GET /entity/{id} | integration | `pytest test_phase6.py::TestEntityEndpoint` | ❌ W0 | ⬜ pending |
| 06-05-api3 | 05 | 3 | GET /attack_chain | integration | `pytest test_phase6.py::TestAttackChainEndpoint` | ❌ W0 | ⬜ pending |
| 06-05-api4 | 05 | 3 | POST /query | integration | `pytest test_phase6.py::TestQueryEndpoint` | ❌ W0 | ⬜ pending |
| 06-06-ui | 06 | 4 | npm build | build | `cd dashboard && npm run build` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/src/tests/test_phase6.py` — 14 xfail stubs covering all test classes
- [ ] `backend/causality/__init__.py` — empty package stub
- [ ] `backend/causality/engine.py` — stub: `def build_causality_sync(*args): return {}`
- [ ] `backend/causality/entity_resolver.py` — stub: `def resolve_canonical_id(*args): return None`
- [ ] `backend/causality/attack_chain_builder.py` — stub: `def find_causal_chain(*args): return []`
- [ ] `backend/causality/mitre_mapper.py` — stub: `def map_techniques(*args): return []`
- [ ] `backend/causality/scoring.py` — stub: `def score_chain(*args): return 0`

*Existing pytest infrastructure (pyproject.toml, conftest patterns) carries over from Phases 4/5.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Attack graph renders in browser | Dashboard UI | DOM interaction requires browser | Open dashboard, navigate to Alert view, confirm graph renders with nodes/edges |
| Node expansion click works | Dashboard UI | Interactive event | Click a node in the attack graph, confirm expansion panel appears |
| Attack path highlight visible | Dashboard UI | Visual distinction | Verify highlighted path is visually distinct from non-path edges |
| Timeline filter narrows events | Dashboard UI | Visual/interactive | Apply time range filter, confirm graph updates |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING (❌ W0) references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
