---
phase: 13-mature-soc-metrics-kpis-hf-model-upgrade
plan: "01"
subsystem: infra
tags: [ollama, llm, cybersecurity, adr, model-selection, foundation-sec]

# Dependency graph
requires: []
provides:
  - "ADR-020-hf-model.md: architecture decision record selecting Foundation-Sec-8B as cybersec LLM"
  - "OLLAMA_CYBERSEC_MODEL env var name documented for Plan 02"
affects:
  - 13-02-model-routing
  - backend/core/config.py

# Tech tracking
tech-stack:
  added: ["foundation-sec:8b (Ollama model, Q4_K_M)"]
  patterns: ["Dual-model Ollama routing — qwen3:14b for general, foundation-sec:8b for cybersec domain tasks"]

key-files:
  created: ["docs/ADR-020-hf-model.md"]
  modified: []

key-decisions:
  - "Foundation-Sec-8B (Cisco Foundation AI, Apache 2.0) selected over Seneca-Cybersecurity-LLM due to institutional provenance, documented training corpus, clear licence, and Ollama-native GGUF support"
  - "Q4_K_M quantisation chosen — ~4.8 GB VRAM fits alongside qwen3:14b Q4_K_M (~9 GB) within RTX 5080 16 GB budget"
  - "OLLAMA_CYBERSEC_MODEL is the env var name for Plan 02 to implement; default value foundation-sec:8b"

patterns-established:
  - "ADR pattern: Security scan table (licence, provenance, CVEs, publisher trust, prompt injection risk) before any new LLM adoption"
  - "Hardware fit table: always document VRAM estimates for each quantisation tier when evaluating Ollama models"

requirements-completed: [P13-T01]

# Metrics
duration: 8min
completed: 2026-03-27
---

# Phase 13 Plan 01: HF Model Security Review and ADR-020 Summary

**Foundation-Sec-8B (Cisco Foundation AI, Apache 2.0, Q4_K_M, ~4.8 GB VRAM) selected as cybersec LLM with full security scan and hardware fit analysis documented in ADR-020**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-27T14:07:55Z
- **Completed:** 2026-03-27T14:15:00Z
- **Tasks:** 1/1
- **Files modified:** 1

## Accomplishments
- Wrote ADR-020-hf-model.md with complete security evaluation of two HF candidate models
- Documented security scan findings: licence, training data provenance, CVEs, publisher trust, prompt injection risk for both candidates
- Produced hardware fit table covering Q4_K_M / Q5_K_M / Q8_0 quantisation variants against RTX 5080 16 GB VRAM budget
- Established `OLLAMA_CYBERSEC_MODEL` env var name as the gating artefact for Plan 02 model routing work

## Task Commits

Each task was committed atomically:

1. **Task 1: Research and write ADR-020-hf-model.md** - `500a2df` (docs)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `docs/ADR-020-hf-model.md` - Architecture Decision Record: cybersec LLM selection, security scan, hardware fit table, Foundation-Sec-8B decision with rationale and consequences

## Decisions Made
- Foundation-Sec-8B selected over Seneca-Cybersecurity-LLM: institutional publisher (Cisco), Apache 2.0 licence, documented corpus, Ollama-native GGUF, fits in remaining VRAM headroom
- Seneca rejected: undocumented licence (commercial restriction risk), poorly documented training data, individual contributor with no institutional backing, no first-party GGUF
- Q4_K_M chosen as recommended quantisation: balances quality and VRAM (~4.8 GB), leaves buffer below the 7 GB headroom after qwen3:14b

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

Operators must pull the model before first use:
```bash
ollama pull foundation-sec:8b
```

The `OLLAMA_CYBERSEC_MODEL` environment variable will be wired into `backend/core/config.py` in Plan 02.

## Next Phase Readiness

- ADR-020-hf-model.md passes automated validation (all assertions green)
- `OLLAMA_CYBERSEC_MODEL` env var name is established; Plan 02 can add it to Settings and implement model routing
- No blockers

---
*Phase: 13-mature-soc-metrics-kpis-hf-model-upgrade*
*Completed: 2026-03-27*
