---
phase: 52
slug: thehive-case-management-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-16
---

# Phase 52 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` — `asyncio_mode = "auto"` |
| **Quick run command** | `uv run pytest tests/unit/test_thehive_client.py tests/unit/test_thehive_sync.py -x` |
| **Full suite command** | `uv run pytest tests/unit/ -x --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_thehive_client.py tests/unit/test_thehive_sync.py -x`
- **After every plan wave:** Run `uv run pytest tests/unit/ -x --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 52-W0-01 | W0 | 0 | REQ-52-02 | unit | `uv run pytest tests/unit/test_thehive_client.py::test_case_payload_severity -x` | ❌ Wave 0 | ⬜ pending |
| 52-W0-02 | W0 | 0 | REQ-52-02 | unit | `uv run pytest tests/unit/test_thehive_client.py::test_suppress_rules_skip -x` | ❌ Wave 0 | ⬜ pending |
| 52-W0-03 | W0 | 0 | REQ-52-03 | unit | `uv run pytest tests/unit/test_thehive_client.py::test_observable_builder -x` | ❌ Wave 0 | ⬜ pending |
| 52-W0-04 | W0 | 0 | REQ-52-04 | unit | `uv run pytest tests/unit/test_thehive_client.py::test_enqueue_on_failure -x` | ❌ Wave 0 | ⬜ pending |
| 52-W0-05 | W0 | 0 | REQ-52-04 | unit | `uv run pytest tests/unit/test_thehive_sync.py::test_retry_queue_drains -x` | ❌ Wave 0 | ⬜ pending |
| 52-W0-06 | W0 | 0 | REQ-52-06 | unit | `uv run pytest tests/unit/test_thehive_sync.py::test_closure_sync_writes_sqlite -x` | ❌ Wave 0 | ⬜ pending |
| 52-W0-07 | W0 | 0 | REQ-52-06 | unit | `uv run pytest tests/unit/test_thehive_sync.py::test_closure_sync_tolerates_failure -x` | ❌ Wave 0 | ⬜ pending |
| 52-W0-08 | W0 | 0 | REQ-52-01 | unit | `uv run pytest tests/unit/test_thehive_client.py::test_ping_returns_false_when_unreachable -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_thehive_client.py` — stubs for REQ-52-02 (severity mapping, suppress rules), REQ-52-03 (observable builder), REQ-52-04 (enqueue on failure), REQ-52-01 (ping/health check)
- [ ] `tests/unit/test_thehive_sync.py` — stubs for REQ-52-04 (retry queue drain), REQ-52-06 (closure sync writes SQLite, tolerates failure)
- [ ] `uv add thehive4py==2.0.3` — install Python client (use `pytest.importorskip("thehive4py")` in test files until installed)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TheHive + Cortex containers start on GMKtec N100 | REQ-52-01 | Requires physical GMKtec deployment via SSH | SSH to GMKtec; `docker compose -f infra/docker-compose.thehive.yml up -d`; `docker ps` shows all 6 containers healthy |
| "Open in TheHive" button deep-links to correct case | REQ-52-05 | Requires live TheHive instance + live detection | Create test detection; verify badge shows `#N · New`; click button; confirm browser opens `http://192.168.1.22:9000/cases/{id}` |
| Cortex analyser runs against observable | REQ-52-07 | Requires live Cortex + API keys configured | In TheHive case, click observable → Run Analyzer → AbuseIPDB; verify result appears in Cortex Reports |
| MISP connector pulls events into TheHive | REQ-52-08 | Requires live TheHive + MISP integration configured | In TheHive Platform Management → Connectors → MISP → Test connection; verify MISP events appear as TheHive alerts |
| Case auto-creates for High/Critical detection | REQ-52-02 | Requires live TheHive + live detection pipeline | Submit a High-severity detection via API; verify case appears in TheHive UI within 30s |
| Closure sync updates verdict in SOC Brain | REQ-52-06 | Requires live TheHive + live polling task | Close a case in TheHive as True Positive; wait 5 min; verify `thehive_status = TruePositive` in SQLite |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
