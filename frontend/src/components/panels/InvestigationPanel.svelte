<script lang="ts">
  import {
    getAttackGraph,
    getInvestigationSummary,
    type MitreTechnique,
    type InvestigationSummaryResponse,
  } from '../../lib/api'

  // Single $props() call with all props merged (Svelte 5 — $props() called once per component)
  let { alertId, score, techniques, firstEvent, lastEvent, onFilterApplied } = $props<{
    alertId: string
    score: number
    techniques: MitreTechnique[]
    firstEvent: string
    lastEvent: string
    onFilterApplied?: (range: { from: string; to: string }) => void
  }>()

  let summary = $state<InvestigationSummaryResponse | null>(null)
  let summaryLoading = $state(false)
  let summaryError = $state<string | null>(null)

  // Timeline filter state (locked dashboard capability: "Support timeline filtering")
  let timeFrom = $state('')
  let timeTo = $state('')
  let filterLoading = $state(false)
  let filterError = $state<string | null>(null)

  async function generateSummary() {
    if (!alertId || summaryLoading) return
    summaryLoading = true
    summaryError = null
    try {
      summary = await getInvestigationSummary(alertId)
    } catch (err) {
      summaryError = err instanceof Error ? err.message : 'Failed to generate summary'
    } finally {
      summaryLoading = false
    }
  }

  async function applyTimeFilter() {
    if (!alertId || filterLoading) return
    filterLoading = true
    filterError = null
    try {
      // Re-fetch graph with time bounds; result is emitted via onFilterApplied callback
      // The ?from/to params are passed — backend will honor them once implemented
      await getAttackGraph(alertId, {
        from: timeFrom || undefined,
        to: timeTo || undefined,
      })
      // Notify parent so it can refresh AttackChain.svelte with the filtered view
      onFilterApplied?.({ from: timeFrom, to: timeTo })
    } catch (err) {
      filterError = err instanceof Error ? err.message : 'Failed to apply filter'
    } finally {
      filterLoading = false
    }
  }

  function clearTimeFilter() {
    timeFrom = ''
    timeTo = ''
    filterError = null
    onFilterApplied?.({ from: '', to: '' })
  }

  function scoreBadgeColor(s: number): string {
    if (s > 60) return '#ef4444'  // red
    if (s >= 30) return '#f59e0b' // yellow
    return '#22c55e'              // green
  }
</script>

<div class="investigation-panel">
  <header class="panel-header">
    <h3>Investigation</h3>
    <span class="score-badge" style="background-color: {scoreBadgeColor(score)}">
      Score: {score}
    </span>
  </header>

  <!-- Timeline range display -->
  {#if firstEvent || lastEvent}
    <div class="time-range">
      <span class="label">Event range:</span>
      <span>{firstEvent || '—'} to {lastEvent || '—'}</span>
    </div>
  {/if}

  <!-- Timeline filter inputs (locked: "Support timeline filtering") -->
  <section class="timeline-filter">
    <h4>Timeline Filter</h4>
    <div class="filter-row">
      <label class="filter-label" for="timeFrom">From</label>
      <input
        id="timeFrom"
        type="datetime-local"
        class="filter-input"
        bind:value={timeFrom}
      />
    </div>
    <div class="filter-row">
      <label class="filter-label" for="timeTo">To</label>
      <input
        id="timeTo"
        type="datetime-local"
        class="filter-input"
        bind:value={timeTo}
      />
    </div>
    {#if filterError}
      <p class="error">{filterError}</p>
    {/if}
    <div class="filter-actions">
      <button
        class="filter-btn"
        onclick={applyTimeFilter}
        disabled={filterLoading || (!timeFrom && !timeTo)}
      >
        {filterLoading ? 'Applying...' : 'Apply Filter'}
      </button>
      {#if timeFrom || timeTo}
        <button class="clear-btn" onclick={clearTimeFilter}>Clear</button>
      {/if}
    </div>
  </section>

  {#if techniques.length > 0}
    <section class="techniques">
      <h4>MITRE ATT&amp;CK Techniques</h4>
      <ul>
        {#each techniques as t}
          <li class="technique-item">
            <span class="technique-id">{t.technique}</span>
            <span class="technique-name">{t.name}</span>
            <span class="tactic-badge">{t.tactic}</span>
          </li>
        {/each}
      </ul>
    </section>
  {:else}
    <p class="muted">No MITRE techniques identified.</p>
  {/if}

  <section class="ai-summary">
    <h4>AI Investigation Summary</h4>
    {#if summary}
      <div class="summary-text">{summary.summary}</div>
    {:else if summaryLoading}
      <p class="muted">Generating summary...</p>
    {:else if summaryError}
      <p class="error">{summaryError}</p>
    {:else}
      <p class="muted">Click below to generate an AI-assisted summary.</p>
    {/if}
    <button
      class="generate-btn"
      onclick={generateSummary}
      disabled={summaryLoading}
    >
      {summaryLoading ? 'Generating...' : 'Generate Summary'}
    </button>
  </section>
</div>

<style>
  .investigation-panel {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 16px;
    background: #161b22;
    color: #e5e7eb;
    height: 100%;
    overflow-y: auto;
    font-size: 13px;
  }
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .panel-header h3 { margin: 0; font-size: 15px; }
  .score-badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: bold;
    font-size: 12px;
    color: #fff;
  }
  .time-range { color: #9ca3af; font-size: 12px; }
  .label { color: #6b7280; margin-right: 4px; }
  h4 { font-size: 13px; color: #9ca3af; margin: 0 0 8px; }
  .timeline-filter {
    background: #0d1117;
    border: 1px solid #1f2937;
    border-radius: 6px;
    padding: 12px;
  }
  .filter-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }
  .filter-label {
    width: 32px;
    color: #6b7280;
    font-size: 12px;
    flex-shrink: 0;
  }
  .filter-input {
    flex: 1;
    background: #161b22;
    border: 1px solid #374151;
    border-radius: 4px;
    color: #e5e7eb;
    font-size: 12px;
    padding: 4px 8px;
  }
  .filter-input:focus { outline: none; border-color: #3b82f6; }
  .filter-actions { display: flex; gap: 8px; margin-top: 4px; }
  .filter-btn {
    padding: 4px 12px;
    background: #1d4ed8;
    color: #fff;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
  }
  .filter-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .filter-btn:hover:not(:disabled) { background: #2563eb; }
  .clear-btn {
    padding: 4px 10px;
    background: transparent;
    color: #9ca3af;
    border: 1px solid #374151;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
  }
  .clear-btn:hover { border-color: #6b7280; color: #e5e7eb; }
  .technique-item {
    display: flex;
    gap: 8px;
    align-items: center;
    padding: 4px 0;
    border-bottom: 1px solid #1f2937;
    list-style: none;
  }
  .technique-id { font-family: monospace; color: #60a5fa; font-size: 12px; }
  .technique-name { flex: 1; }
  .tactic-badge {
    font-size: 11px;
    padding: 1px 6px;
    background: #1f2937;
    border-radius: 3px;
    color: #9ca3af;
  }
  ul { margin: 0; padding: 0; }
  .muted { color: #6b7280; font-style: italic; }
  .error { color: #ef4444; }
  .summary-text {
    white-space: pre-wrap;
    line-height: 1.5;
    color: #d1d5db;
    margin-bottom: 12px;
  }
  .generate-btn {
    padding: 6px 14px;
    background: #1d4ed8;
    color: #fff;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
  }
  .generate-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .generate-btn:hover:not(:disabled) { background: #2563eb; }
</style>
