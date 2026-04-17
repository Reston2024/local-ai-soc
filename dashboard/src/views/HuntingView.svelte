<script lang="ts">
  import { onMount } from 'svelte'
  import { api } from '../lib/api.ts'
  import type { HuntResult, HuntPreset, HuntRow, OsintResult, HuntHistoryItem } from '../lib/api.ts'

  // Fetched from /api/hunts/presets on mount — single source of truth
  let presetHunts = $state<HuntPreset[]>([])

  let query = $state('')
  let isRunning = $state(false)
  let errorMsg = $state<string | null>(null)
  let results = $state<HuntResult | null>(null)
  let expandedIp = $state<string | null>(null)
  let osintData = $state<OsintResult | null>(null)
  let osintLoading = $state(false)
  let huntHistory = $state<HuntHistoryItem[]>([])

  async function runHunt(q: string) {
    if (!q.trim()) return
    isRunning = true
    errorMsg = null
    expandedIp = null
    osintData = null
    try {
      results = await api.hunts.query(q)
      huntHistory = [
        {
          hunt_id: results.hunt_id,
          query: q,
          sql_text: results.sql,
          row_count: results.row_count,
          analyst_id: 'analyst',
          created_at: results.created_at,
        },
        ...huntHistory,
      ].slice(0, 10)
    } catch (err: unknown) {
      errorMsg = err instanceof Error ? err.message : String(err)
    } finally {
      isRunning = false
    }
  }

  async function expandRow(ip: string | undefined | null) {
    if (!ip) return
    // Private IP ranges — no OSINT
    if (
      ip.startsWith('10.') ||
      ip.startsWith('192.168.') ||
      ip.startsWith('172.') ||
      ip === '127.0.0.1' ||
      ip.startsWith('::1')
    ) {
      expandedIp = ip
      osintData = null
      osintLoading = false
      return
    }
    expandedIp = ip
    osintLoading = true
    osintData = null
    try {
      osintData = await api.osint.get(ip)
    } catch (err: unknown) {
      // Silently clear — private IP or invalid IP error from backend
      osintData = null
    } finally {
      osintLoading = false
    }
  }

  onMount(async () => {
    try {
      const { presets } = await api.hunts.presets()
      presetHunts = presets
    } catch { /* presets fetch is non-critical — grid stays empty */ }
    try {
      const { hunts } = await api.hunts.history(20)
      huntHistory = hunts
    } catch { /* history fetch is non-critical */ }
  })

  function isPrivateIp(ip: string): boolean {
    return (
      ip.startsWith('10.') ||
      ip.startsWith('192.168.') ||
      ip.startsWith('172.') ||
      ip === '127.0.0.1' ||
      ip.startsWith('::1')
    )
  }
</script>

