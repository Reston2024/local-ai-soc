---
phase: 50
slug: misp-threat-intelligence-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 50 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (pytest-asyncio 1.3.0, mode: auto) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/unit/test_misp_sync.py -x -q` |
| **Full suite command** | `uv run pytest tests/unit/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_misp_sync.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/unit/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 50-01-01 | 01 | 0 | PHASE33-01 | unit | `uv run pytest tests/unit/test_misp_sync.py -x -q` | ❌ W0 | ⬜ pending |
| 50-01-02 | 01 | 0 | VIEW-01 | unit | `uv run pytest tests/unit/test_intel_api.py -x -q` | ❌ W0 | ⬜ pending |
| 50-02-01 | 02 | 1 | DOCKER-01 | manual | `docker compose -f infra/misp/docker-compose.misp.yml config` | ❌ W0 | ⬜ pending |
| 50-02-02 | 02 | 1 | PHASE33-01 | unit | `uv run pytest tests/unit/test_misp_sync.py::test_misp_worker_sync -x` | ❌ W0 | ⬜ pending |
| 50-02-03 | 02 | 1 | PHASE33-01 | unit | `uv run pytest tests/unit/test_misp_sync.py::test_attribute_type_mapping -x` | ❌ W0 | ⬜ pending |
| 50-02-04 | 02 | 1 | PHASE33-01 | unit | `uv run pytest tests/unit/test_misp_sync.py::test_confidence_mapping -x` | ❌ W0 | ⬜ pending |
| 50-02-05 | 02 | 1 | PHASE33-01 | unit | `uv run pytest tests/unit/test_misp_sync.py::test_retroactive_trigger -x` | ❌ W0 | ⬜ pending |
| 50-03-01 | 03 | 2 | VIEW-01 | unit | `uv run pytest tests/unit/test_intel_api.py::test_misp_events_endpoint -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_misp_sync.py` — stubs for PHASE33-01 (MispSyncService, MispWorker, type mapping, confidence, retroactive trigger)
- [ ] `tests/unit/test_intel_api.py` — stubs for VIEW-01 (MISP events endpoint)
- [ ] `infra/misp/docker-compose.misp.yml` — compose file skeleton (DOCKER-01)
- [ ] `infra/misp/.env.misp.template` — secrets template
- [ ] `backend/services/intel/misp_sync.py` — MispSyncService stub
- [ ] `uv add pymisp` — dependency install

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MISP web UI accessible at http://gmktec-ip:8080 | DOCKER-01 | Requires live Docker deploy on GMKtec | `curl -I http://<gmktec-ip>:8080` returns 200 |
| MISP admin API key retrievable from UI | DOCKER-01 | Requires human login to MISP web UI | Login → Administration → List Auth Keys → copy 40-char key |
| CIRCL OSINT feed attributes appear in ioc_store after sync | PHASE33-01 | Requires live MISP instance with internet access | Query SQLite: `SELECT COUNT(*) FROM ioc_store WHERE feed_source='misp'` > 0 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
