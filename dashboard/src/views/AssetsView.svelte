<script lang="ts">
  import { api, type Asset, type OsintResult } from '../lib/api.ts'

  let assets = $state<Asset[] | null>(null)
  let expandedIp = $state<string | null>(null)
  let expandedData = $state<{
    events: any[] | null
    detections: any[] | null
    osint: OsintResult | null
    osintError: string | null
  } | null>(null)
  let loading = $state(true)
  let error = $state<string | null>(null)

  function isPrivateIp(ip: string): boolean {
    return /^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|127\.)/.test(ip)
  }

  function riskClass(score: number): string {
    if (score >= 70) return 'risk-high'
    if (score >= 30) return 'risk-medium'
    return 'risk-low'
  }

  function formatDate(iso: string): string {
    try {
      const d = new Date(iso)
      return d.toISOString().replace('T', ' ').substring(0, 16)
    } catch {
      return iso
    }
  }

  async function toggleExpand(ip: string) {
    if (expandedIp === ip) {
      expandedIp = null
      expandedData = null
      return
    }
    expandedIp = ip
    expandedData = { events: null, detections: null, osint: null, osintError: null }

    const results = await Promise.allSettled([
      api.assets.get(ip),
      isPrivateIp(ip) ? Promise.resolve(null) : api.osint.get(ip),
    ])

    const assetDetail = results[0].status === 'fulfilled' ? results[0].value : null
    const osintResult = results[1].status === 'fulfilled' ? results[1].value : null
    const osintErr = results[1].status === 'rejected'
      ? (results[1].reason?.message ?? 'OSINT fetch failed')
      : null

    expandedData = {
      events: assetDetail ? [assetDetail] : [],
      detections: [],
      osint: osintResult,
      osintError: isPrivateIp(ip) ? null : osintErr,
    }
  }

  $effect(() => {
    loading = true
    error = null
    api.assets.list()
      .then(data => { assets = data })
      .catch(e => { error = String(e) })
      .finally(() => { loading = false })
  })
</script>

