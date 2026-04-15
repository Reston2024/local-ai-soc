<script lang="ts">
  import { api, type IocHit, type FeedStatus, type MispIoc } from '../lib/api.ts'

  let hits = $state<IocHit[] | null>(null)
  let feeds = $state<FeedStatus[]>([])
  let mispIocs = $state<MispIoc[] | null>(null)
  let expandedId = $state<number | null>(null)
  let error = $state<string | null>(null)
  let refreshing = $state(false)
  let lastUpdated = $state<Date | null>(null)

  function toggleExpand(id: number) {
    expandedId = expandedId === id ? null : id
  }

  function feedLabel(feed: string): string {
    if (feed === 'feodo') return 'Feodo Tracker'
    if (feed === 'cisa_kev') return 'CISA KEV'
    if (feed === 'threatfox') return 'ThreatFox'
    if (feed === 'misp') return 'MISP'
    return feed
  }

  function statusClass(status: string): string {
    if (status === 'ok') return 'text-green-400'
    if (status === 'stale') return 'text-yellow-400'
    if (status === 'error') return 'text-red-400'
    return 'text-zinc-500'
  }

  function riskClass(score: number): string {
    if (score >= 75) return 'bg-red-900/50 text-red-300'
    if (score >= 50) return 'bg-orange-900/50 text-orange-300'
    if (score >= 25) return 'bg-yellow-900/50 text-yellow-300'
    return 'bg-zinc-800 text-zinc-400'
  }

  function formatRelative(iso: string): string {
    try {
      const diff = Date.now() - new Date(iso).getTime()
      const mins = Math.floor(diff / 60000)
      if (mins < 60) return `${mins}m ago`
      const hrs = Math.floor(mins / 60)
      if (hrs < 24) return `${hrs}h ago`
      return `${Math.floor(hrs / 24)}d ago`
    } catch {
      return iso
    }
  }

  function formatTs(iso: string): string {
    try {
      return new Date(iso).toISOString().replace('T', ' ').substring(0, 19)
    } catch {
      return iso
    }
  }

  async function loadIntel() {
    refreshing = true
    error = null
    try {
      const [f, h, m] = await Promise.all([
        api.intel.feeds(),
        api.intel.iocHits(),
        api.intel.mispEvents(),
      ])
      feeds = f
      hits = h
      mispIocs = m
      lastUpdated = new Date()
    } catch (e) {
      error = String(e)
      hits = hits ?? []
      mispIocs = mispIocs ?? []
    } finally {
      refreshing = false
    }
  }

  $effect(() => {
    loadIntel()
  })
</script>

