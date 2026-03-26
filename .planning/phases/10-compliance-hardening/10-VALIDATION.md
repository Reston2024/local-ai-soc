---
phase: 10
slug: compliance-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (existing) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/unit/ tests/security/ -x -q` |
| **Full suite command** | `uv run pytest tests/unit/ tests/security/ --cov=backend --cov=ingestion --cov=detections --cov-report=term-missing -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ tests/security/ -x -q`
- **After every plan wave:** Run full suite with coverage
- **Before `/gsd:verify-work`:** Full suite must be green with coverage ≥ 70%
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 10-01-01 | 01 | 0 | P10-T02, P10-T09 | unit stub | `uv run pytest tests/unit/test_normalizer.py tests/security/ -x -q` | ⬜ pending |
| 10-01-02 | 01 | 0 | P10-T06, P10-T09 | unit stub | `uv run pytest tests/unit/test_auth.py tests/security/test_auth.py -x -q` | ⬜ pending |
| 10-01-03 | 01 | 0 | P10-T07 | unit stub | `uv run pytest tests/unit/test_ollama_audit.py -x -q` | ⬜ pending |
| 10-02-01 | 02 | 1 | P10-T02 | unit | `uv run pytest tests/unit/test_normalizer.py -x -q` | ⬜ pending |
| 10-02-02 | 02 | 1 | P10-T09 | security | `uv run pytest tests/security/test_injection.py -x -q` | ⬜ pending |
| 10-03-01 | 03 | 1 | P10-T06 | unit | `uv run pytest tests/unit/test_auth.py -x -q` | ⬜ pending |
| 10-03-02 | 03 | 1 | P10-T09 | security | `uv run pytest tests/security/test_auth.py -x -q` | ⬜ pending |
| 10-04-01 | 04 | 1 | P10-T07 | unit | `uv run pytest tests/unit/test_ollama_audit.py -x -q` | ⬜ pending |
| 10-05-01 | 05 | 2 | P10-T05 | verify | `uv run python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); [print(k,v) for k,v in d['project']['dependencies']]"` | ⬜ pending |
| 10-05-02 | 05 | 2 | P10-T05 | verify | `uv run pip-audit --desc 2>&1 \| tail -5` | ⬜ pending |
| 10-06-01 | 06 | 2 | P10-T01 | CI verify | `cat .github/workflows/ci.yml` | ⬜ pending |
| 10-07-01 | 07 | 3 | P10-T03, P10-T04, P10-T08 | manual/script | `pwsh scripts/verify-firewall.ps1` | ⬜ pending |
| 10-08-01 | 08 | 3 | P10-T10 | verify | `cat docs/manifest.md \| head -20` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/security/__init__.py` — empty init for security test package
- [ ] `tests/security/test_injection.py` — xfail stubs for P10-T02 and Sigma SQL injection
- [ ] `tests/security/test_auth.py` — xfail stubs for P10-T06 auth endpoint protection
- [ ] `tests/unit/test_auth.py` — xfail stubs for `verify_token` dependency unit tests
- [ ] `tests/unit/test_ollama_audit.py` — xfail stubs for P10-T07 LLM audit log

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Firewall rule blocks port 11434 | P10-T03 | Requires Windows Firewall admin + network test | Run `pwsh scripts/verify-firewall.ps1`; verify rule shown as enabled |
| Caddy admin API not reachable on 0.0.0.0 | P10-T04 | Requires running Docker + network probe | `curl http://127.0.0.1:2019/config/ -f` should succeed; `curl http://0.0.0.0:2019/config/` should fail or be same as localhost only |
| icacls ACL on data/ is restricted | P10-T08 | Requires Windows ACL inspection | Run `pwsh scripts/configure-acls.ps1 -WhatIf`; verify output shows intended permissions |
| CI workflow triggers on push | P10-T01 | Requires GitHub remote + push | Push a trivial commit to a branch and verify Actions tab shows a run |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
