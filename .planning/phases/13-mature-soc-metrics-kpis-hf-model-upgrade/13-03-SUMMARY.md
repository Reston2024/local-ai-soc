---
phase: 13-mature-soc-metrics-kpis-hf-model-upgrade
plan: "03"
subsystem: ingestion/seeding
tags:
  - huggingface
  - datasets
  - seed-data
  - ingestion
  - siem
dependency_graph:
  requires:
    - 13-01  # ADR-020 confirming HF model selection
  provides:
    - scripts/seed_siem_data.py
    - datasets dependency in pyproject.toml
  affects:
    - 13-04  # metrics service needs seed events for non-zero MTTD/MTTR
tech_stack:
  added:
    - datasets==4.8.4 (Hugging Face datasets library)
    - pyarrow==23.0.1 (transitive)
    - pandas==3.0.1 (transitive)
  patterns:
    - Streaming HF dataset load (streaming=True, trust_remote_code=False)
    - Async script with asyncio.run(main())
    - IngestionLoader.ingest_events() for direct event batch ingestion
key_files:
  created:
    - scripts/seed_siem_data.py
  modified:
    - pyproject.toml
    - uv.lock
decisions:
  - "datasets>=2.21.0 pinned (floor pin) to avoid API breakage; resolved to 4.8.4"
  - "streaming=True used to avoid downloading the full dataset; islice(ds, limit) caps at --limit rows"
  - "trust_remote_code=False enforced as a security requirement"
  - "Severity mapping: 'info/informational/debug/verbose/unknown' -> 'low' per plan spec (differs from normalizer which maps these to 'info')"
  - "hostname field mapped from 'Source IP' as fallback when no explicit host column exists in HF dataset"
  - "Dry-run mode validates normalisation and prints 3 sample events without writing to any store"
metrics:
  duration_minutes: 15
  completed_date: "2026-03-27"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
---

# Phase 13 Plan 03: HF SIEM Dataset Seed Script Summary

**One-liner:** Streaming seed script fetching darkknight25/Advanced_SIEM_Dataset via HF datasets library and ingesting via IngestionLoader with dry-run support and trust_remote_code=False security guard.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add datasets dependency to pyproject.toml | 4a10db2 | pyproject.toml, uv.lock |
| 2 | Write scripts/seed_siem_data.py | fdd1809 | scripts/seed_siem_data.py |

## What Was Built

### Task 1: datasets dependency
Added `"datasets>=2.21.0"` to pyproject.toml under a `# Data seeding` comment block. `uv sync` resolved `datasets==4.8.4` with transitive dependencies: pyarrow, pandas, aiohttp, multiprocess, dill, tzdata.

### Task 2: scripts/seed_siem_data.py
A standalone async Python script that:

1. **Argument parsing** — `--dry-run` flag and `--limit N` (default 500) via argparse.
2. **HF dataset loading** — `datasets.load_dataset(path="darkknight25/Advanced_SIEM_Dataset", split="train", streaming=True, trust_remote_code=False)` + `itertools.islice(ds, limit)`.
3. **Field normalisation** — `_normalise_row(row)` maps HF columns:
   - `event_id`: `uuid.uuid4()`
   - `timestamp`: parsed via `_parse_timestamp()` with multiple format fallbacks
   - `source_type`: `"hf_siem_seed"`
   - `hostname`: `Source IP / hostname / Host`
   - `username`: `User / username`
   - `process_name`: `Process / process`
   - `event_type`: `Event Type / event_type / "siem_event"`
   - `severity`: normalised via `_normalise_severity()` with alias map
   - `src_ip`, `dst_ip`: network columns
   - `raw_event`: `json.dumps(row, default=str)`
4. **Dry-run mode** — prints first 3 normalised events and total count; exits 0 without writing.
5. **Ingestion** — initialises DuckDBStore, ChromaStore, SQLiteStore, wraps in `Stores`, creates `IngestionLoader`, calls `ingest_events()` in batches of 50.
6. **Shutdown** — cancels DuckDB write worker task, closes Ollama HTTP client.
7. **Error handling** — network failures or missing dataset print a clear error and `sys.exit(1)`.

## Verification

```
uv run python -c "import datasets; print('datasets', datasets.__version__)"
# datasets 4.8.4  -> exit 0

uv run python scripts/seed_siem_data.py --dry-run --limit 5
# Prints 3 normalised event samples with timestamps, severity, event_type  -> exit 0

grep "darkknight25" scripts/seed_siem_data.py
# _HF_DATASET = "darkknight25/Advanced_SIEM_Dataset"  -> hit

grep "trust_remote_code=False" scripts/seed_siem_data.py
# trust_remote_code=False,  -> hit
```

All success criteria met.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `scripts/seed_siem_data.py` — exists and verified
- [x] `pyproject.toml` contains `datasets` — verified
- [x] Commits `4a10db2` and `fdd1809` — verified in git log
- [x] `--dry-run --limit 5` exits 0 with normalised event output — verified