<div class="view">
  <!-- Page header -->
  <div class="view-header">
    <div class="header-left">
      <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style="color:#f97316">
        <path d="M8 2a6 6 0 1 1 0 12A6 6 0 0 1 8 2Z" stroke="currentColor" stroke-width="1.4"/>
        <path d="M8 5v3.5l2 1.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <h1>Threat Intelligence</h1>
    </div>
    <div class="header-right">
      {#if lastUpdated}
        <span class="last-updated">Updated {formatRelative(lastUpdated.toISOString())}</span>
      {/if}
      <button
        class="btn-refresh"
        onclick={loadIntel}
        disabled={refreshing}
        title="Refresh feeds and IOC hits"
      >
        {#if refreshing}⟳ Refreshing…{:else}⟳ Refresh{/if}
      </button>
    </div>
  </div>

  <!-- Feed header strip -->
  <div class="feed-strip">
    {#each feeds as f}
      <div class="feed-tile">
        <span class="feed-name">{feedLabel(f.feed)}</span>
        <span class="feed-count">{f.ioc_count} IOCs</span>
        <span class="feed-sync">{f.last_sync ? formatRelative(f.last_sync) : 'never'}</span>
        <span class="feed-status {statusClass(f.status)}">{f.status}</span>
      </div>
    {/each}
    {#if feeds.length === 0}
      <div class="feed-loading">Loading feeds…</div>
    {/if}
  </div>

  <!-- Hit list / empty state -->
  <div class="content">
    {#if error}
      <div class="loading-state" style="color:#ef4444">Error: {error}</div>
    {:else if hits === null}
      <div class="loading-state">Loading…</div>
    {:else if hits.length === 0}
      <div class="empty-state">
        <p>No IOC matches yet — feeds syncing hourly.</p>
      </div>
    {:else}
      <table class="hits-table">
        <thead>
          <tr>
            <th>Risk</th>
            <th>Timestamp</th>
            <th>Hostname</th>
            <th>Src IP</th>
            <th>Dst IP</th>
            <th>IOC</th>
            <th>Actor</th>
          </tr>
        </thead>
        <tbody>
          {#each hits as hit}
            <tr
              onclick={() => toggleExpand(hit.id)}
              class="hit-row {expandedId === hit.id ? 'expanded' : ''}"
            >
              <td>
                <span class="risk-badge {riskClass(hit.risk_score)}">{hit.risk_score}</span>
              </td>
              <td class="mono">{formatTs(hit.event_timestamp)}</td>
              <td>{hit.hostname ?? '—'}</td>
              <td class="mono">{hit.src_ip ?? '—'}</td>
              <td class="mono">{hit.dst_ip ?? '—'}</td>
              <td class="mono ioc-val">{hit.ioc_value}</td>
              <td>{hit.actor_tag ?? '—'}</td>
            </tr>
            {#if expandedId === hit.id}
              <tr class="detail-row">
                <td colspan="7">
                  <div class="detail-panel">
                    <div class="detail-section">
                      <span class="detail-label">Feed:</span>
                      <span class="detail-val">{hit.ioc_source}</span>
                      <span class="detail-sep">|</span>
                      <span class="detail-label">IOC Type:</span>
                      <span class="detail-val">{hit.ioc_type}</span>
                      <span class="detail-sep">|</span>
                      <span class="detail-label">IOC Value:</span>
                      <span class="detail-val mono">{hit.ioc_value}</span>
                    </div>
                    <div class="detail-section">
                      <span class="detail-label">Actor Tag:</span>
                      <span class="detail-val">{hit.actor_tag ?? '—'}</span>
                      <span class="detail-sep">|</span>
                      <span class="detail-label">Malware:</span>
                      <span class="detail-val">{hit.malware_family ?? '—'}</span>
                      <span class="detail-sep">|</span>
                      <span class="detail-label">Confidence:</span>
                      <span class="detail-val">{hit.risk_score}</span>
                      <span class="detail-sep">|</span>
                      <span class="detail-label">Matched At:</span>
                      <span class="detail-val mono">{formatTs(hit.matched_at)}</span>
                    </div>
                    <div class="detail-section">
                      <span class="detail-label">Event —</span>
                      <span class="detail-label">Timestamp:</span>
                      <span class="detail-val mono">{formatTs(hit.event_timestamp)}</span>
                      <span class="detail-sep">|</span>
                      <span class="detail-label">Hostname:</span>
                      <span class="detail-val">{hit.hostname ?? '—'}</span>
                      <span class="detail-sep">|</span>
                      <span class="detail-label">Src IP:</span>
                      <span class="detail-val mono">{hit.src_ip ?? '—'}</span>
                      <span class="detail-sep">|</span>
                      <span class="detail-label">Dst IP:</span>
                      <span class="detail-val mono">{hit.dst_ip ?? '—'}</span>
                    </div>
                    {#if hit.ioc_source === 'misp'}
                      {@const ctx = (() => { try { return JSON.parse(hit.extra_json ?? '{}') } catch { return {} } })()}
                      <div class="detail-section misp-context">
                        <span class="detail-label misp-badge">MISP</span>
                        <span class="detail-sep">|</span>
                        <span class="detail-label">Event:</span>
                        <span class="detail-val mono">{ctx.misp_event_id ?? '—'}</span>
                        <span class="detail-sep">|</span>
                        <span class="detail-label">Category:</span>
                        <span class="detail-val">{ctx.misp_category ?? '—'}</span>
                        {#if ctx.misp_tags?.length}
                          <span class="detail-sep">|</span>
                          <span class="detail-label">Tags:</span>
                          <span class="detail-val">{ctx.misp_tags.join(', ')}</span>
                        {/if}
                      </div>
                    {/if}
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    {/if}

    <!-- MISP Intel section -->
    <div class="misp-section">
      <div class="misp-section-header">
        <span class="misp-badge-header">MISP</span>
        <span class="misp-section-title">MISP Threat Intelligence</span>
        <span class="misp-count">
          {mispIocs ? `${mispIocs.length} IOC${mispIocs.length !== 1 ? 's' : ''}` : ''}
        </span>
      </div>
      {#if mispIocs === null}
        <div class="misp-loading">Loading MISP intel…</div>
      {:else if mispIocs.length === 0}
        <div class="misp-empty">
          MISP not yet deployed — see <code>infra/misp/docker-compose.misp.yml</code> to deploy on GMKtec.
        </div>
      {:else}
        <table class="misp-table">
          <thead>
            <tr>
              <th>IOC Value</th>
              <th>Type</th>
              <th>Confidence</th>
              <th>Actor</th>
              <th>MISP Event</th>
              <th>Tags</th>
            </tr>
          </thead>
          <tbody>
            {#each mispIocs as ioc}
              {@const ctx = (() => { try { return JSON.parse(ioc.extra_json ?? '{}') } catch { return {} } })()}
              <tr class="misp-row">
                <td class="mono">{ioc.ioc_value}</td>
                <td><span class="ioc-type-badge">{ioc.ioc_type}</span></td>
                <td>
                  <span class="confidence-badge {ioc.confidence >= 75 ? 'high' : ioc.confidence >= 50 ? 'med' : 'low'}">
                    {ioc.confidence}
                  </span>
                </td>
                <td>{ioc.actor_tag ?? '—'}</td>
                <td class="mono">{ctx.misp_event_id ?? '—'}</td>
                <td class="misp-tags">
                  {#each (ctx.misp_tags ?? []).slice(0, 3) as tag}
                    <span class="tag-chip">{tag}</span>
                  {/each}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  </div>
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

  .view-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
    flex-shrink: 0;
  }

  .header-left { display: flex; align-items: center; gap: 10px; }
  .header-right { display: flex; align-items: center; gap: 12px; }
  h1 { font-size: 15px; font-weight: 600; }

  .last-updated {
    font-size: 11px;
    color: var(--text-muted);
  }

  .btn-refresh {
    font-size: 12px;
    padding: 4px 12px;
    background: var(--bg-tertiary, #1f2937);
    border: 1px solid var(--border);
    border-radius: 5px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: background 0.15s;
  }
  .btn-refresh:hover:not(:disabled) { background: var(--bg-hover, #374151); color: var(--text-primary); }
  .btn-refresh:disabled { opacity: 0.5; cursor: default; }

  /* Feed strip */
  .feed-strip {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
    flex-shrink: 0;
  }

  .feed-tile {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 20px;
    border-right: 1px solid var(--border);
    font-size: 12px;
  }

  .feed-name { font-weight: 600; color: var(--text-primary); }
  .feed-count { color: var(--text-secondary); }
  .feed-sync { color: var(--text-muted); }
  .feed-status { font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px; }
  .feed-loading { padding: 8px 20px; font-size: 12px; color: var(--text-muted); }

  /* Content area */
  .content { flex: 1; overflow-y: auto; padding: 0; }

  .loading-state,
  .empty-state {
    padding: 40px 24px;
    font-size: 13px;
    color: var(--text-secondary);
    text-align: center;
  }

  /* Hits table */
  .hits-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  .hits-table thead th {
    padding: 8px 12px;
    text-align: left;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
    white-space: nowrap;
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .hits-table tbody td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    color: var(--text-secondary);
    white-space: nowrap;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .hit-row {
    cursor: pointer;
    transition: background 0.1s;
  }

  .hit-row:hover { background: rgba(255,255,255,0.04); }
  .hit-row.expanded { background: rgba(255,255,255,0.06); }

  .risk-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  .mono { font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 11px; }
  .ioc-val { max-width: 180px; }

  /* Inline detail panel */
  .detail-row td { padding: 0; background: rgba(255,255,255,0.03); border-bottom: 1px solid var(--border); }

  .detail-panel {
    padding: 12px 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 12px;
  }

  .detail-section {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }

  .detail-label { color: var(--text-muted); font-weight: 600; font-size: 11px; }
  .detail-val { color: var(--text-primary); }
  .detail-sep { color: var(--border); }

  /* MISP section */
  .misp-section {
    border-top: 1px solid var(--border);
    margin-top: 16px;
    padding: 12px 20px 20px;
  }
  .misp-section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    font-size: 13px;
  }
  .misp-badge-header {
    background: #6d28d9;
    color: #ede9fe;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 3px;
    letter-spacing: 0.5px;
  }
  .misp-section-title { font-weight: 600; color: var(--text-primary); }
  .misp-count { font-size: 11px; color: var(--text-muted); margin-left: auto; }
  .misp-loading, .misp-empty { font-size: 12px; color: var(--text-muted); padding: 12px 0; }
  .misp-empty code { font-family: monospace; color: #8b5cf6; }
  .misp-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }
  .misp-table th {
    text-align: left;
    padding: 6px 10px;
    color: var(--text-muted);
    font-weight: 500;
    border-bottom: 1px solid var(--border);
  }
  .misp-row td { padding: 6px 10px; border-bottom: 1px solid var(--border-subtle, #1f2937); }
  .misp-row:hover td { background: var(--bg-hover, #1a1f2e); }
  .ioc-type-badge {
    background: var(--bg-tertiary, #1f2937);
    border: 1px solid var(--border);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 10px;
    font-family: monospace;
  }
  .confidence-badge {
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 600;
  }
  .confidence-badge.high { background: #450a0a; color: #fca5a5; }
  .confidence-badge.med { background: #431407; color: #fdba74; }
  .confidence-badge.low { background: #1c1917; color: #a8a29e; }
  .misp-tags { display: flex; flex-wrap: wrap; gap: 4px; }
  .tag-chip {
    background: #2e1065;
    color: #c4b5fd;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 10px;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .misp-badge {
    background: #6d28d9;
    color: #ede9fe;
    font-size: 9px;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 3px;
    letter-spacing: 0.5px;
  }
  .misp-context { border-top: 1px dashed #6d28d9; margin-top: 6px; padding-top: 6px; }
</style>
