---
phase: 27
slug: malcolm-nsm-integration-and-live-feed-collector
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-07
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) |
| **Config file** | pyproject.toml (pytest-asyncio mode: auto) |
| **Quick run command** | `uv run pytest tests/unit/test_malcolm_collector.py tests/unit/test_malcolm_normalizer.py tests/unit/test_dispatch_endpoint.py -x -q` |
| **Full suite command** | `uv run pytest tests/unit/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command above
- **After every plan wave:** Run `uv run pytest tests/unit/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 27-00-01 | 00 | 0 | P27-T02 | unit stub | `uv run pytest tests/unit/test_malcolm_collector.py -q` | ❌ W0 | ⬜ pending |
| 27-00-02 | 00 | 0 | P27-T02 | unit stub | `uv run pytest tests/unit/test_malcolm_normalizer.py -q` | ❌ W0 | ⬜ pending |
| 27-00-03 | 00 | 0 | P27-T04 | unit stub | `uv run pytest tests/unit/test_dispatch_endpoint.py -q` | ❌ W0 | ⬜ pending |
| 27-01-01 | 01 | 1 | P27-T01 | manual | `curl -sk -u "admin:Adam1000!" https://192.168.1.22:9200/_cat/indices` | N/A | ⬜ pending |
| 27-02-01 | 02 | 2 | P27-T03 | unit | `uv run python -c "from backend.core.config import settings; print(settings.MALCOLM_ENABLED)"` | N/A | ⬜ pending |
| 27-02-02 | 02 | 2 | P27-T02 | unit | `uv run pytest tests/unit/test_malcolm_collector.py -x -v` | ❌ W0 | ⬜ pending |
| 27-03-01 | 03 | 2 | P27-T02 | unit | `uv run pytest tests/unit/test_malcolm_normalizer.py -x -v` | ❌ W0 | ⬜ pending |
| 27-04-01 | 04 | 3 | P27-T04 | unit | `uv run pytest tests/unit/test_dispatch_endpoint.py -x -v` | ❌ W0 | ⬜ pending |
| 27-05-01 | 05 | 3 | P27-T05 | manual | `scripts/sync-chroma-corpus.ps1 -DryRun` | N/A | ⬜ pending |
| 27-06-01 | 06 | 4 | P27-T06 | manual | `scripts/e2e-malcolm-verify.ps1` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_malcolm_collector.py` — stubs for P27-T02 (MalcolmCollector lifecycle)
- [ ] `tests/unit/test_malcolm_normalizer.py` — stubs for P27-T02 (field normalization: alerts + syslog)
- [ ] `tests/unit/test_dispatch_endpoint.py` — stubs for P27-T04 (POST /dispatch happy path + 422)

*Existing infrastructure covers all other phase requirements (pytest-asyncio already configured).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OpenSearch LAN accessible at 192.168.1.22:9200 | P27-T01 | Requires SSH to remote server + live network | `curl -sk -u "admin:Adam1000!" https://192.168.1.22:9200/_cat/indices` |
| MalcolmCollector ingests live alerts from Malcolm | P27-T02 | Requires live Malcolm instance on LAN | Check DuckDB event count before/after with Malcolm running |
| ChromaDB corpus syncs from remote host | P27-T05 | Requires SSH + scp + remote file existence | Run `scripts/sync-chroma-corpus.ps1`, verify doc count |
| Full alert pipeline E2E | P27-T06 | Requires live IPFire, Malcolm, and local-ai-soc | Run `scripts/e2e-malcolm-verify.ps1`, expect PASS within 2 poll cycles |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
