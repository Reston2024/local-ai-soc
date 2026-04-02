<script lang="ts">
  import { api } from '../lib/api.ts'

  type Tab = 'ingest' | 'detection' | 'llm' | 'playbook'

  let activeTab = $state<Tab>('ingest')
  let searchId = $state('')
  let result = $state<Record<string, unknown> | null>(null)
  let loading = $state(false)
  let error = $state<string | null>(null)
  let copied = $state(false)

  const tabLabels: Record<Tab, string> = {
    ingest: 'Ingest',
    detection: 'Detection',
    llm: 'AI Response',
    playbook: 'Playbook Run',
  }

  const tabPlaceholders: Record<Tab, string> = {
    ingest: 'Event ID',
    detection: 'Detection ID',
    llm: 'Audit ID',
    playbook: 'Run ID',
  }

  async function lookup() {
    if (!searchId.trim()) return
    loading = true
    error = null
    result = null
    try {
      result = await (api.provenance[activeTab] as (id: string) => Promise<Record<string, unknown>>)(searchId.trim())
    } catch (e: unknown) {
      error = (e instanceof Error ? e.message : null) ?? 'Not found'
    } finally {
      loading = false
    }
  }

  function copyHash(hash: string) {
    navigator.clipboard.writeText(hash).then(() => {
      copied = true
      setTimeout(() => { copied = false }, 1500)
    })
  }

  function isHash(_key: string, val: unknown): boolean {
    return typeof val === 'string' && val.length === 64 && /^[0-9a-f]+$/.test(val)
  }
</script>

<div class="provenance-view">
  <h2>Provenance Lookup</h2>
  <p>Trace the chain of custody for any artefact.</p>

  <div class="tabs">
    {#each (Object.keys(tabLabels) as Tab[]) as tab}
      <button
        class:active={activeTab === tab}
        onclick={() => { activeTab = tab; result = null; error = null }}
      >{tabLabels[tab]}</button>
    {/each}
  </div>

  <div class="search-row">
    <input
      type="text"
      placeholder={tabPlaceholders[activeTab]}
      bind:value={searchId}
      onkeydown={(e) => e.key === 'Enter' && lookup()}
    />
    <button onclick={lookup} disabled={loading}>
      {loading ? 'Looking up...' : 'Lookup'}
    </button>
  </div>

  {#if error}
    <p class="error">{error}</p>
  {/if}

  {#if result}
    <table class="result-table">
      <tbody>
        {#each Object.entries(result) as [key, val]}
          <tr>
            <td class="key">{key}</td>
            <td class="val">
              {#if isHash(key, val)}
                <span class="hash">{val as string}</span>
                <button class="copy-btn" onclick={() => copyHash(val as string)}>
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              {:else if Array.isArray(val)}
                {JSON.stringify(val)}
              {:else}
                {val ?? '—'}
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .provenance-view { padding: 1.5rem; max-width: 800px; }
  .provenance-view h2 { margin: 0 0 0.25rem; font-size: 1.25rem; font-weight: 600; }
  .provenance-view p { margin: 0 0 1.25rem; color: var(--text-secondary, #9ca3af); font-size: 0.875rem; }
  .tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  .tabs button { padding: 0.4rem 1rem; border-radius: 4px; border: 1px solid #555; background: transparent; color: inherit; cursor: pointer; font-size: 0.875rem; }
  .tabs button.active { background: #f59e0b; color: #000; border-color: #f59e0b; }
  .search-row { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  .search-row input { flex: 1; padding: 0.4rem 0.75rem; border-radius: 4px; border: 1px solid #555; background: #1a1a1a; color: inherit; font-size: 0.875rem; }
  .search-row button { padding: 0.4rem 1rem; border-radius: 4px; border: none; background: #f59e0b; color: #000; cursor: pointer; font-size: 0.875rem; font-weight: 600; }
  .search-row button:disabled { opacity: 0.6; cursor: not-allowed; }
  .error { color: #f87171; margin: 0 0 1rem; font-size: 0.875rem; }
  .result-table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
  .result-table td { padding: 0.4rem 0.75rem; border-bottom: 1px solid #333; vertical-align: top; font-size: 0.875rem; }
  .key { color: #9ca3af; font-family: monospace; width: 220px; }
  .hash { font-family: monospace; font-size: 0.8em; word-break: break-all; }
  .copy-btn { margin-left: 0.5rem; padding: 0.1rem 0.5rem; font-size: 0.75em; cursor: pointer; border-radius: 3px; border: 1px solid #555; background: transparent; color: inherit; }
</style>
