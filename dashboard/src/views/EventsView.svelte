<script lang="ts">
  import { untrack } from 'svelte'
  import { api, type NormalizedEvent } from '../lib/api.ts'

  let events = $state<NormalizedEvent[]>([])
  let total = $state(0)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let offset = $state(0)
  let limit = 50
  let searchQuery = $state('')

  // Phase 31: event_type filter chips
  const CHIPS = [
    { label: 'All',     value: '' },
    { label: 'Alert',   value: 'alert' },
    { label: 'TLS',     value: 'tls' },
    { label: 'DNS',     value: 'dns_query' },
    { label: 'File',    value: 'file_transfer' },
    { label: 'Anomaly', value: 'anomaly' },
    { label: 'Syslog',  value: 'syslog' },
  ]
  let selectedChip = $state('')   // '' = All

  // Phase 36 Zeek chips — disabled until SPAN port is configured (managed switch in transit)
  const ZEEK_CHIPS = [
    { label: 'Connection', value: 'conn' },
    { label: 'HTTP',       value: 'http' },
    { label: 'SSL',        value: 'ssl' },
    { label: 'SMB',        value: 'smb' },
    { label: 'Auth',       value: 'auth' },
    { label: 'SSH',        value: 'ssh' },
    { label: 'SMTP',       value: 'smtp' },
    { label: 'DHCP',       value: 'dhcp' },
  ]

  async function load() {
    loading = true
    error = null
    try {
      const res = await api.events.list({
        offset,
        limit,
        ...(selectedChip ? { event_type: selectedChip } : {}),
      })
      events = res.events
      total = res.total
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  $effect(() => {
    // Track ONLY selectedChip. untrack() prevents load() from registering
    // offset as a dependency — otherwise every Next/Prev click would trigger
    // this effect, resetting offset to 0 and bouncing back to page 1.
    selectedChip
    untrack(() => {
      offset = 0
      load()
    })
  })

  async function search() {
    if (!searchQuery.trim()) { load(); return }
    loading = true
    error = null
    try {
      const res = await api.events.search(searchQuery, 50)
      events = res.events
      total = events.length
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  function fmtTime(ts: string) {
    return new Date(ts).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }
</script>

<div class="view">
  <div class="view-header">
    <h1>Events <span class="count">{total}</span></h1>
    <div class="search-bar">
      <input
        type="text"
        placeholder="Semantic search events…"
        bind:value={searchQuery}
        onkeydown={(e) => e.key === 'Enter' && search()}
      />
      <button class="btn btn-primary" onclick={search}>Search</button>
      <button class="btn" onclick={() => { searchQuery = ''; load() }}>Clear</button>
    </div>
  </div>

  <div class="chip-row">
    {#each CHIPS as chip}
      <button
        class="chip {selectedChip === chip.value ? 'chip-active' : ''}"
        onclick={() => { selectedChip = chip.value }}
      >
        {chip.label}
      </button>
    {/each}
    <span class="chip-divider" title="Zeek telemetry — available once managed switch SPAN port is configured">Phase 36</span>
    {#each ZEEK_CHIPS as chip}
      <button
        class="chip {selectedChip === chip.value ? 'chip-active' : ''}"
        title="Zeek {chip.label} logs"
        onclick={() => { selectedChip = chip.value }}
      >
        {chip.label}
      </button>
    {/each}
  </div>

  {#if error}
    <div class="error-banner">⚠ {error}</div>
  {/if}

  {#if loading}
    <div class="loading">Loading events...</div>
  {:else if events.length === 0}
    <div class="empty">No events found. Upload event files via Ingest.</div>
  {:else}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Host</th>
            <th>User</th>
            <th>Process</th>
            <th>Type</th>
            <th>Severity</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {#each events as e}
            <tr>
              <td class="mono ts">{fmtTime(e.timestamp)}</td>
              <td>{e.hostname ?? '—'}</td>
              <td>{e.username ?? '—'}</td>
              <td class="mono">{e.process_name ?? '—'}</td>
              <td class="mono event-type">{e.event_type ?? '—'}</td>
              <td><span class="badge badge-{e.severity}">{e.severity}</span></td>
              <td class="mono source">{e.source_type}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <div class="pagination">
      <button class="btn" disabled={offset === 0} onclick={() => { offset = Math.max(0, offset - limit); load() }}>← Prev</button>
      <span>{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
      <button class="btn" disabled={offset + limit >= total} onclick={() => { offset += limit; load() }}>Next →</button>
    </div>
  {/if}
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
  .view-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 20px; border-bottom: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0; gap: 16px;
  }
  h1 { font-size: 16px; font-weight: 600; flex-shrink: 0; }
  .search-bar { display: flex; gap: 8px; flex: 1; max-width: 600px; }
  .search-bar input { flex: 1; }
  .count {
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 20px; height: 18px; padding: 0 6px;
    background: var(--bg-tertiary); border: 1px solid var(--border);
    border-radius: 10px; font-size: 11px; font-weight: 600;
    margin-left: 8px; color: var(--text-secondary);
  }
  .chip-row {
    display: flex; gap: 6px; padding: 8px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0;
    overflow-x: auto;
  }
  .chip {
    padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 500;
    border: 1px solid var(--border); background: var(--bg-primary);
    color: var(--text-secondary); cursor: pointer; white-space: nowrap;
    transition: background 0.15s, color 0.15s;
  }
  .chip:hover { background: var(--bg-tertiary); color: var(--text-primary); }
  .chip-active {
    background: var(--accent, #4ade80); color: #0d0d0d;
    border-color: transparent;
  }
  .chip-divider {
    font-size: 10px; font-weight: 600; color: var(--text-muted, #666);
    text-transform: uppercase; letter-spacing: 0.05em;
    align-self: center; padding: 0 4px; white-space: nowrap;
    border-left: 1px solid var(--border); padding-left: 10px; margin-left: 4px;
  }
  .chip-beta {
    opacity: 0.45; cursor: not-allowed;
    border-style: dashed;
  }
  .chip-beta:hover { background: var(--bg-primary); color: var(--text-secondary); }
  .table-wrap { flex: 1; overflow-y: auto; }
  .ts { color: var(--text-secondary); font-size: 12px; white-space: nowrap; }
  .event-type { color: var(--text-secondary); }
  .source { color: var(--text-muted); font-size: 11px; }
  .pagination {
    display: flex; align-items: center; justify-content: center; gap: 16px;
    padding: 12px; border-top: 1px solid var(--border);
    color: var(--text-secondary); font-size: 13px; flex-shrink: 0;
  }
  .loading, .empty { padding: 40px; text-align: center; color: var(--text-secondary); }
  .error-banner { padding: 12px 20px; background: rgba(248,81,73,0.1); color: var(--severity-critical); border-bottom: 1px solid rgba(248,81,73,0.3); font-size: 13px; }
</style>
