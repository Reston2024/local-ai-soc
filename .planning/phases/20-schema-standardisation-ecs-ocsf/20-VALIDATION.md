---
phase: 20
slug: schema-standardisation-ecs-ocsf
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio (auto mode) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/unit/test_normalized_event_ecs.py tests/unit/test_field_mapper.py tests/unit/test_duckdb_migration.py -q` |
| **Full suite command** | `uv run pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command above
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 20-00-01 | 00 | 0 | P20-T01–T05 | unit stubs | `uv run pytest tests/unit/test_normalized_event_ecs.py tests/unit/test_field_mapper.py tests/unit/test_duckdb_migration.py -q` | ❌ W0 | ⬜ pending |
| 20-01-01 | 01 | 1 | P20-T01 | unit | `uv run pytest tests/unit/test_normalized_event_ecs.py -v` | ❌ W0 | ⬜ pending |
| 20-01-02 | 01 | 1 | P20-T01 | regression | `uv run pytest tests/ -q --tb=short` | ✅ | ⬜ pending |
| 20-02-01 | 02 | 1 | P20-T02 | unit | `uv run pytest tests/unit/test_field_mapper.py -v` | ❌ W0 | ⬜ pending |
| 20-02-02 | 02 | 1 | P20-T02 | regression | `uv run pytest tests/ -q --tb=short` | ✅ | ⬜ pending |
| 20-03-01 | 03 | 2 | P20-T03 | unit | `uv run pytest tests/unit/test_duckdb_migration.py -v` | ❌ W0 | ⬜ pending |
| 20-04-01 | 04 | 2 | P20-T04 | sigma smoke | `uv run pytest tests/sigma_smoke/ -v` | ✅ | ⬜ pending |
| 20-04-02 | 04 | 2 | P20-T04 | unit | `uv run pytest tests/unit/test_field_map.py -v` | ✅ (extends) | ⬜ pending |
| 20-05-01 | 05 | 2 | P20-T05 | unit | `uv run pytest tests/unit/test_entity_extractor.py -v` | ✅ (extends) | ⬜ pending |
| 20-05-02 | 05 | 2 | P20-T05 | regression | `uv run pytest tests/ -q --tb=short` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_normalized_event_ecs.py` — stubs for P20-T01 (ECS fields, OCSF class_uid, backward compat)
- [ ] `tests/unit/test_field_mapper.py` — stubs for P20-T02 (FieldMapper pure function, each parser source type)
- [ ] `tests/unit/test_duckdb_migration.py` — stubs for P20-T03 (additive migration, db_meta version table)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| EVTX ingest → ECS entity graph | P20-T05 | Requires running backend + DuckDB file | Start server, ingest fixtures/sample.evtx, check graph nodes use ECS field names |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
