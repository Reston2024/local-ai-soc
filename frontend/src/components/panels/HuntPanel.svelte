<script lang="ts">
  import { getHuntTemplates, executeHunt, createCase } from '$lib/api'
  import type { HuntTemplate, HuntResult } from '$lib/api'

  let templates = $state<HuntTemplate[]>([])
  let selectedTemplate = $state('')
  let params = $state<Record<string, string>>({})
  let results = $state<HuntResult[]>([])
  let resultCount = $state(0)
  let loading = $state(false)
  let creating = $state(false)
  let error = $state<string | null>(null)
  let success = $state<string | null>(null)

  $effect(() => {
    getHuntTemplates().then(data => {
      templates = data.templates
      if (templates.length > 0) selectedTemplate = templates[0].name
    })
  })

  const currentTemplate = $derived(
    templates.find(t => t.name === selectedTemplate) ?? null
  )

  function handleTemplateChange() {
    params = {}
    results = []
    error = null
  }

  async function runHunt() {
    if (!selectedTemplate) return
    loading = true
    error = null
    results = []
    try {
      const data = await executeHunt(selectedTemplate, params)
      results = data.results
      resultCount = data.result_count
    } catch (e) {
      error = 'Hunt failed'
    } finally {
      loading = false
    }
  }

  async function pivotToCase() {
    if (results.length === 0) return
    creating = true
    success = null
    try {
      const title = `Hunt: ${selectedTemplate} (${resultCount} results)`
      const newCase = await createCase(title, `Pivot from hunt query on template ${selectedTemplate}`)
      success = `Case created: ${newCase.case_id}`
    } catch (e) {
      error = 'Failed to create case'
    } finally {
      creating = false
    }
  }

  const resultColumns = $derived(
    results.length > 0 ? Object.keys(results[0]) : []
  )
</script>

<div class="hunt-panel">
  <header>
    <h2>Threat Hunting</h2>
  </header>

  <div class="controls">
    <label>
      Template
      <select bind:value={selectedTemplate} onchange={handleTemplateChange}>
        {#each templates as t}
          <option value={t.name}>{t.description}</option>
        {/each}
      </select>
    </label>

    {#if currentTemplate && currentTemplate.param_keys.length > 0}
      <div class="params">
        {#each currentTemplate.param_keys as key}
          <label>
            {key}
            <input
              type="text"
              placeholder={key}
              bind:value={params[key]}
            />
          </label>
        {/each}
      </div>
    {/if}

    <button onclick={runHunt} disabled={loading || !selectedTemplate}>
      {loading ? 'Hunting...' : 'Run Hunt'}
    </button>
  </div>

  {#if error}<div class="error">{error}</div>{/if}
  {#if success}<div class="success">{success}</div>{/if}

  {#if results.length > 0}
    <div class="results-header">
      <span>{resultCount} results</span>
      <button class="pivot-btn" onclick={pivotToCase} disabled={creating}>
        {creating ? 'Creating...' : 'Open as Case'}
      </button>
    </div>

    <div class="results-table">
      <table>
        <thead>
          <tr>
            {#each resultColumns as col}
              <th>{col}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each results.slice(0, 100) as row, i (i)}
            <tr>
              {#each resultColumns as col}
                <td>{row[col] ?? ''}</td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
      {#if results.length > 100}
        <p class="truncated">Showing 100 of {resultCount} results</p>
      {/if}
    </div>
  {:else if !loading}
    <p class="empty">Run a hunt query to see results.</p>
  {/if}
</div>

<style>
  .hunt-panel { display: flex; flex-direction: column; gap: 12px; padding: 16px; }
  header h2 { margin: 0; color: #e2e8f0; }
  .controls { display: flex; flex-direction: column; gap: 10px; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #94a3b8; }
  select, input[type="text"] { padding: 6px 10px; background: #1e293b; border: 1px solid #334155; color: #e2e8f0; border-radius: 4px; }
  .params { display: flex; gap: 12px; flex-wrap: wrap; }
  button { padding: 8px 18px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; align-self: flex-start; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .results-header { display: flex; align-items: center; justify-content: space-between; }
  .pivot-btn { background: #22c55e; }
  .results-table { overflow-x: auto; max-height: 500px; overflow-y: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; font-family: monospace; }
  th { background: #0f172a; color: #64748b; padding: 6px 10px; text-align: left; position: sticky; top: 0; }
  td { padding: 4px 10px; color: #e2e8f0; border-bottom: 1px solid #1e293b; white-space: nowrap; max-width: 200px; overflow: hidden; text-overflow: ellipsis; }
  tr:hover td { background: #1e293b; }
  .empty { color: #475569; font-style: italic; font-size: 13px; }
  .error { color: #ef4444; font-size: 13px; padding: 6px; background: #1e0a0a; border-radius: 4px; }
  .success { color: #22c55e; font-size: 13px; padding: 6px; background: #0a1e0a; border-radius: 4px; }
  .truncated { color: #64748b; font-size: 12px; text-align: center; padding: 8px; }
</style>
