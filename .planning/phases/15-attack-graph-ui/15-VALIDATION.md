---
phase: 15
slug: attack-graph-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (Python) + uv run pytest |
| **Config file** | pyproject.toml (pytest-asyncio mode: auto) |
| **Quick run command** | `uv run pytest tests/unit/test_graph_api.py -x -q` |
| **Full suite command** | `uv run pytest -q --tb=short && cd dashboard && npm run build` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_graph_api.py -x -q`
- **After every plan wave:** Run `uv run pytest -q --tb=short && cd dashboard && npm run build`
- **Before `/gsd:verify-work`:** Full suite must be green + npm build exits 0
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | P15-T01 | unit | `uv run pytest tests/unit/test_graph_api.py -x -q` | ❌ W0 | ⬜ pending |
| 15-02-01 | 02 | 2 | P15-T01 | unit | `uv run pytest tests/unit/test_graph_api.py -x -q` | ❌ W0 | ⬜ pending |
| 15-03-01 | 03 | 2 | P15-T02 | manual | `cd dashboard && npm run build` exits 0 | — | ⬜ pending |
| 15-03-02 | 03 | 2 | P15-T03 | manual | Browser: attack path highlights on detection click | — | ⬜ pending |
| 15-04-01 | 04 | 3 | P15-T04 | manual | Browser: node click → InvestigationView; "Open in Graph" button | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_graph_api.py` — stubs for P15-T01 (investigation graph endpoint, global graph endpoint, route precedence)

*Frontend tests (P15-T02/T03/T04) are manual-only — no Vitest configured in this project.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| fCoSE/dagre layout renders without error | P15-T02 | Cytoscape canvas rendering requires browser | Open http://localhost:5173/app/, navigate to Attack Graph, verify nodes/edges appear |
| Attack path highlighted on detection select | P15-T03 | Visual CSS animation requires browser | Click a detection → click "Open in Graph", verify red thick edges on attack path |
| Node click navigates to InvestigationView | P15-T04 | Svelte navigation requires browser | Click any node in graph, verify InvestigationView opens for that entity |
| "Open in Graph" from InvestigationView works | P15-T04 | Svelte cross-view navigation requires browser | Open InvestigationView, click "Open in Graph", verify graph centres on investigation entity |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
