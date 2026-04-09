---
phase: 31
slug: malcolm-full-telemetry
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (uv run pytest) |
| **Config file** | pyproject.toml (pytest-asyncio mode: auto) |
| **Quick run command** | `uv run pytest tests/unit/test_malcolm_collector.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_malcolm_collector.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 31-T01 | 01 | 1 | P31-T01 | unit | `uv run pytest tests/unit/test_normalized_event.py -x -q` | ⬜ pending |
| 31-T02 | 01 | 1 | P31-T02 | unit | `uv run pytest tests/unit/test_malcolm_collector.py::test_normalize_tls -x -q` | ⬜ pending |
| 31-T03 | 01 | 1 | P31-T03 | unit | `uv run pytest tests/unit/test_malcolm_collector.py::test_normalize_dns -x -q` | ⬜ pending |
| 31-T04 | 01 | 1 | P31-T04 | unit | `uv run pytest tests/unit/test_malcolm_collector.py::test_normalize_fileinfo -x -q` | ⬜ pending |
| 31-T05 | 01 | 1 | P31-T05 | unit | `uv run pytest tests/unit/test_malcolm_collector.py::test_normalize_anomaly -x -q` | ⬜ pending |
| 31-T06 | 01 | 1 | P31-T06 | unit | `uv run pytest tests/unit/test_malcolm_collector.py::test_poll_all_eve_types -x -q` | ⬜ pending |
| 31-T07 | 02 | 1 | P31-T07 | unit | `uv run pytest tests/unit/test_evidence_archiver.py -x -q` | ⬜ pending |
| 31-T08 | 02 | 1 | P31-T08 | manual | curl http://192.168.1.22:PORT/normalized/index | ⬜ pending |
| 31-T09 | 01 | 2 | P31-T09 | unit | `uv run pytest tests/unit/test_malcolm_collector.py::test_ubuntu_poll -x -q` | ⬜ pending |
| 31-T10 | 03 | 2 | P31-T10 | manual | Open dashboard, verify chip row renders, click DNS chip, verify event list filters | ⬜ pending |
| 31-T11 | 01 | 1 | P31-T11 | unit | `uv run pytest tests/unit/test_normalized_event.py::test_ocsf_new_types -x -q` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_malcolm_collector.py` — add stubs for test_normalize_tls, test_normalize_dns, test_normalize_fileinfo, test_normalize_anomaly, test_poll_all_eve_types, test_ubuntu_poll
- [ ] `tests/unit/test_evidence_archiver.py` — stub file with test_write_gzip, test_sha256_written, test_daily_rotation
- [ ] `tests/unit/test_normalized_event.py` — add stubs for test_new_fields_in_duckdb_row, test_ocsf_new_types

*Existing infrastructure (pytest-asyncio auto mode, conftest.py) covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Ubuntu FastAPI endpoint live | P31-T08 | Requires Ubuntu box running | `curl http://192.168.1.22:PORT/normalized/index` returns JSON list |
| Ubuntu poll source ingest | P31-T09 | Requires Ubuntu endpoint live | Set MALCOLM_ENABLED=true, wait 60s, check DuckDB for ubuntu_normalized events |
| EventsView chip filter | P31-T10 | Svelte component — browser test | Open dashboard, click TLS chip, verify events list shows only tls events |
| Evidence archive gzip written | P31-T07 | Requires Ubuntu filesystem access | `ls -la /mnt/evidence/raw/` shows daily .gz files with matching .sha256 |

---

## DuckDB Migration Idempotency Test

After adding all 20 new columns, run schema bootstrap twice:
```bash
uv run python -c "
import asyncio
from backend.stores.duckdb_store import DuckDBStore
async def test():
    store = DuckDBStore('data/test_migration')
    await store.initialise_schema()
    await store.initialise_schema()  # second call must not raise
    print('IDEMPOTENT OK')
asyncio.run(test())
"
```
Expected: `IDEMPOTENT OK` — no DuckDB error on second call.
