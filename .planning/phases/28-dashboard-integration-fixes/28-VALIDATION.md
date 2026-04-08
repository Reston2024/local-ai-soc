---
phase: 28
slug: dashboard-integration-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-08
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python) + svelte-check (TypeScript) |
| **Config file** | `pyproject.toml` (pytest-asyncio auto mode) |
| **Quick run command** | `uv run pytest tests/unit/ -q --tb=short` |
| **Full suite command** | `uv run pytest --tb=short -q && cd dashboard && npx svelte-check --output machine` |
| **Estimated runtime** | ~30s (unit), ~60s (full + svelte-check) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -q --tb=short`
- **After every plan wave:** Run full suite + `npx svelte-check`
- **Before `/gsd:verify-work`:** Full suite must be green, svelte-check 0 errors
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 28-01-T1 | 01 | 1 | P28-T01 | unit+type | `uv run pytest tests/unit/ -k "query" -q && cd dashboard && npx svelte-check` | ⬜ pending |
| 28-01-T2 | 01 | 1 | P28-T02 | unit+type | `uv run pytest tests/unit/ -k "search" -q && cd dashboard && npx svelte-check` | ⬜ pending |
| 28-01-T3 | 01 | 1 | P28-T04 | unit | `uv run pytest tests/unit/ -k "ingest" -q` | ⬜ pending |
| 28-02-T1 | 02 | 2 | P28-T03 | type | `cd dashboard && npx svelte-check --output machine` | ⬜ pending |
| 28-02-T2 | 02 | 2 | P28-T05 | unit+type | `uv run pytest tests/unit/ -k "events" -q && cd dashboard && npx svelte-check` | ⬜ pending |
| 28-02-T3 | 02 | 2 | P28-T06 | type | `cd dashboard && npx svelte-check --output machine` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

No new test files required — all fixes are contract corrections. Existing test infrastructure covers:
- `tests/unit/test_ingest_api.py` — ingest job status tests
- `tests/unit/test_events_api.py` — event search tests
- `dashboard/` — svelte-check validates TypeScript types

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| QueryView streams LLM tokens in real time | P28-T01 | Requires running Ollama + backend + browser | Start backend + dashboard, submit query, confirm text streams token-by-token |
| SettingsView renders operator list | P28-T03 | Requires running backend with seeded operator | Navigate to Settings gear icon, confirm operator table visible |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
