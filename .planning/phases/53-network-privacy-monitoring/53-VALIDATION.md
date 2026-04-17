---
phase: 53
slug: network-privacy-monitoring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-17
---

# Phase 53 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` (pytest-asyncio mode: auto) |
| **Quick run command** | `uv run pytest tests/unit/test_privacy_blocklist.py tests/unit/test_privacy_detection.py tests/unit/test_privacy_api.py -x -q` |
| **Full suite command** | `uv run pytest tests/unit/ tests/security/ -q --tb=short` |
| **Estimated runtime** | ~30 seconds (unit); ~90 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_privacy_blocklist.py tests/unit/test_privacy_detection.py tests/unit/test_privacy_api.py -x -q`
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 53-01-01 | 01 | 0 | stub: blocklist store | unit | `uv run pytest tests/unit/test_privacy_blocklist.py -k test_parse_easyprivacy -x` | ⬜ pending |
| 53-01-02 | 01 | 0 | stub: cookie exfil scanner | unit | `uv run pytest tests/unit/test_privacy_detection.py -k test_cookie_exfil -x` | ⬜ pending |
| 53-01-03 | 01 | 0 | stub: tracking pixel scanner | unit | `uv run pytest tests/unit/test_privacy_detection.py -k test_tracking_pixel -x` | ⬜ pending |
| 53-02-01 | 02 | 1 | _normalize_http fields | unit | `uv run python -c "from backend.models.event import NormalizedEvent; from ingestion.jobs.malcolm_collector import _normalize_http; e=_normalize_http({'zeek':{'http':{'referrer':'https://mail.example.com','request_body_len':8192,'response_body_len':45,'resp_mime_types':['image/gif']}}}); assert e.http_referrer=='https://mail.example.com'; assert e.http_request_body_len==8192; print('ok')"` | ⬜ pending |
| 53-02-02 | 02 | 1 | PrivacyBlocklistStore | unit | `uv run pytest tests/unit/test_privacy_blocklist.py -v` | ⬜ pending |
| 53-03-01 | 03 | 2 | cookie exfil detection | unit | `uv run pytest tests/unit/test_privacy_detection.py tests/unit/test_privacy_api.py -v` | ⬜ pending |
| 53-03-02 | 03 | 2 | tracking pixel detection | unit | `uv run pytest tests/unit/test_privacy_detection.py tests/unit/test_privacy_api.py -v` | ⬜ pending |
| 53-03-03 | 03 | 2 | /api/privacy/detections route | unit | `uv run pytest tests/unit/test_privacy_detection.py tests/unit/test_privacy_api.py -v` | ⬜ pending |
| 53-04-01 | 04 | 3 | dashboard privacy chip | manual | Check OverviewView for privacy chip | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_privacy_blocklist.py` — stubs for PRIV-01 through PRIV-04 + PRIV-11 (parsing, store, normalizer)
- [ ] `tests/unit/test_privacy_detection.py` — stubs for PRIV-05 through PRIV-08 (scanner logic)
- [ ] `tests/unit/test_privacy_api.py` — stubs for PRIV-09 and PRIV-10 (REST API)
- [ ] Double-guard skip pattern: `@pytest.mark.skip` decorator + `pytest.skip()` body

*Existing infrastructure covers framework — no new installs needed.*

---

## Manual-Only Verifications

| Behavior | Why Manual | Test Instructions |
|----------|------------|-------------------|
| Zeek http.log `request_body_len` field present in Malcolm OpenSearch | Requires live Malcolm at 192.168.1.22:9200 | `curl -k -u malcolm_internal:... 'https://192.168.1.22:9200/zeek_*/_search?q=_exists_:zeek.http.request_body_len&size=1'` |
| EasyPrivacy blocklist fetch from live URL | Network dependency | `uv run python -c "import urllib.request; d=urllib.request.urlopen('https://easylist.to/easylist/easyprivacy.txt').read(); print(len(d))"` |
| Cookie exfil detection fires on synthetic large-cookie HTTP event | Requires DuckDB with test event | Manual insert + scanner run |
| Dashboard privacy chip visible in UI | Requires built dashboard + running backend | Open https://localhost, check Overview tab |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
