<script lang="ts">
  import { api } from '../lib/api.ts'
  import type { Playbook, PlaybookRun } from '../lib/api.ts'

  let {
    investigationId = '',
  }: {
    investigationId?: string
  } = $props()

  // --- Library mode state ---
  let playbooks = $state<Playbook[]>([])
  let loadingLibrary = $state(false)
  let libraryError = $state('')

  // --- Execution mode state ---
  let activeRun = $state<PlaybookRun | null>(null)
  let activePlaybook = $state<Playbook | null>(null)
  let stepNote = $state('')
  let isSubmitting = $state(false)
  let errorMsg = $state('')

  const currentStepNumber = $derived(
    activeRun && activePlaybook
      ? (activeRun.steps_completed.length + 1)
      : 0
  )

  // Load playbooks on mount
  $effect(() => {
    loadLibrary()
  })

  async function loadLibrary() {
    loadingLibrary = true
    libraryError = ''
    try {
      const res = await api.playbooks.list()
      playbooks = res.playbooks
    } catch (e: any) {
      libraryError = e.message
    } finally {
      loadingLibrary = false
    }
  }

  async function startRun(playbook: Playbook) {
    if (!investigationId) return
    errorMsg = ''
    try {
      const run = await api.playbooks.startRun(playbook.playbook_id, investigationId)
      activeRun = run
      activePlaybook = playbook
      stepNote = ''
    } catch (e: any) {
      errorMsg = e.message
    }
  }

  async function advanceStep(outcome: 'confirmed' | 'skipped') {
    if (!activeRun || isSubmitting) return
    isSubmitting = true
    errorMsg = ''
    try {
      const updated = await api.playbookRuns.advanceStep(
        activeRun.run_id,
        currentStepNumber,
        { analyst_note: stepNote, outcome }
      )
      activeRun = updated
      stepNote = ''
    } catch (e: any) {
      errorMsg = e.message
    } finally {
      isSubmitting = false
    }
  }

  async function cancelRun() {
    if (!activeRun) return
    errorMsg = ''
    try {
      const updated = await api.playbookRuns.cancel(activeRun.run_id)
      activeRun = updated
    } catch (e: any) {
      errorMsg = e.message
    }
  }

  function backToLibrary() {
    activeRun = null
    activePlaybook = null
    stepNote = ''
    errorMsg = ''
  }

  function fmtTs(ts: string): string {
    try { return new Date(ts).toLocaleString() }
    catch { return ts }
  }

  function stepCircleStyle(stepNum: number): string {
    if (!activeRun) return 'background:#2d3a52;color:#8899aa;border-color:#3d4a62'
    const done = activeRun.steps_completed.find(s => s.step_number === stepNum)
    if (done) return 'background:#166534;color:#4ade80;border-color:#16a34a'
    if (stepNum === currentStepNumber && activeRun.status === 'running')
      return 'background:#78350f;color:#fbbf24;border-color:#d97706'
    return 'background:#2d3a52;color:#8899aa;border-color:#3d4a62'
  }
</script>

