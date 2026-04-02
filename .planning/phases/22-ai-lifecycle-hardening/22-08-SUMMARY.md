---
phase: 22-ai-lifecycle-hardening
plan: "08"
subsystem: api
tags: [fastapi, pydantic, provenance, copilot, trust-signals]

# Dependency graph
requires:
  - phase: 22-ai-lifecycle-hardening
    provides: llm_audit_provenance table with confidence_score column (P22-T02 migration)
provides:
  - GET /api/provenance/copilot/response/{audit_id} endpoint returning CopilotResponseRecord
  - CopilotResponseRecord pydantic model with grounding trust signals
affects:
  - dashboard (UI copilot trust display)
  - api consumers auditing AI responses

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Derive is_grounded boolean from non-empty grounding_event_ids list at serialization time"
    - "Reuse existing get_llm_provenance store method for new caller-facing endpoint"

key-files:
  created: []
  modified:
    - backend/models/provenance.py
    - backend/api/provenance.py

key-decisions:
  - "22-08: response_text not exposed — CopilotResponseRecord surfaces trust signals only (grounding_event_ids, confidence_score, is_grounded) per privacy/storage design"
  - "22-08: is_grounded derived inline (len(grounding_ids) > 0) rather than stored — derived field keeps DB schema minimal"
  - "22-08: Reuses get_llm_provenance store method — avoids duplicate DB query logic"

patterns-established:
  - "Caller-facing trust record pattern: separate model from internal LlmProvenanceRecord to expose only UI/audit-relevant fields"

requirements-completed:
  - P22-T01

# Metrics
duration: 1min
completed: "2026-04-02"
---

# Phase 22 Plan 08: Copilot Response Trust Endpoint Summary

**GET /api/provenance/copilot/response/{audit_id} endpoint returning CopilotResponseRecord with grounding_event_ids, confidence_score, and derived is_grounded trust signals**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-02T17:38:13Z
- **Completed:** 2026-04-02T17:39:13Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added CopilotResponseRecord pydantic model with caller-facing trust signals (grounding_event_ids, confidence_score, is_grounded, prompt_template_name, operator_id)
- Added GET /api/provenance/copilot/response/{audit_id} endpoint that reuses get_llm_provenance store method and derives is_grounded at response time
- All 18 eval tests continue to pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add CopilotResponseRecord model** - `cb52a8c` (feat)
2. **Task 2: Add GET /api/copilot/response/{audit_id} endpoint** - `622ba63` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/models/provenance.py` - Added CopilotResponseRecord model appended after PlaybookProvenanceRecord
- `backend/api/provenance.py` - Added CopilotResponseRecord import and get_copilot_response endpoint

## Decisions Made

- response_text not stored or exposed — CopilotResponseRecord surfaces trust signals only per the plan's privacy/storage design decision
- is_grounded derived at serialization time (len(grounding_ids) > 0) rather than persisted — keeps DB schema minimal
- Reuses existing get_llm_provenance store method to avoid duplicate DB query logic

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Copilot trust record endpoint ready for UI consumption
- Dashboard can call GET /api/provenance/copilot/response/{audit_id} to display confidence scores and grounding status alongside AI responses

---
*Phase: 22-ai-lifecycle-hardening*
*Completed: 2026-04-02*
