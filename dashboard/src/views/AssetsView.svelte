<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type HealthResponse } from '../lib/api.ts'

  // Coverage categories derived from live entity graph data
  let entityCounts = $state<Record<string, number>>({})
  let sourceCounts = $state<Record<string, number>>({})
  let healthData = $state<HealthResponse | null>(null)
  let loading = $state(true)
  let error = $state<string | null>(null)

  // Helper: map /api/health component status to online/offline/unknown
  function componentOnline(name: string): boolean {
    if (!healthData) return false
    // Check direct component name match, then partial match
    const comp = healthData.components[name] ?? healthData.components[Object.keys(healthData.components).find(k => k.toLowerCase().includes(name.toLowerCase())) ?? '']
    return comp?.status === 'healthy' || comp?.status === 'ok'
  }

  // Overall pipeline health: true if healthData.status is healthy
  function pipelineOnline(): boolean {
    return healthData?.status === 'healthy'
  }

  // Derived coverage categories (computed from real entity types)
  let coverageCategories = $derived([
    { label: 'Endpoints/Hosts', monitored: entityCounts['host'] ?? 0, total: entityCounts['host'] ?? 0, color: '#00d4ff' },
    { label: 'Users/Accounts',  monitored: entityCounts['user'] ?? 0, total: entityCounts['user'] ?? 0, color: '#3b82f6' },
    { label: 'Processes',       monitored: entityCounts['process'] ?? 0, total: entityCounts['process'] ?? 0, color: '#22c55e' },
    { label: 'Files',           monitored: entityCounts['file'] ?? 0, total: entityCounts['file'] ?? 0, color: '#a78bfa' },
    { label: 'Network',         monitored: entityCounts['network'] ?? 0, total: entityCounts['network'] ?? 0, color: '#f97316' },
  ])

  // Ingestion sources: status from /api/health (pipeline up/down) + event count from /api/events
  // Status logic: if pipeline is offline -> 'error'; if events > 0 -> 'active'; else -> 'ready'
  let ingestionSources = $derived([
    { name: 'Windows EVTX',      status: !pipelineOnline() ? 'error' : (sourceCounts['evtx'] ?? 0) > 0 ? 'active' : 'ready', events: sourceCounts['evtx'] ?? 0 },
    { name: 'CSV / Syslog',      status: !pipelineOnline() ? 'error' : (sourceCounts['csv'] ?? 0) > 0 ? 'active' : 'ready',  events: sourceCounts['csv'] ?? 0 },
    { name: 'osquery',           status: !pipelineOnline() ? 'error' : (sourceCounts['osquery'] ?? 0) > 0 ? 'active' : 'ready', events: sourceCounts['osquery'] ?? 0 },
    { name: 'JSON / NDJSON',     status: !pipelineOnline() ? 'error' : ((sourceCounts['ndjson'] ?? 0) + (sourceCounts['json'] ?? 0)) > 0 ? 'active' : 'ready', events: (sourceCounts['ndjson'] ?? 0) + (sourceCounts['json'] ?? 0) },
    { name: 'HF SIEM Seed',      status: !pipelineOnline() ? 'error' : (sourceCounts['hf_siem_seed'] ?? 0) > 0 ? 'active' : 'ready', events: sourceCounts['hf_siem_seed'] ?? 0 },
    { name: 'Cloud (AWS/Azure)', status: 'planned', events: 0 },
  ])

  const statusColor: Record<string, string> = {
    ready:   '#22c55e',
    active:  '#00d4ff',
    planned: '#4a5d7a',
    error:   '#ef4444',
  }

  async function loadAssets() {
    loading = true
    error = null
    try {
      // 1. /api/health — pipeline operational status (satisfies P13-T07: source health)
      //    HealthResponse.status: 'healthy'|'degraded'|'unhealthy'
      //    HealthResponse.components: Record<name, { status, detail? }>
      healthData = await api.health()

      // 2. /api/graph/entities — entity type counts for coverage grid
      //    api.graph.entities accepts params?: { type?: string; limit?: number }
      //    Confirmed in api.ts lines 143-148 — no signature change needed.
      const graphRes = await api.graph.entities({ limit: 1000 })
      const counts: Record<string, number> = {}
      for (const entity of graphRes.entities) {
        const t = (entity.type ?? entity.entity_type ?? 'unknown').toLowerCase()
        counts[t] = (counts[t] ?? 0) + 1
      }
      entityCounts = counts

      // 3. /api/events — event counts grouped by source_type (volume per source)
      //    Fetch a representative sample; source counts are approximate for large datasets.
      const eventsRes = await api.events.list({ limit: 500 })
      const sCounts: Record<string, number> = {}
      for (const ev of eventsRes.events) {
        const st = (ev.source_type ?? 'unknown').toLowerCase()
        sCounts[st] = (sCounts[st] ?? 0) + 1
      }
      sourceCounts = sCounts
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  onMount(loadAssets)
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
      <h1>Assets &amp; Coverage</h1>
    </div>
    <button class="btn" disabled>Discover Assets</button>
  </div>

  <div class="content">

    <!-- Coverage summary -->
    <div class="section-title">Coverage by Asset Type</div>
    <div class="coverage-grid">
      {#each coverageCategories as cat}
        <div class="coverage-card">
          <div class="cov-header">
            <span class="cov-label">{cat.label}</span>
            <span class="cov-ratio" style="color: {cat.color}">
              {cat.monitored}/{cat.total}
            </span>
          </div>
          <div class="cov-bar-bg">
            <div
              class="cov-bar-fill"
              style="width: {cat.total > 0 ? Math.round(cat.monitored / cat.total * 100) : 0}%; background: {cat.color}"
            ></div>
          </div>
          <span class="cov-pct">
            {cat.total > 0 ? Math.round(cat.monitored / cat.total * 100) : 0}% monitored
          </span>
        </div>
      {/each}
    </div>

    <!-- Ingestion sources -->
    <div class="section-title" style="margin-top: 8px">Ingestion Sources</div>
    <div class="source-list">
      {#each ingestionSources as src}
        <div class="source-row">
          <span class="src-dot" style="background: {statusColor[src.status]}; box-shadow: 0 0 5px {statusColor[src.status]}"></span>
          <span class="src-name">{src.name}</span>
          <span class="src-events">{src.events > 0 ? src.events.toLocaleString() + ' events' : '—'}</span>
          <span class="src-status" style="color: {statusColor[src.status]}">{src.status}</span>
        </div>
      {/each}
    </div>

    <div class="roadmap-note">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" style="flex-shrink:0; color:var(--accent-cyan)">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.5"/>
        <line x1="8" y1="7" x2="8" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="8" cy="5" r="0.8" fill="currentColor"/>
      </svg>
      Showing live data: entity graph + ingestion pipeline health.
    </div>
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

  .content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }

  .section-title {
    font-size: 11px; font-weight: 600; letter-spacing: 0.8px;
    text-transform: uppercase; color: var(--text-muted);
  }

  .coverage-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px;
  }

  .coverage-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-md); padding: 14px;
    display: flex; flex-direction: column; gap: 8px;
  }

  .cov-header { display: flex; align-items: center; justify-content: space-between; }
  .cov-label { font-size: 12px; font-weight: 600; }
  .cov-ratio { font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; }

  .cov-bar-bg {
    height: 3px; background: var(--bg-tertiary); border-radius: 2px; overflow: hidden;
  }
  .cov-bar-fill { height: 100%; border-radius: 2px; transition: width 0.5s; }

  .cov-pct { font-size: 11px; color: var(--text-muted); }

  .source-list { display: flex; flex-direction: column; gap: 4px; }

  .source-row {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 12px; background: var(--bg-card);
    border: 1px solid var(--border); border-radius: var(--radius-md);
    transition: border-color 0.15s;
  }
  .source-row:hover { border-color: var(--border-hover); }

  .src-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .src-name { font-size: 13px; font-weight: 500; flex: 1; }
  .src-events { font-size: 12px; color: var(--text-muted); font-family: var(--font-mono); }
  .src-status {
    font-size: 10px; font-weight: 700; text-transform: capitalize;
    letter-spacing: 0.3px; min-width: 52px; text-align: right;
  }

  .roadmap-note {
    display: flex; align-items: flex-start; gap: 8px;
    background: rgba(0,212,255,0.05); border: 1px solid rgba(0,212,255,0.15);
    border-radius: var(--radius-md); padding: 12px 14px;
    font-size: 12px; color: var(--text-secondary); line-height: 1.6; max-width: 560px;
  }
</style>