<div class="view">

  <!-- ========================================================
       VIEW HEADER
       ======================================================== -->
  <div class="view-header">
    <div class="header-left">
      <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style="color:#34d399">
        <rect x="3" y="2" width="10" height="12" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
        <line x1="6" y1="6" x2="10" y2="6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="6" y1="9" x2="9" y2="9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
      </svg>
      {#if activeRun && activePlaybook}
        <h1>{activePlaybook.name}</h1>
        <span class="run-status status-{activeRun.status}">{activeRun.status.toUpperCase()}</span>
      {:else}
        <h1>Playbooks / SOAR</h1>
      {/if}
    </div>

    <div class="header-right">
      {#if activeRun && activePlaybook}
        {#if activeRun.status === 'running'}
          <button class="btn-danger" onclick={cancelRun}>Cancel Run</button>
        {/if}
        <button class="btn-secondary" onclick={backToLibrary}>Back to Library</button>
      {:else}
        {#if investigationId}
          <span class="context-badge">Investigation: {investigationId.slice(0, 8)}…</span>
        {:else}
          <span class="context-badge muted-badge">No investigation selected</span>
        {/if}
      {/if}
    </div>
  </div>

  <!-- ========================================================
       ERROR BANNER
       ======================================================== -->
  {#if errorMsg}
    <div class="error-banner">{errorMsg}</div>
  {/if}

  <!-- ========================================================
       MODE A — LIBRARY BROWSER
       ======================================================== -->
  {#if !activeRun}
    <div class="content">
      {#if loadingLibrary}
        <p class="muted">Loading playbooks…</p>
      {:else if libraryError}
        <p class="error-text">{libraryError}</p>
      {:else if playbooks.length === 0}
        <p class="muted">No playbooks found.</p>
      {:else}
        <div class="playbook-list">
          {#each playbooks as pb (pb.playbook_id)}
            <div class="pb-card">
              <div class="pb-top">
                <div class="pb-left">
                  <span class="pb-name">{pb.name}</span>
                  <span class="pb-version">v{pb.version}{pb.is_builtin ? ' · Built-in' : ''}</span>
                  <p class="pb-desc">{pb.description}</p>
                  <div class="pb-triggers">
                    {#each pb.trigger_conditions as tc}
                      <span class="trigger-tag">{tc}</span>
                    {/each}
                  </div>
                </div>
                <div class="pb-meta">
                  <span class="step-count">{pb.steps.length} steps</span>
                </div>
              </div>

              <div class="pb-actions">
                <button
                  class="btn-run"
                  disabled={!investigationId}
                  title={!investigationId ? 'Select an investigation first' : `Run ${pb.name}`}
                  onclick={() => startRun(pb)}
                >
                  Run Playbook
                </button>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>

  <!-- ========================================================
       MODE B — EXECUTION VIEW
       ======================================================== -->
  {:else}
    <div class="content">

      {#if activeRun.status === 'completed'}
        <div class="completed-banner">Run Completed — all {activePlaybook?.steps.length} steps finished</div>
      {:else if activeRun.status === 'cancelled'}
        <div class="cancelled-banner">Run Cancelled</div>
      {/if}

      <div class="step-list">
        {#each (activePlaybook?.steps ?? []) as step (step.step_number)}
          {@const result = activeRun.steps_completed.find(s => s.step_number === step.step_number)}
          {@const isCurrent = step.step_number === currentStepNumber && activeRun.status === 'running'}

          <div class="step-row {result ? 'done' : isCurrent ? 'current' : 'future'}">
            <div class="step-circle" style={stepCircleStyle(step.step_number)}>
              {#if result}
                &#10003;
              {:else}
                {step.step_number}
              {/if}
            </div>

            <div class="step-body">
              <div class="step-header-row">
                <span class="step-title">{step.title}</span>
                {#if result}
                  <span class="outcome-badge outcome-{result.outcome}">{result.outcome.toUpperCase()}</span>
                {/if}
              </div>

              <p class="step-desc">{step.description}</p>

              {#if step.evidence_prompt}
                <p class="evidence-hint"><em>Evidence hint: {step.evidence_prompt}</em></p>
              {/if}

              {#if result}
                <!-- Completed step audit trail -->
                {#if result.analyst_note}
                  <p class="audit-note">Note: {result.analyst_note}</p>
                {/if}
                <p class="audit-ts">{fmtTs(result.completed_at)}</p>
              {:else if isCurrent}
                <!-- Active step controls -->
                <textarea
                  class="step-note-input"
                  placeholder="Analyst note (optional)…"
                  rows="2"
                  bind:value={stepNote}
                  disabled={isSubmitting}
                ></textarea>
                <div class="step-btns">
                  <button
                    class="btn-confirm"
                    disabled={isSubmitting}
                    onclick={() => advanceStep('confirmed')}
                  >
                    Confirm
                  </button>
                  <button
                    class="btn-skip"
                    disabled={isSubmitting}
                    onclick={() => advanceStep('skipped')}
                  >
                    Skip
                  </button>
                </div>
              {/if}
            </div>
          </div>
        {/each}
      </div>

    </div>
  {/if}

</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

  /* Header */
  .view-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 20px; border-bottom: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0; gap: 12px;
  }
  .header-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .header-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  h1 { font-size: 15px; font-weight: 600; margin: 0; white-space: nowrap; }

  .run-status {
    font-size: 10px; font-weight: 700; letter-spacing: 0.6px;
    padding: 2px 8px; border-radius: 10px;
  }
  .status-running  { color: #fbbf24; background: rgba(251,191,36,0.12); border: 1px solid rgba(251,191,36,0.3); }
  .status-completed { color: #4ade80; background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3); }
  .status-cancelled { color: #f87171; background: rgba(248,113,113,0.12); border: 1px solid rgba(248,113,113,0.3); }

  .context-badge {
    font-size: 11px; color: var(--text-secondary);
    background: var(--bg-tertiary); border: 1px solid var(--border);
    padding: 3px 10px; border-radius: 10px;
  }
  .muted-badge { opacity: 0.6; }

  /* Error banner */
  .error-banner {
    background: rgba(248,113,113,0.1); border-bottom: 1px solid rgba(248,113,113,0.3);
    color: #f87171; font-size: 12px; padding: 8px 20px; flex-shrink: 0;
  }

  /* Content area */
  .content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 14px; }

  /* Library list */
  .playbook-list { display: flex; flex-direction: column; gap: 10px; }

  .pb-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-md); padding: 16px;
    display: flex; flex-direction: column; gap: 12px;
  }
  .pb-top { display: flex; align-items: flex-start; gap: 12px; }
  .pb-left { flex: 1; display: flex; flex-direction: column; gap: 4px; }
  .pb-meta { flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
  .pb-name { font-size: 14px; font-weight: 600; }
  .pb-version { font-size: 11px; color: var(--text-secondary); }
  .pb-desc { font-size: 12px; color: var(--text-secondary); margin: 2px 0; line-height: 1.5; }
  .step-count {
    font-size: 11px; font-weight: 600; color: var(--accent-green);
    background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.25);
    padding: 2px 8px; border-radius: 10px; white-space: nowrap;
  }
  .pb-triggers { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 4px; }
  .trigger-tag {
    font-size: 10px; padding: 2px 7px; border-radius: 10px;
    background: rgba(99,102,241,0.1); color: #818cf8;
    border: 1px solid rgba(99,102,241,0.2);
  }
  .pb-actions { display: flex; gap: 8px; }

  /* Buttons */
  .btn-run {
    font-size: 12px; padding: 6px 16px;
    background: rgba(34,197,94,0.1); color: var(--accent-green);
    border: 1px solid rgba(34,197,94,0.35); border-radius: var(--radius-md);
    cursor: pointer; font-family: var(--font-sans);
    transition: background 0.15s;
  }
  .btn-run:hover:not(:disabled) { background: rgba(34,197,94,0.18); }
  .btn-run:disabled { opacity: 0.4; cursor: not-allowed; }

  .btn-secondary {
    font-size: 12px; padding: 5px 14px;
    background: transparent; color: var(--text-secondary);
    border: 1px solid var(--border); border-radius: var(--radius-md);
    cursor: pointer; font-family: var(--font-sans);
  }
  .btn-secondary:hover { background: var(--bg-tertiary); }

  .btn-danger {
    font-size: 12px; padding: 5px 14px;
    background: rgba(248,113,113,0.1); color: #f87171;
    border: 1px solid rgba(248,113,113,0.3); border-radius: var(--radius-md);
    cursor: pointer; font-family: var(--font-sans);
  }
  .btn-danger:hover { background: rgba(248,113,113,0.18); }

  /* Execution mode */
  .completed-banner {
    background: rgba(74,222,128,0.1); border: 1px solid rgba(74,222,128,0.3);
    color: #4ade80; font-size: 13px; font-weight: 600;
    padding: 10px 16px; border-radius: var(--radius-md); text-align: center;
    flex-shrink: 0;
  }
  .cancelled-banner {
    background: rgba(248,113,113,0.1); border: 1px solid rgba(248,113,113,0.3);
    color: #f87171; font-size: 13px; font-weight: 600;
    padding: 10px 16px; border-radius: var(--radius-md); text-align: center;
    flex-shrink: 0;
  }

  .step-list { display: flex; flex-direction: column; gap: 8px; }

  .step-row {
    display: flex; gap: 14px; align-items: flex-start;
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-md); padding: 14px;
  }
  .step-row.current { border-color: rgba(251,191,36,0.3); background: rgba(251,191,36,0.03); }
  .step-row.done    { opacity: 0.85; }

  .step-circle {
    width: 28px; height: 28px; border-radius: 50%;
    border: 2px solid; display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; flex-shrink: 0; margin-top: 2px;
  }

  .step-body { flex: 1; display: flex; flex-direction: column; gap: 6px; }

  .step-header-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .step-title { font-size: 13px; font-weight: 600; }

  .outcome-badge {
    font-size: 10px; font-weight: 700; letter-spacing: 0.5px;
    padding: 2px 7px; border-radius: 10px;
  }
  .outcome-confirmed { color: #4ade80; background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3); }
  .outcome-skipped   { color: #94a3b8; background: rgba(148,163,184,0.12); border: 1px solid rgba(148,163,184,0.3); }

  .step-desc { font-size: 12px; color: var(--text-secondary); margin: 0; line-height: 1.5; }
  .evidence-hint { font-size: 11px; color: var(--text-secondary); margin: 0; opacity: 0.8; }

  .audit-note { font-size: 12px; color: var(--text-secondary); margin: 0; }
  .audit-ts   { font-size: 10px; color: var(--text-muted, #64748b); margin: 0; }

  .step-note-input {
    width: 100%; box-sizing: border-box;
    background: var(--bg-tertiary, #1e293b); border: 1px solid var(--border);
    border-radius: var(--radius-md); color: inherit; padding: 7px 10px;
    font-size: 12px; font-family: var(--font-sans); resize: none;
  }
  .step-note-input:disabled { opacity: 0.5; }

  .step-btns { display: flex; gap: 8px; }

  .btn-confirm {
    font-size: 12px; padding: 5px 16px;
    background: rgba(34,197,94,0.1); color: #4ade80;
    border: 1px solid rgba(34,197,94,0.3); border-radius: var(--radius-md);
    cursor: pointer; font-family: var(--font-sans);
  }
  .btn-confirm:hover:not(:disabled) { background: rgba(34,197,94,0.18); }
  .btn-confirm:disabled { opacity: 0.4; cursor: not-allowed; }

  .btn-skip {
    font-size: 12px; padding: 5px 16px;
    background: rgba(148,163,184,0.08); color: #94a3b8;
    border: 1px solid rgba(148,163,184,0.25); border-radius: var(--radius-md);
    cursor: pointer; font-family: var(--font-sans);
  }
  .btn-skip:hover:not(:disabled) { background: rgba(148,163,184,0.14); }
  .btn-skip:disabled { opacity: 0.4; cursor: not-allowed; }

  .muted { color: var(--text-secondary); font-size: 13px; padding: 20px; text-align: center; }
  .error-text { color: #f87171; font-size: 13px; padding: 1rem; }
</style>
