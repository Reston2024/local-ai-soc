---
phase: 22-ai-lifecycle-hardening
plan: "05"
subsystem: ui
tags: [svelte, llm, prompt-engineering, ai-safety, advisory, nist-ai-rmf]

# Dependency graph
requires:
  - phase: 22-ai-lifecycle-hardening
    provides: analyst_qa.py and triage.py prompt modules, InvestigationView.svelte with confidence badge from 22-02
provides:
  - Advisory prefix '[AI Advisory — not a verified fact]' injected into analyst_qa.SYSTEM and triage.SYSTEM
  - Non-dismissable AI Advisory banner on every assistant message in InvestigationView copilot panel
  - Confidence badge rendered for all assistant messages (unknown if no score)
  - AI response text styled with italic + muted colour (.ai-content class)
  - test_advisory.py skip decorators removed; 2 passing eval tests for P22-T05
affects: [backend/api/query.py, InvestigationView copilot panel rendering]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Advisory prefix pattern: LLM system prompts begin with '[AI Advisory — not a verified fact]' per NIST AI RMF requirements"
    - "Non-dismissable UI banner: advisory div has no onclick/close button — enforced by code pattern"
    - "TEMPLATE_SHA256 auto-recomputes by hashing module file — changing SYSTEM automatically updates provenance fingerprint"

key-files:
  created: []
  modified:
    - prompts/analyst_qa.py
    - prompts/triage.py
    - dashboard/src/views/InvestigationView.svelte
    - tests/eval/test_advisory.py

key-decisions:
  - "Advisory prefix placed at top of SYSTEM string so every LLM call inherits the framing — no API changes needed"
  - "Streaming block receives confidence-unknown badge with 'Generating...' label until response completes"
  - "Pre-existing TestDetectEndpoint 401 failure is out-of-scope (auth enforcement added in earlier phase, not caused by this plan)"

patterns-established:
  - "AI advisory banner pattern: .ai-advisory-banner with amber border-left, .advisory-label uppercase, .confidence-badge for level — reuse for any future AI output panels"
  - ".ai-content class: italic + var(--text-muted) colour for all AI-generated text — visually distinct from user messages"

requirements-completed: [P22-T05]

# Metrics
duration: 3min
completed: 2026-04-02
---

# Phase 22 Plan 05: AI Advisory Framing Summary

**NIST AI RMF advisory prefix injected into analyst_qa + triage SYSTEM prompts; non-dismissable amber banner + confidence badge on every copilot assistant message in InvestigationView**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-02T16:35:37Z
- **Completed:** 2026-04-02T16:37:43Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Both `analyst_qa.SYSTEM` and `triage.SYSTEM` now start with `[AI Advisory — not a verified fact]` prefix with "Prefix uncertain claims with Possible:/Unverified:" instruction
- TEMPLATE_SHA256 automatically recomputed (module hashes its own source on import)
- InvestigationView copilot panel replaced `ai-advisory-inline` partial implementation with full `ai-advisory-banner` structure — amber left-border, bold uppercase "AI Advisory" label, confidence badge (high/medium/low/unknown), always present, no dismiss button
- AI response paragraph styled with `.ai-content` (italic, muted colour) to visually distinguish from user messages
- Streaming block also shows advisory banner with "Generating..." badge during live token delivery
- `test_advisory.py` skip decorators removed; both tests implemented and passing (2/2 green)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add advisory prefix to analyst_qa.py and triage.py** - `444e715` (feat)
2. **Task 2: Advisory banner + confidence badge + test activation** - `0f3984e` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `prompts/analyst_qa.py` - SYSTEM prefixed with advisory text; TEMPLATE_SHA256 auto-recomputed
- `prompts/triage.py` - SYSTEM prefixed with advisory text; TEMPLATE_SHA256 auto-recomputed
- `dashboard/src/views/InvestigationView.svelte` - Non-dismissable AI Advisory banner + confidence badge + italic ai-content style
- `tests/eval/test_advisory.py` - Skip decorators removed; 2 passing tests for P22-T05

## Decisions Made
- Advisory prefix placed at the top of SYSTEM so all LLM calls inherit advisory framing without API changes
- Streaming message shows `confidence-unknown` badge with label "Generating..." until final message is committed to chatMessages state
- Pre-existing `TestDetectEndpoint` 401 failure is out of scope — it was failing before this plan's changes (confirmed via git stash verify)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Advisory framing fully wired: prompts, UI, and tests all aligned
- P22-T05 requirement satisfied
- Ready for Phase 22 plan 06 (if any) or phase completion

---
*Phase: 22-ai-lifecycle-hardening*
*Completed: 2026-04-02*
