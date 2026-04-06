---
phase: 26
slug: graph-schema-versioning-and-perimeter-entities
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-06
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (auto mode) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/unit/test_graph_schema.py tests/unit/test_graph_versioning.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30 seconds (unit only), ~60 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_graph_schema.py tests/unit/test_graph_versioning.py -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green + human visual checkpoint complete
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| Schema constants extended | 01 | 1 | P26-T02 | unit | `uv run pytest tests/unit/test_graph_schema.py -x` | Wave 0 | ⬜ pending |
| Edge types added | 01 | 1 | P26-T03 | unit | same | Wave 0 | ⬜ pending |
| system_kv migration | 02 | 1 | P26-T01 | unit | `uv run pytest tests/unit/test_graph_versioning.py -x` | Wave 0 | ⬜ pending |
| GET /api/graph/schema-version | 02 | 1 | P26-T01 | unit | same | Wave 0 | ⬜ pending |
| Additive-only constraint | 02 | 1 | P26-T04 | unit | same | Wave 0 | ⬜ pending |
| IPFire syslog graph emission | 03 | 2 | P26-T03 | unit | `uv run pytest tests/unit/test_graph_schema.py -x` | Wave 0 | ⬜ pending |
| Dashboard perimeter rendering | 04 | 2 | P26-T05 | human | checkpoint | manual | ⬜ pending |
| Test activation | 05 | 3 | P26-T01-T05 | unit | `uv run pytest tests/unit/test_graph_schema.py tests/unit/test_graph_versioning.py -v` | Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_graph_schema.py` — stubs for P26-T02, P26-T03, P26-T04 (new file)
- [ ] `tests/unit/test_graph_versioning.py` — stubs for P26-T01, P26-T04 (new file)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| firewall_zone rendered with zone-color coding | P26-T05 | Requires browser rendering of Cytoscape.js | Start backend, open dashboard, ingest test graph data, verify firewall_zone shows zone-color, network_segment shows as subnet bubble, new edge styles visible |
| No visual regression on existing node types | P26-T05 | Requires visual comparison | Compare existing node/edge rendering against baseline screenshots |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
