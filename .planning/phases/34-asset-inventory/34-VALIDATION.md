---
phase: 34
slug: mitre-attack-actor-asset
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-10
---

# Phase 34 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (auto mode set in pyproject.toml) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/unit/test_asset_store.py tests/unit/test_attack_store.py tests/unit/test_attack_tagging.py tests/unit/test_assets_api.py tests/unit/test_attack_api.py -x -q` |
| **Full suite command** | `uv run pytest tests/unit/ -x` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command above
- **After every plan wave:** Run `uv run pytest tests/unit/ -x`
- **Before `/gsd:verify-work`:** Full unit suite must be green
- **Max feedback latency:** ~35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| P34-T01-upsert-technique | 01 | 0 | P34-T01 | unit | `uv run pytest tests/unit/test_attack_store.py::test_upsert_technique -x` | Wave 0 | ⬜ pending |
| P34-T01-upsert-group | 01 | 0 | P34-T01 | unit | `uv run pytest tests/unit/test_attack_store.py::test_upsert_group -x` | Wave 0 | ⬜ pending |
| P34-T01-group-tech-dedup | 01 | 0 | P34-T01 | unit | `uv run pytest tests/unit/test_attack_store.py::test_group_technique_dedup -x` | Wave 0 | ⬜ pending |
| P34-T01-revoked-filter | 01 | 0 | P34-T01 | unit | `uv run pytest tests/unit/test_attack_store.py::test_revoked_filtered -x` | Wave 0 | ⬜ pending |
| P34-T01-external-ref | 01 | 0 | P34-T01 | unit | `uv run pytest tests/unit/test_attack_store.py::test_external_ref_filter -x` | Wave 0 | ⬜ pending |
| P34-T02-extract-techniques | 01 | 0 | P34-T02 | unit | `uv run pytest tests/unit/test_attack_tagging.py::test_extract_techniques -x` | Wave 0 | ⬜ pending |
| P34-T02-case-insensitive | 01 | 0 | P34-T02 | unit | `uv run pytest tests/unit/test_attack_tagging.py::test_tag_case_insensitive -x` | Wave 0 | ⬜ pending |
| P34-T02-subtechnique | 01 | 0 | P34-T02 | unit | `uv run pytest tests/unit/test_attack_tagging.py::test_subtechnique_tag -x` | Wave 0 | ⬜ pending |
| P34-T03-top3-actors | 01 | 0 | P34-T03 | unit | `uv run pytest tests/unit/test_attack_store.py::test_actor_matching_top3 -x` | Wave 0 | ⬜ pending |
| P34-T03-confidence-labels | 01 | 0 | P34-T03 | unit | `uv run pytest tests/unit/test_attack_store.py::test_confidence_labels -x` | Wave 0 | ⬜ pending |
| P34-T04-coverage-scan | 01 | 0 | P34-T04 | unit | `uv run pytest tests/unit/test_attack_tagging.py::test_coverage_scan -x` | Wave 0 | ⬜ pending |
| P34-T04-coverage-endpoint | 02 | 0 | P34-T04 | unit | `uv run pytest tests/unit/test_attack_api.py::test_coverage_endpoint -x` | Wave 0 | ⬜ pending |
| P34-T07-upsert-from-event | 01 | 0 | P34-T07 | unit | `uv run pytest tests/unit/test_asset_store.py::test_upsert_from_event -x` | Wave 0 | ⬜ pending |
| P34-T07-internal-external | 01 | 0 | P34-T07 | unit | `uv run pytest tests/unit/test_asset_store.py::test_internal_external_tag -x` | Wave 0 | ⬜ pending |
| P34-T07-upsert-dedup | 01 | 0 | P34-T07 | unit | `uv run pytest tests/unit/test_asset_store.py::test_upsert_dedup -x` | Wave 0 | ⬜ pending |
| P34-T07-null-ip-skip | 01 | 0 | P34-T07 | unit | `uv run pytest tests/unit/test_asset_store.py::test_null_ip_skip -x` | Wave 0 | ⬜ pending |
| P34-T08-list-assets | 02 | 0 | P34-T08 | unit | `uv run pytest tests/unit/test_assets_api.py::test_list_assets -x` | Wave 0 | ⬜ pending |
| P34-T08-get-asset | 02 | 0 | P34-T08 | unit | `uv run pytest tests/unit/test_assets_api.py::test_get_asset -x` | Wave 0 | ⬜ pending |
| P34-T08-tag-asset | 02 | 0 | P34-T08 | unit | `uv run pytest tests/unit/test_assets_api.py::test_tag_asset -x` | Wave 0 | ⬜ pending |
| P34-T09-ts-compile | 03 | 1 | P34-T09 | smoke | `cd dashboard && npm run check` | N/A | ⬜ pending |
| P34-T09-ui-assets-table | 03 | 1 | P34-T09 | manual | Open /app → AssetsView in browser | N/A | ⬜ pending |
| P34-T09-ui-detail-panel | 03 | 1 | P34-T09 | manual | Click asset row → verify detail panel | N/A | ⬜ pending |
| P34-T09-ui-heatmap | 03 | 1 | P34-T09 | manual | Open ATT&CK Coverage view → verify grid | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_asset_store.py` — stubs for P34-T07 (AssetStore CRUD, internal/external tag, null IP skip, upsert dedup). In-memory SQLite via `sqlite3.connect(":memory:")` + `_DDL` import pattern (see `test_ioc_store.py`)
- [ ] `tests/unit/test_attack_store.py` — stubs for P34-T01 (technique/group/relationship upsert, revoked filter, external_ref filter), P34-T03 (actor matching top-3, confidence labels)
- [ ] `tests/unit/test_attack_tagging.py` — stubs for P34-T02 (Sigma tag extraction, case-insensitivity, sub-technique handling), P34-T04 (coverage scan using fixture YAML rule files)
- [ ] `tests/unit/test_assets_api.py` — stubs for P34-T08 (list/get/tag endpoints via FastAPI TestClient with mocked `app.state.asset_store`)
- [ ] `tests/unit/test_attack_api.py` — stubs for P34-T04 (GET /api/attack/coverage structure) and P34-T03 (GET /api/attack/actor-matches response shape)

**Mock strategy:** In-memory SQLite for store tests. FastAPI TestClient with overridden `app.state` for API tests. No real HTTP calls — mock `httpx.get` for STIX download tests.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| AssetsView renders with hostname + risk score + last seen + alert count columns | P34-T09 | Svelte UI — no browser test framework in scope | Open /app, navigate to Assets, verify 4-column table with badge rendering |
| Asset detail panel expands on row click with event timeline + detections + OSINT | P34-T09 | Interactive inline expansion | Click any asset row, verify 3-block detail panel appears below |
| ATT&CK Coverage view shows 14-column heat-scaled grid | P34-T09 | Visual rendering | Navigate to ATT&CK Coverage, verify 14 tactic columns with colour gradient |
| Tactic column click expands inline technique list | P34-T09 | Interactive behavior | Click any tactic column header, verify technique list appears inline |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 35s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
