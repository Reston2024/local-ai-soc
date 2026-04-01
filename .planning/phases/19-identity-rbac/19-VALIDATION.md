---
phase: 19
slug: identity-rbac
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `uv run pytest tests/unit/test_auth.py tests/unit/test_rbac.py tests/unit/test_operators.py -x -q` |
| **Full suite command** | `uv run pytest tests/unit/ -q --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_auth.py tests/unit/test_rbac.py tests/unit/test_operators.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/unit/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | P19-T01 | unit | `uv run pytest tests/unit/test_operators.py -x -q` | ❌ W0 | ⬜ pending |
| 19-01-02 | 01 | 1 | P19-T02 | unit | `uv run pytest tests/unit/test_auth.py -x -q` | ✅ (update) | ⬜ pending |
| 19-02-01 | 02 | 2 | P19-T03 | unit | `uv run pytest tests/unit/test_rbac.py -x -q` | ❌ W0 | ⬜ pending |
| 19-03-01 | 03 | 2 | P19-T04 | unit | `uv run pytest tests/unit/test_totp.py -x -q` | ❌ W0 | ⬜ pending |
| 19-04-01 | 04 | 3 | P19-T05 | unit | `uv run pytest tests/unit/test_operators_api.py -x -q` | ❌ W0 | ⬜ pending |
| 19-04-02 | 04 | 3 | P19-T05 | manual | See manual section | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_operators.py` — stubs for P19-T01 (operator CRUD, bcrypt hash/verify, bootstrap)
- [ ] `tests/unit/test_rbac.py` — stubs for P19-T03 (require_role dep, 403 on violation, role boundary per route)
- [ ] `tests/unit/test_totp.py` — stubs for P19-T04 (TOTP enable, verify, QR URI format)
- [ ] `tests/unit/test_operators_api.py` — stubs for P19-T05 (operator CRUD endpoints, key rotation)
- [ ] Update `tests/unit/test_auth.py` — extend for multi-operator lookup, legacy AUTH_TOKEN backward compat

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SettingsView Operators tab renders in browser | P19-T05 | Svelte UI — no automated browser test | Open http://localhost:5174/app/, navigate Settings → Operators, verify operator list, create new operator, rotate key |
| TOTP QR code scans with authenticator app | P19-T04 | Requires physical authenticator app | Enable TOTP for an operator, scan QR with Google Authenticator/Authy, confirm 6-digit codes work |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
