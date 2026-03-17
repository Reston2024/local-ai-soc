<script lang="ts">
  import { getCases, createCase, getCase, patchCase, getCaseTimeline } from '$lib/api'
  import type { CaseItem, TimelineEntry } from '$lib/api'

  let cases = $state<CaseItem[]>([])
  let selectedCase = $state<CaseItem | null>(null)
  let timeline = $state<TimelineEntry[]>([])
  let loading = $state(false)
  let creating = $state(false)
  let newCaseTitle = $state('')
  let error = $state<string | null>(null)

  $effect(() => {
    loadCases()
  })

  async function loadCases() {
    loading = true
    error = null
    try {
      const data = await getCases()
      cases = data.cases
    } catch (e) {
      error = 'Failed to load cases'
    } finally {
      loading = false
    }
  }

  async function selectCase(caseId: string) {
    selectedCase = null
    timeline = []
    try {
      const [detail, tl] = await Promise.all([
        getCase(caseId),
        getCaseTimeline(caseId),
      ])
      selectedCase = detail
      timeline = tl.timeline
    } catch (e) {
      error = 'Failed to load case detail'
    }
  }

  async function handleCreateCase() {
    if (!newCaseTitle.trim()) return
    creating = true
    try {
      await createCase(newCaseTitle.trim())
      newCaseTitle = ''
      await loadCases()
    } catch (e) {
      error = 'Failed to create case'
    } finally {
      creating = false
    }
  }

  async function closeCase(caseId: string) {
    await patchCase(caseId, { case_status: 'closed' })
    await loadCases()
    if (selectedCase?.case_id === caseId) selectedCase = null
  }

  const statusColor = $derived((status: string) => {
    if (status === 'open') return '#22c55e'
    if (status === 'in-progress') return '#f59e0b'
    if (status === 'closed') return '#6b7280'
    return '#94a3b8'
  })
</script>

<div class="case-panel">
  <header>
    <h2>Investigation Cases</h2>
    <div class="create-row">
      <input
        type="text"
        placeholder="New case title..."
        bind:value={newCaseTitle}
        onkeydown={(e) => e.key === 'Enter' && handleCreateCase()}
      />
      <button onclick={handleCreateCase} disabled={creating || !newCaseTitle.trim()}>
        {creating ? 'Creating...' : 'New Case'}
      </button>
    </div>
  </header>

  {#if error}<div class="error">{error}</div>{/if}
  {#if loading}<div class="loading">Loading...</div>{/if}

  <div class="layout">
    <div class="case-list">
      {#each cases as c (c.case_id)}
        <div
          class="case-card"
          class:selected={selectedCase?.case_id === c.case_id}
          onclick={() => selectCase(c.case_id)}
        >
          <span class="status-dot" style="background:{statusColor(c.case_status)}"></span>
          <div class="case-info">
            <strong>{c.title}</strong>
            <small>{c.case_status} · {c.tags.join(', ') || 'no tags'}</small>
          </div>
          <button
            class="close-btn"
            onclick={(e) => { e.stopPropagation(); closeCase(c.case_id) }}
            disabled={c.case_status === 'closed'}
          >Close</button>
        </div>
      {:else}
        <p class="empty">No cases. Create one above.</p>
      {/each}
    </div>

    {#if selectedCase}
      <div class="case-detail">
        <h3>{selectedCase.title}</h3>
        <p>Status: <strong>{selectedCase.case_status}</strong></p>
        <p>Alerts: {selectedCase.related_alerts.length} · Entities: {selectedCase.related_entities.length}</p>
        {#if selectedCase.analyst_notes}
          <p class="notes">{selectedCase.analyst_notes}</p>
        {/if}

        <h4>Timeline ({timeline.length} events)</h4>
        <div class="timeline">
          {#each timeline as entry (entry.timestamp)}
            <div class="timeline-entry" style="opacity:{entry.confidence_score}">
              <span class="ts">{entry.timestamp.replace('T', ' ').slice(0, 19)}</span>
              <span class="src">{entry.event_source}</span>
              <span class="refs">{entry.entity_references.slice(0, 3).join(', ')}</span>
              <span class="conf">{(entry.confidence_score * 100).toFixed(0)}%</span>
            </div>
          {:else}
            <p class="empty">No events in timeline for this case.</p>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .case-panel { display: flex; flex-direction: column; gap: 12px; padding: 16px; }
  header { display: flex; flex-direction: column; gap: 8px; }
  .create-row { display: flex; gap: 8px; }
  .create-row input { flex: 1; padding: 6px 10px; border: 1px solid #334155; background: #1e293b; color: #e2e8f0; border-radius: 4px; }
  .create-row button { padding: 6px 14px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; }
  .create-row button:disabled { opacity: 0.5; cursor: not-allowed; }
  .layout { display: grid; grid-template-columns: 300px 1fr; gap: 16px; }
  .case-list { display: flex; flex-direction: column; gap: 6px; }
  .case-card { display: flex; align-items: center; gap: 8px; padding: 10px; background: #1e293b; border-radius: 6px; cursor: pointer; border: 1px solid transparent; }
  .case-card.selected { border-color: #3b82f6; }
  .case-card:hover { background: #263248; }
  .status-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .case-info { flex: 1; display: flex; flex-direction: column; }
  .case-info strong { font-size: 14px; color: #e2e8f0; }
  .case-info small { font-size: 12px; color: #64748b; }
  .close-btn { padding: 2px 8px; font-size: 12px; background: #374151; color: #9ca3af; border: none; border-radius: 3px; cursor: pointer; }
  .close-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .case-detail { background: #1e293b; border-radius: 8px; padding: 16px; }
  .case-detail h3 { margin: 0 0 8px; color: #e2e8f0; }
  .case-detail h4 { margin: 16px 0 8px; color: #94a3b8; font-size: 13px; text-transform: uppercase; }
  .timeline { display: flex; flex-direction: column; gap: 4px; max-height: 400px; overflow-y: auto; }
  .timeline-entry { display: grid; grid-template-columns: 160px 100px 1fr 50px; gap: 8px; padding: 6px 8px; background: #0f172a; border-radius: 4px; font-size: 12px; font-family: monospace; }
  .ts { color: #64748b; }
  .src { color: #60a5fa; }
  .refs { color: #e2e8f0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .conf { color: #22c55e; text-align: right; }
  .empty { color: #475569; font-style: italic; font-size: 13px; }
  .error { color: #ef4444; font-size: 13px; padding: 6px; background: #1e0a0a; border-radius: 4px; }
  .loading { color: #64748b; font-size: 13px; }
  .notes { color: #94a3b8; font-size: 13px; white-space: pre-wrap; }
</style>
