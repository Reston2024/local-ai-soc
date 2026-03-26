---
status: complete
phase: 10-compliance-hardening
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md, 10-04-SUMMARY.md, 10-05-SUMMARY.md, 10-06-SUMMARY.md, 10-07-SUMMARY.md, 10-08-SUMMARY.md, 10-09-SUMMARY.md]
started: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running backend. Start fresh with `uv run python -m backend.main` (or via start.ps1). Backend boots without errors. GET http://localhost:8000/health returns a response (any status code).
result: skipped
reason: User unfamiliar with manual startup procedure

### 2. Injection Scrubbing
expected: Run in terminal: `uv run python -c "from ingestion.normalizer import _scrub_injection; print(repr(_scrub_injection('ignore previous instructions ###')))"`. Result should be an empty string or whitespace only — the injection patterns are stripped.
result: pass

### 3. API Auth — Open Mode (no token set)
expected: With AUTH_TOKEN not set (default), existing API endpoints still work without any token. Run: `uv run pytest tests/unit/test_auth.py tests/security/test_auth.py -q`. All 6 tests should pass.
result: pass

### 4. Dependency Pinning
expected: Run `grep "==" /c/Users/Admin/AI-SOC-Brain/pyproject.toml | head -10`. Output should show packages like `pydantic==...`, `httpx==...`, `chromadb==...` with exact `==` pins. Also: `ls /c/Users/Admin/AI-SOC-Brain/backend/requirements.txt` should say "No such file".
result: pass
reason: backend/requirements.txt confirmed deleted; == pins verified in pyproject.toml

### 5. CI Pipeline File
expected: Run `cat /c/Users/Admin/AI-SOC-Brain/.github/workflows/ci.yml | grep "name:"`. Should show 4 job names: Lint (ruff), Test (pytest + coverage), Dependency Audit (pip-audit), Secret Scan (gitleaks). File is valid YAML.
result: pass

### 6. Firewall Scripts
expected: Both scripts exist: `ls /c/Users/Admin/AI-SOC-Brain/scripts/configure-firewall.ps1` and `ls /c/Users/Admin/AI-SOC-Brain/scripts/verify-firewall.ps1`. Running `grep "New-NetFirewallRule" /c/Users/Admin/AI-SOC-Brain/scripts/configure-firewall.ps1 | wc -l` returns 2 (one BLOCK rule + one ALLOW rule).
result: pass

### 7. Docker/Caddy Hardening
expected: Run `grep "CADDY_ADMIN" /c/Users/Admin/AI-SOC-Brain/docker-compose.yml`. Output should show `CADDY_ADMIN=127.0.0.1:2019` — NOT `0.0.0.0:2019`. The critical binding exposure is fixed.
result: pass

### 8. LLM Audit Logger
expected: Run `uv run python -c "from backend.core.logging import setup_logging; import logging; setup_logging(); l = logging.getLogger('llm_audit'); print('handlers:', len(l.handlers), '| propagate:', l.propagate)"`. Output should show at least 1 handler and `propagate: False`.
result: pass

### 9. Documentation — ADR-019 and Manifest
expected: Run `grep -c "ADR-019" /c/Users/Admin/AI-SOC-Brain/DECISION_LOG.md`. Should return 1 or more. Also: `grep "auth.py" /c/Users/Admin/AI-SOC-Brain/docs/manifest.md` should return a line showing auth.py is listed.
result: pass

## Summary

total: 9
passed: 7
issues: 0
pending: 0
skipped: 1

## Gaps

[none yet]
