---
phase: 12
slug: api-hardening-parser-coverage
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/unit/test_evtx_parser.py tests/unit/test_rate_limiting.py -x -q` |
| **Full suite command** | `uv run pytest tests/ --cov=backend --cov=ingestion --cov=detections --cov-fail-under=70 -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| P12-T01 | 12-01 | 1 | Rate limiter returns 429 after threshold | unit | `uv run pytest tests/unit/test_rate_limiting.py -x` | Wave 0 stub | ○ |
| P12-T02 | 12-02 | 2 | Caddy rejects body > limit with 413 | manual-only | `curl -X POST https://localhost/api/ingest/file -F "file=@bigfile"` | N/A | ○ |
| P12-T03 | 12-03 | 2 | EVTX parser helper functions ≥60% coverage | unit | `uv run pytest tests/unit/test_evtx_parser.py -x -q` | Wave 0 stub | ○ |
| P12-T04 | 12-03 | 2 | Overall coverage stays ≥70% | coverage gate | `uv run pytest tests/ --cov --cov-fail-under=70` | Existing CI | ○ |
| P12-T05 | 12-05 | 4 | PR CI passes on GitHub Actions | CI / manual | GitHub Actions on PR push | N/A | ○ |

> **P12-T02 note:** Caddy body limits are manual-only. Requires running Docker Caddy instance. Verify with curl after `docker compose up`.

---

## Wave 0 Gaps

- [ ] `tests/unit/test_rate_limiting.py` — covers P12-T01 (slowapi 429 behavior, disabled-in-test mode)
- [ ] `tests/unit/test_evtx_parser.py` — covers P12-T03 (all helper functions + `parse()` with mock)

---

## Phase Gate

Before `/gsd:verify-work 12`:

```bash
uv run pytest tests/ --cov=backend --cov=ingestion --cov=detections --cov-fail-under=70 -q
```

Must exit 0. Coverage must stay ≥70% (rate limiting + EVTX tests add coverage, not subtract).
