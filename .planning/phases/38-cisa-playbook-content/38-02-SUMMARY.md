---
phase: 38-cisa-playbook-content
plan: "02"
subsystem: playbook-engine
tags: [playbooks, cisa, sqlite-migrations, pydantic-models, tdd]
dependency_graph:
  requires: [38-01]
  provides: [PlaybookStep-extended, CISA-playbook-content, seed-replace-strategy]
  affects: [backend/models/playbook.py, backend/data/builtin_playbooks.py, backend/api/playbooks.py, backend/stores/sqlite_store.py]
tech_stack:
  added: []
  patterns: [idempotent-alter-table, replace-not-supplement-seed, json-blob-field-extension, tdd-red-green]
key_files:
  created: []
  modified:
    - backend/models/playbook.py
    - backend/data/builtin_playbooks.py
    - backend/api/playbooks.py
    - backend/stores/sqlite_store.py
    - tests/unit/test_builtin_playbooks.py
decisions:
  - "PlaybookStep new fields stored in existing JSON blob column — zero SQLite column migration needed for step fields"
  - "create_playbook() updated to persist source column alongside existing columns"
  - "Seed strategy: UPDATE source='nist' WHERE is_builtin=1 AND source='custom', then DELETE WHERE source='nist', then INSERT CISA if source='cisa' count==0"
  - "test_builtin_playbooks.py updated to reflect CISA content — old NIST assertions replaced"
metrics:
  duration_seconds: 341
  completed_date: "2026-04-11"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 5
---

# Phase 38 Plan 02: CISA Playbook Model Extension + Content Summary

**One-liner:** Extended PlaybookStep with 5 CISA enrichment fields, replaced 5 NIST starters with 4 CISA IR playbooks (full ATT&CK IDs, SLAs, escalation gates, containment actions), and added 3 idempotent SQLite migrations.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Extend PlaybookStep model + SQLite migrations | b7e7c04 | backend/models/playbook.py, backend/stores/sqlite_store.py |
| 2 | Replace BUILTIN_PLAYBOOKS with CISA content + update seed | 1c3d30d | backend/data/builtin_playbooks.py, backend/api/playbooks.py, tests/unit/test_builtin_playbooks.py |

## What Was Built

### Task 1: Model Extension + Migrations

`PlaybookStep` gained 5 new optional fields (all with safe defaults for backward compatibility with existing stored JSON blobs):
- `attack_techniques: list[str] = []` — ATT&CK technique IDs per step
- `escalation_threshold: Optional[Literal["critical", "high"]] = None` — severity-based escalation gate
- `escalation_role: Optional[str] = None` — role to notify at escalation (e.g. "CISO", "SOC Manager")
- `time_sla_minutes: Optional[int] = None` — informational SLA badge
- `containment_actions: list[str] = []` — controlled-vocab actions for this step

`PlaybookRunAdvance` gained `containment_action: Optional[str] = None`.

`SQLiteStore.__init__` gained 3 idempotent `ALTER TABLE` migrations:
- `playbooks ADD COLUMN source TEXT NOT NULL DEFAULT 'custom'`
- `playbook_runs ADD COLUMN escalation_acknowledged TEXT NOT NULL DEFAULT '[]'`
- `playbook_runs ADD COLUMN active_case_id TEXT`

`create_playbook()` updated to include `source` in the INSERT column list.

### Task 2: CISA Content + Seed Strategy

`backend/data/builtin_playbooks.py` replaced with 4 CISA Federal IR Playbooks:
1. **Phishing / BEC Response** — 7 steps, triggers: phishing/BEC/T1566/T1598/T1534
2. **Ransomware Response** — 8 steps, triggers: ransomware/T1486/T1490/T1059
3. **Credential / Account Compromise Response** — 7 steps, triggers: T1078/T1110/T1003
4. **Malware / Intrusion Response** — 8 steps, triggers: malware/C2/T1059/T1071/T1055

Every step has: non-empty `attack_techniques`, positive `time_sla_minutes`, valid controlled-vocab `containment_actions`. Escalation gates are set on steps requiring SOC Manager or CISO notification.

`seed_builtin_playbooks()` updated with replace-not-supplement strategy:
1. Tag existing builtin rows `source='nist'` (ALTER TABLE DEFAULT fills as 'custom')
2. `DELETE WHERE is_builtin=1 AND source='nist'`
3. Skip if CISA builtins already present (`COUNT(*) WHERE is_builtin=1 AND source='cisa' > 0`)
4. Insert 4 CISA playbooks

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_builtin_playbooks.py had NIST assertions**
- **Found during:** Task 2 full unit suite run
- **Issue:** Existing `test_builtin_playbooks.py` asserted exactly 5 playbooks with NIST names ("Phishing Initial Triage", etc.) — these tests were correct for the old NIST content but become incorrect after Phase 38 replaces them with CISA playbooks.
- **Fix:** Updated test file to assert 4 CISA playbooks with correct CISA names. All assertions consistent with new content. Added `test_seeded_playbooks_have_source_cisa` to cover the source field.
- **Files modified:** `tests/unit/test_builtin_playbooks.py`
- **Commit:** 1c3d30d

None beyond the test update above — plan executed as written.

## Verification Results

```
uv run pytest tests/unit/test_playbooks_model.py -x -q  →  4 passed
uv run pytest tests/unit/test_playbooks_seed.py tests/unit/test_playbooks_cisa.py -x -q  →  10 passed
uv run pytest tests/unit/ -x -q  →  1012 passed, 1 skipped, 9 xfailed, 7 xpassed
```

Model serialization check:
```python
PlaybookStep(step_number=1, title='t', description='d',
    attack_techniques=['T1566'], escalation_threshold='critical',
    escalation_role='CISO', time_sla_minutes=30, containment_actions=['block_ip'])
# → {'step_number': 1, 'title': 't', 'description': 'd', 'requires_approval': True,
#    'evidence_prompt': None, 'attack_techniques': ['T1566'],
#    'escalation_threshold': 'critical', 'escalation_role': 'CISO',
#    'time_sla_minutes': 30, 'containment_actions': ['block_ip']}
```

BUILTIN_PLAYBOOKS length check:
```python
# len=4, names=['Phishing / BEC Response', 'Ransomware Response',
#               'Credential / Account Compromise Response', 'Malware / Intrusion Response']
```

## Self-Check: PASSED

All created/modified files exist on disk. Both task commits (b7e7c04, 1c3d30d) found in git log.
