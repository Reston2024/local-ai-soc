---
phase: 54-hf-model-integration
plan: "02"
subsystem: infra
tags: [ollama, gpu, vulkan, rtx5080, blackwell, cuda, windows]

# Dependency graph
requires:
  - phase: 54-01
    provides: Wave-0 test stubs and config additions for HF model integration
provides:
  - Ollama GPU acceleration via Vulkan backend (RTX 5080 confirmed 11%/89% CPU/GPU split)
  - OLLAMA_VULKAN=true set at Machine scope (permanent, survives reboots)
  - Pre-flight GPU advisory warning in _start-backend.ps1
affects:
  - 54-03
  - 54-04
  - 54-05
  - All subsequent plans dependent on sub-30s LLM inference TTFT

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Vulkan-first GPU path for Blackwell-generation NVIDIA GPUs (sm_120) where CUDA runtime lags"
    - "Machine-scope env vars for Ollama Windows service (user-scope vars not inherited by services)"
    - "Pre-flight advisory check pattern in startup scripts (non-fatal warn, never blocks launch)"

key-files:
  created: []
  modified:
    - scripts/_start-backend.ps1

key-decisions:
  - "CUDA_VISIBLE_DEVICES was NOT set at Machine scope — it was the root cause of GPU discovery failure (setting =0 blocks Vulkan enumeration)"
  - "OLLAMA_VULKAN=true at Machine scope is the correct fix for RTX 5080 (Blackwell sm_120 not in Ollama bundled CUDA runtime)"
  - "Pre-flight warning references 54-02-PLAN.md for remediation steps rather than embedding full instructions"
  - "Warning is advisory-only (try/catch, non-fatal) — slow inference never blocks backend launch"

patterns-established:
  - "Vulkan workaround pattern: for NVIDIA Blackwell GPUs, set OLLAMA_VULKAN=true + leave CUDA_VISIBLE_DEVICES unset"

requirements-completed:
  - REQ-54-01

# Metrics
duration: manual (human-executed)
completed: 2026-04-16
---

# Phase 54 Plan 02: Ollama GPU Migration Summary

**RTX 5080 GPU acceleration achieved via Vulkan backend (OLLAMA_VULKAN=true) after diagnosing Blackwell sm_120 CUDA gap — ollama ps confirms 11%/89% CPU/GPU split**

## Performance

- **Duration:** Manual (human-executed over multiple sessions)
- **Started:** 2026-04-16
- **Completed:** 2026-04-16
- **Tasks:** 4 (Tasks 1-3 manual, Task 4 automated)
- **Files modified:** 1 (scripts/_start-backend.ps1)

## Accomplishments

- Identified root cause: `CUDA_VISIBLE_DEVICES=0` set at Machine scope was blocking Vulkan GPU enumeration entirely
- Unset `CUDA_VISIBLE_DEVICES` at all scopes (Machine, User, Process) to restore default GPU discovery
- Set `OLLAMA_VULKAN=true` at Machine scope — Vulkan backend (`vulkan/ggml-vulkan.dll`) is present in Ollama install and supports RTX 5080
- Confirmed GPU acceleration: `ollama ps` shows 11% CPU / 89% GPU during inference, unlocking sub-30s TTFT for all subsequent HF model plans
- Added pre-flight GPU advisory warning block to `scripts/_start-backend.ps1` (commit 339c4c4)

## Task Commits

1. **Task 4: Pre-flight GPU warning in _start-backend.ps1** - `339c4c4` (feat)

Tasks 1-3 were manual Windows system configuration steps (no code commits).

## Files Created/Modified

- `scripts/_start-backend.ps1` - Added pre-flight GPU check block: calls `ollama ps`, parses GPU Layers value, emits yellow WARNING if CPU-only mode detected (advisory, non-fatal)

## Decisions Made

**Root cause was CUDA_VISIBLE_DEVICES, not CUDA itself:**
The original plan spec called for setting `CUDA_VISIBLE_DEVICES=0` at Machine scope to enable GPU. In practice this was the opposite of the fix needed — the variable was already set (incorrectly) and was blocking Vulkan discovery. Unsetting it was the correct action.

**Vulkan over CUDA for Blackwell:**
RTX 5080 uses the Blackwell architecture (sm_120). Ollama's bundled CUDA runtime does not yet include sm_120 support. The Vulkan backend (`vulkan/ggml-vulkan.dll`) ships with Ollama and has no such architecture constraint. Setting `OLLAMA_VULKAN=true` at Machine scope routes all inference through Vulkan.

**Machine scope required for Windows services:**
The Ollama process runs as a Windows service and does not inherit User-scope environment variables. Machine-scope env vars (`[System.Environment]::SetEnvironmentVariable(..., "Machine")`) are read by the service on startup.

## Deviations from Plan

### Approach Change (human-resolved)

**Original plan objective vs actual fix:**
- **Plan specified:** Set `CUDA_VISIBLE_DEVICES=0` at Machine scope to route Ollama to the RTX 5080 via CUDA
- **Actual diagnosis:** `CUDA_VISIBLE_DEVICES` was already set (to "0") and was the blocking variable — it prevented Vulkan GPU discovery. Unsetting it was step one.
- **Actual fix:** `OLLAMA_VULKAN=true` at Machine scope + unset `CUDA_VISIBLE_DEVICES` at all scopes
- **Why:** RTX 5080 (Blackwell sm_120) is not supported by Ollama's bundled CUDA runtime. Vulkan backend is present and fully functional for this GPU generation.
- **Outcome:** GPU confirmed working (11%/89% CPU/GPU split in `ollama ps`)

This was a human-resolved deviation during the manual tasks (Tasks 1-3). The automated Task 4 (pre-flight warning script) was executed as planned.

---

**Total deviations:** 1 (human-resolved architectural diagnosis during manual GPU migration)
**Impact on plan:** Deviation was necessary — CUDA path is not available for Blackwell GPUs. Vulkan path achieves identical outcome (GPU acceleration). All subsequent plans unblocked.

## Issues Encountered

**CUDA runtime gap for Blackwell (sm_120):**
Ollama's bundled CUDA DLLs target older NVIDIA compute capabilities. RTX 5080 uses sm_120 (Blackwell) which was not in the bundled runtime at time of execution. The Vulkan backend is architecture-agnostic and worked immediately after `OLLAMA_VULKAN=true` was set.

**CUDA_VISIBLE_DEVICES was a pre-existing incorrect setting:**
Someone (or a prior install) had set `CUDA_VISIBLE_DEVICES=0` at Machine scope. With CUDA unavailable for sm_120, this variable had the side effect of disabling Vulkan enumeration as well, leaving Ollama fully CPU-bound.

## User Setup Required

The following environment variable is now set at Windows Machine scope:
- `OLLAMA_VULKAN=true` — routes Ollama inference to RTX 5080 via Vulkan backend

`CUDA_VISIBLE_DEVICES` was cleared at Machine, User, and Process scope.

To verify GPU is still active after any Ollama reinstall:
```powershell
ollama run qwen3:14b "test" ; ollama ps
# Should show 11%/89% or similar CPU/GPU ratio
```

## Next Phase Readiness

- GPU acceleration confirmed — inference TTFT is now sub-30s (was ~300s on CPU)
- 54-03 (bge-m3 embedding model integration) is unblocked; GPU will accelerate embedding generation
- 54-04 through 54-10 all benefit from GPU acceleration
- The Vulkan workaround is stable and survives reboots (Machine scope env var)

---
*Phase: 54-hf-model-integration*
*Completed: 2026-04-16*