<div class="view">
  <div class="view-header">
    <div class="header-left">
      <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style="color:#e879f9">
        <circle cx="7.5" cy="7.5" r="5" stroke="currentColor" stroke-width="1.4"/>
        <line x1="7.5" y1="2.5" x2="7.5" y2="4.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="7.5" y1="10.5" x2="7.5" y2="12.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="2.5" y1="7.5" x2="4.5" y2="7.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="10.5" y1="7.5" x2="12.5" y2="7.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <circle cx="7.5" cy="7.5" r="1.5" fill="currentColor"/>
      </svg>
      <h1>Threat Hunting</h1>
    </div>
    <span class="active-badge">ACTIVE</span>
  </div>

  <div class="content">
    <div class="hunt-bar">
      <input
        type="text"
        bind:value={query}
        placeholder="Describe what you're hunting for… (e.g. 'PowerShell download cradle')"
        class="hunt-input"
        disabled={isRunning}
      />
      <button
        class="btn btn-primary"
        onclick={() => runHunt(query)}
        disabled={isRunning || !query.trim()}
      >
        {#if isRunning}
          <span class="spinner"></span>
        {:else}
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="1.6"/>
            <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
          </svg>
        {/if}
        Hunt
      </button>
    </div>

    {#if errorMsg}
      <div class="error-banner">{errorMsg}</div>
    {/if}

    {#if results}
      <div class="results-section">
        <div class="results-header">
          <span>{results.row_count} event{results.row_count !== 1 ? 's' : ''} found</span>
          <code class="sql-pill">{results.sql}</code>
        </div>
        <table class="results-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Host</th>
              <th>Severity</th>
              <th>Type</th>
              <th>Src IP</th>
              <th>Dst IP</th>
              <th>Process</th>
              <th>User</th>
            </tr>
          </thead>
          <tbody>
            {#each results.rows as row}
              <tr onclick={() => expandRow(row.src_ip)} class:selected={expandedIp === row.src_ip && !!row.src_ip}>
                <td>{row.ts?.slice(0, 19) ?? '—'}</td>
                <td>{row.hostname ?? '—'}</td>
                <td><span class="sev-badge sev-{row.severity?.toLowerCase() ?? 'info'}">{row.severity ?? 'info'}</span></td>
                <td>{row.event_type ?? '—'}</td>
                <td class="ip-cell">{row.src_ip ?? '—'}</td>
                <td class="ip-cell">{row.dst_ip ?? '—'}</td>
                <td>{row.process_name ?? '—'}</td>
                <td>{row.user_name ?? '—'}</td>
              </tr>
              {#if expandedIp === row.src_ip && row.src_ip}
                <tr class="osint-row">
                  <td colspan="8">
                    {#if isPrivateIp(row.src_ip)}
                      <div class="osint-loading">Private IP — no OSINT</div>
                    {:else if osintLoading}
                      <div class="osint-loading">Loading OSINT…</div>
                    {:else if osintData}
                      <div class="osint-panel">
                        <div class="osint-section">
                          <span class="osint-label">GEO</span>
                          {osintData.geo?.country_name ?? '—'} / {osintData.geo?.city ?? '—'} ({osintData.geo?.autonomous_system_organization ?? '—'})
                        </div>
                        {#if osintData.abuseipdb}
                          <div class="osint-section">
                            <span class="osint-label">ABUSE</span>
                            Confidence: {osintData.abuseipdb.abuseConfidenceScore}% — {osintData.abuseipdb.totalReports} reports — {osintData.abuseipdb.isp}
                          </div>
                        {/if}
                        {#if osintData.virustotal}
                          <div class="osint-section">
                            <span class="osint-label">VT</span>
                            {osintData.virustotal.malicious} malicious / {osintData.virustotal.suspicious} suspicious
                          </div>
                        {/if}
                        {#if osintData.whois}
                          <div class="osint-section">
                            <span class="osint-label">WHOIS</span>
                            {osintData.whois.registrar ?? '—'} — created {osintData.whois.creation_date ?? '—'} — {osintData.whois.org ?? '—'}
                          </div>
                        {/if}
                        {#if osintData.shodan}
                          <div class="osint-section">
                            <span class="osint-label">SHODAN</span>
                            Ports: {osintData.shodan.open_ports?.join(', ') ?? 'none'} — {osintData.shodan.org ?? '—'}
                          </div>
                        {/if}
                        <div class="osint-cached">{osintData.cached ? '(cached)' : '(fresh)'} as of {osintData.fetched_at.slice(0, 19)}</div>
                      </div>
                    {:else}
                      <div class="osint-loading">No OSINT data available</div>
                    {/if}
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    <div class="preset-label">Preset Hunt Queries</div>
    <div class="hunt-grid">
      {#each presetHunts as hunt}
        <div class="hunt-card">
          <div class="hunt-top">
            <span class="hunt-name">{hunt.name}</span>
            <span class="mitre-tag">{hunt.mitre}</span>
          </div>
          <p class="hunt-desc">{hunt.desc}</p>
          <button class="hunt-run-btn" onclick={() => runHunt(hunt.query)}>Run Hunt</button>
        </div>
      {/each}
    </div>

    {#if huntHistory.length > 0}
      <div class="history-section">
        <div class="preset-label">Hunt History</div>
        {#each huntHistory as h}
          <div class="history-item" onclick={() => { query = h.query; runHunt(h.query) }} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && runHunt(h.query)}>
            <span class="history-query">{h.query}</span>
            <span class="history-meta">{h.row_count} rows · {h.created_at.slice(0, 19)}</span>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

  .view-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 20px; border-bottom: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0;
  }
  .header-left { display: flex; align-items: center; gap: 10px; }
  h1 { font-size: 15px; font-weight: 600; }

  .active-badge {
    font-size: 10px; font-weight: 700; letter-spacing: 0.6px;
    color: #22c55e; background: rgba(34,197,94,0.1);
    border: 1px solid rgba(34,197,94,0.25); padding: 3px 10px; border-radius: 20px;
  }

  .content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 18px; }

  .hunt-bar { display: flex; gap: 10px; }
  .hunt-input {
    flex: 1; height: 38px; border-radius: var(--radius-md);
    font-size: 13px; padding: 0 14px;
  }

  .preset-label {
    font-size: 11px; font-weight: 600; letter-spacing: 0.8px;
    text-transform: uppercase; color: var(--text-muted);
  }

  .hunt-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px;
  }

  .hunt-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-md); padding: 14px; display: flex;
    flex-direction: column; gap: 8px;
    transition: border-color 0.15s;
  }
  .hunt-card:hover { border-color: var(--border-hover); }

  .hunt-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
  .hunt-name { font-size: 13px; font-weight: 600; line-height: 1.3; flex: 1; }

  .mitre-tag {
    font-size: 10px; font-weight: 700; font-family: var(--font-mono);
    color: #a78bfa; background: rgba(167,139,250,0.1);
    border: 1px solid rgba(167,139,250,0.2); padding: 2px 7px; border-radius: 4px;
    white-space: nowrap;
  }

  .hunt-desc { font-size: 12px; color: var(--text-secondary); line-height: 1.5; flex: 1; }

  .hunt-run-btn {
    align-self: flex-start; font-size: 11px; padding: 4px 12px;
    background: var(--bg-tertiary); color: var(--text-secondary);
    border: 1px solid var(--border); border-radius: var(--radius-md);
    cursor: pointer; font-family: var(--font-sans);
  }
  .hunt-run-btn:hover { border-color: var(--border-hover); color: var(--text-primary); }

  /* Results table */
  .results-section { display: flex; flex-direction: column; gap: 8px; }
  .results-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .results-table th { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); font-weight: 600; color: var(--text-muted); font-size: 10px; letter-spacing: 0.5px; }
  .results-table td { padding: 6px 10px; border-bottom: 1px solid var(--border-subtle, var(--border)); }
  .results-table tr:hover td { background: var(--bg-hover); cursor: pointer; }
  .results-table tr.selected td { background: rgba(167,139,250,0.08); }
  .sev-badge { font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; }
  .sev-critical { background: rgba(239,68,68,0.15); color: #ef4444; }
  .sev-high { background: rgba(249,115,22,0.15); color: #f97316; }
  .sev-medium { background: rgba(234,179,8,0.15); color: #eab308; }
  .sev-low { background: rgba(34,197,94,0.15); color: #22c55e; }
  .sev-info { background: rgba(148,163,184,0.1); color: var(--text-muted); }
  .osint-panel { display: flex; flex-wrap: wrap; gap: 12px; padding: 10px 0; }
  .osint-section { font-size: 12px; color: var(--text-secondary); }
  .osint-label { font-size: 10px; font-weight: 700; letter-spacing: 0.5px; color: var(--accent-purple); margin-right: 6px; }
  .osint-cached { font-size: 10px; color: var(--text-muted); width: 100%; }
  .osint-loading { padding: 10px; color: var(--text-muted); font-size: 12px; }
  .sql-pill { font-size: 10px; color: var(--text-muted); background: var(--bg-secondary); padding: 2px 8px; border-radius: 4px; overflow: hidden; text-overflow: ellipsis; max-width: 600px; display: inline-block; white-space: nowrap; }
  .results-header { display: flex; align-items: center; gap: 12px; font-size: 12px; color: var(--text-secondary); }
  .error-banner { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); color: #ef4444; padding: 10px 14px; border-radius: var(--radius-md); font-size: 13px; }
  .history-section { display: flex; flex-direction: column; gap: 6px; }
  .history-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--bg-secondary); border-radius: var(--radius-sm); cursor: pointer; font-size: 12px; }
  .history-item:hover { background: var(--bg-hover); }
  .history-query { color: var(--text-primary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .history-meta { color: var(--text-muted); font-size: 11px; flex-shrink: 0; margin-left: 12px; }
  .spinner { display: inline-block; width: 10px; height: 10px; border: 2px solid transparent; border-top-color: currentColor; border-radius: 50%; animation: spin 0.6s linear infinite; margin-right: 6px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .ip-cell { font-family: monospace; font-size: 11px; }
  .osint-row td { background: var(--bg-secondary); }
  code { font-size: 11px; color: var(--accent-cyan); }
</style>