<div class="view">
  <div class="view-header">
    <div class="header-left">
      <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style="color:#38bdf8">
        <rect x="2" y="2" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/>
        <rect x="9" y="2" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/>
        <rect x="2" y="9" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/>
        <rect x="9" y="9" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/>
      </svg>
      <h1>Assets</h1>
    </div>
  </div>

  <div class="content">
    {#if loading}
      <div class="loading-state">Loading assets…</div>
    {:else if error}
      <div class="error-state">{error}</div>
    {:else if assets === null || assets.length === 0}
      <div class="empty-state">No assets found. Ingest events to populate asset inventory.</div>
    {:else}
      <table class="assets-table">
        <thead>
          <tr>
            <th>Hostname / IP</th>
            <th>Tag</th>
            <th>Risk Score</th>
            <th>Last Seen</th>
            <th>Alerts</th>
          </tr>
        </thead>
        <tbody>
          {#each assets as asset}
            <tr
              class="asset-row {expandedIp === asset.ip ? 'expanded' : ''}"
              onclick={() => toggleExpand(asset.ip)}
            >
              <td class="host-cell">
                <span class="hostname">{asset.hostname ?? asset.ip}</span>
                {#if asset.hostname && asset.hostname !== asset.ip}
                  <span class="ip-secondary">{asset.ip}</span>
                {/if}
              </td>
              <td>
                <span class="tag-chip tag-{asset.tag}">{asset.tag}</span>
              </td>
              <td>
                <span class="risk-badge {riskClass(asset.risk_score)}">{asset.risk_score}</span>
              </td>
              <td class="mono">{formatDate(asset.last_seen)}</td>
              <td class="alert-count {asset.alert_count > 0 ? 'has-alerts' : ''}">{asset.alert_count}</td>
            </tr>
            {#if expandedIp === asset.ip}
              <tr class="detail-row">
                <td colspan="5">
                  <div class="detail-panel">
                    <!-- Event Timeline -->
                    <div class="detail-block">
                      <div class="detail-block-title">Event Timeline</div>
                      {#if expandedData === null}
                        <div class="detail-loading">Loading…</div>
                      {:else if expandedData.events && expandedData.events.length > 0}
                        <div class="timeline-info">
                          <span class="detail-label">First seen:</span>
                          <span class="mono">{formatDate(asset.first_seen)}</span>
                          <span class="sep">|</span>
                          <span class="detail-label">Last seen:</span>
                          <span class="mono">{formatDate(asset.last_seen)}</span>
                          <span class="sep">|</span>
                          <span class="detail-label">Alerts:</span>
                          <span>{asset.alert_count}</span>
                        </div>
                      {:else}
                        <div class="detail-empty">No timeline data available.</div>
                      {/if}
                    </div>

                    <!-- Associated Detections -->
                    <div class="detail-block">
                      <div class="detail-block-title">Associated Detections</div>
                      {#if expandedData === null}
                        <div class="detail-loading">Loading…</div>
                      {:else if expandedData.detections && expandedData.detections.length > 0}
                        {#each expandedData.detections as det}
                          <div class="detection-row">{det.rule_name ?? det.id}</div>
                        {/each}
                      {:else}
                        <div class="detail-empty">No detections linked to this asset.</div>
                      {/if}
                    </div>

                    <!-- OSINT Enrichment -->
                    <div class="detail-block">
                      <div class="detail-block-title">OSINT Enrichment</div>
                      {#if isPrivateIp(asset.ip)}
                        <div class="detail-empty osint-internal">Internal asset — no OSINT enrichment</div>
                      {:else if expandedData === null}
                        <div class="detail-loading">Loading…</div>
                      {:else if expandedData.osintError}
                        <div class="detail-empty">{expandedData.osintError}</div>
                      {:else if expandedData.osint}
                        <div class="osint-grid">
                          {#if expandedData.osint.geo}
                            <span class="detail-label">Country:</span>
                            <span>{expandedData.osint.geo.country_name ?? '—'}</span>
                            <span class="detail-label">ASN:</span>
                            <span>{expandedData.osint.geo.autonomous_system_organization ?? '—'}</span>
                          {/if}
                          {#if expandedData.osint.abuseipdb}
                            <span class="detail-label">Abuse Score:</span>
                            <span>{expandedData.osint.abuseipdb.abuseConfidenceScore ?? '—'}</span>
                          {/if}
                          {#if expandedData.osint.virustotal}
                            <span class="detail-label">VT Malicious:</span>
                            <span>{expandedData.osint.virustotal.malicious ?? '—'}</span>
                          {/if}
                          {#if expandedData.osint.shodan?.open_ports && expandedData.osint.shodan.open_ports.length > 0}
                            <span class="detail-label">Open Ports:</span>
                            <span class="mono">{expandedData.osint.shodan.open_ports.join(', ')}</span>
                          {/if}
                        </div>
                      {:else}
                        <div class="detail-empty">No OSINT data available.</div>
                      {/if}
                    </div>
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

  .view-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 20px; border-bottom: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0;
  }
  .header-left { display: flex; align-items: center; gap: 10px; }
  h1 { font-size: 15px; font-weight: 600; }

  .content { flex: 1; overflow-y: auto; }

  .loading-state,
  .error-state,
  .empty-state {
    padding: 40px 24px;
    font-size: 13px;
    color: var(--text-secondary);
    text-align: center;
  }
  .error-state { color: #ef4444; }

  /* Table */
  .assets-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  .assets-table thead th {
    padding: 8px 14px;
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

  .assets-table tbody td {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    color: var(--text-secondary);
    vertical-align: middle;
  }

  .asset-row {
    cursor: pointer;
    background: #1a1a1a;
    transition: background 0.1s;
  }
  .asset-row:hover { background: rgba(255,255,255,0.04); }
  .asset-row.expanded { background: rgba(255,255,255,0.06); }

  /* Host cell */
  .host-cell { display: flex; flex-direction: column; gap: 2px; }
  .hostname { font-weight: 600; color: var(--text-primary); font-size: 13px; }
  .ip-secondary { font-family: 'JetBrains Mono', monospace; font-size: 10.5px; color: var(--text-muted); }

  /* Tag chips */
  .tag-chip {
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 10.5px; font-weight: 600; text-transform: capitalize; letter-spacing: 0.3px;
  }
  .tag-internal { background: rgba(34,197,94,0.15); color: #22c55e; }
  .tag-external { background: rgba(249,115,22,0.15); color: #f97316; }

  /* Risk badge */
  .risk-badge {
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 11px; font-weight: 700; font-variant-numeric: tabular-nums;
  }
  .risk-high   { background: rgba(239,68,68,0.15);  color: #ef4444; }
  .risk-medium { background: rgba(234,179,8,0.15);  color: #eab308; }
  .risk-low    { background: rgba(34,197,94,0.12);  color: #22c55e; }

  /* Alert count */
  .alert-count { font-variant-numeric: tabular-nums; }
  .alert-count.has-alerts { color: #f97316; font-weight: 700; }

  .mono { font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 11px; }

  /* Detail row */
  .detail-row td { padding: 0; background: rgba(255,255,255,0.02); border-bottom: 1px solid var(--border); }

  .detail-panel {
    display: flex; gap: 0;
    background: #1a1a1a;
    border-left: 2px solid rgba(56,189,248,0.3);
  }

  .detail-block {
    flex: 1; padding: 14px 16px;
    border-right: 1px solid var(--border);
  }
  .detail-block:last-child { border-right: none; }

  .detail-block-title {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.6px; color: var(--text-muted); margin-bottom: 8px;
  }

  .detail-loading,
  .detail-empty { font-size: 12px; color: var(--text-muted); font-style: italic; }
  .osint-internal { color: rgba(56,189,248,0.6); font-style: normal; }

  .timeline-info {
    display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 12px;
  }
  .detail-label { font-size: 11px; color: var(--text-muted); font-weight: 600; }
  .sep { color: var(--border); }

  .detection-row {
    padding: 3px 0; font-size: 12px; color: var(--text-secondary);
  }

  .osint-grid {
    display: grid; grid-template-columns: auto 1fr; gap: 4px 10px; font-size: 12px;
  }
  .osint-grid .detail-label { white-space: nowrap; }
</style>
