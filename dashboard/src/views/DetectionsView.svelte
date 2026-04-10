<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type Detection, type KpiSnapshot, type TriageResult } from '../lib/api.ts'

  let {
    onInvestigate,
    onPostureUpdate,
  }: {
    onInvestigate?: (id: string) => void
    onPostureUpdate?: (score: number) => void
  } = $props()

  let detections = $state<Detection[]>([])
  let total = $state(0)
  let loading = $state(true)
  let runningDetection = $state(false)
  let error = $state<string | null>(null)
  let severityFilter = $state('')

  // Severity breakdowns
  let criticalCount = $derived(detections.filter(d => d.severity?.toLowerCase() === 'critical').length)
  let highCount     = $derived(detections.filter(d => d.severity?.toLowerCase() === 'high').length)
  let mediumCount   = $derived(detections.filter(d => d.severity?.toLowerCase() === 'medium').length)
  let lowCount      = $derived(detections.filter(d => d.severity?.toLowerCase() === 'low').length)

  // Naive posture: 100 - (critical*25 + high*10 + medium*4 + low*1), floored at 0
  let postureScore = $derived(
    Math.max(0, 100 - criticalCount * 25 - highCount * 10 - mediumCount * 4 - lowCount * 1)
  )

  // Push posture to parent whenever it changes
  $effect(() => { onPostureUpdate?.(postureScore) })

  // Live KPI state — replaces mock mttd/mttr stubs
  let kpis = $state<KpiSnapshot | null>(null)
  let kpiError = $state<string | null>(null)
  let kpiPollingInterval: ReturnType<typeof setInterval> | null = null
  // Keep activeCases as a fallback for open_cases when kpis is null
  let activeCases = $state(0)
  let ingestionOk = $state<boolean | null>(null)

  async function load() {
    loading = true
    error = null
    try {
      const res = await api.detections.list({ limit: 100, severity: severityFilter || undefined })
      detections = res.detections ?? []
      total = res.total
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  async function checkIngestion() {
    try {
      await api.health()
      ingestionOk = true
    } catch {
      ingestionOk = false
    }
  }

  async function loadKpis() {
    try {
      kpis = await api.metrics.kpis()
      kpiError = null
    } catch (e) {
      kpiError = String(e)
      // Keep stale kpis rather than nulling on transient error
    }
  }

  async function runDetection() {
    runningDetection = true
    error = null
    try {
      await api.detections.run()
      await load()
    } catch (e) {
      error = String(e)
    } finally {
      runningDetection = false
    }
  }

  onMount(async () => {
    await Promise.all([load(), checkIngestion(), loadKpis()])
  })

  $effect(() => {
    kpiPollingInterval = setInterval(loadKpis, 60_000)
    return () => { if (kpiPollingInterval) clearInterval(kpiPollingInterval) }
  })

  function severityClass(s: string) { return `badge badge-${s.toLowerCase()}` }

  function fmtTime(ts: string | undefined) {
    if (!ts) return '—'
    return new Date(ts).toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  }

  function getDetectionId(d: Detection): string { return d.detection_id ?? d.id ?? '' }

  function getEventCount(d: Detection): number {
    if (d.matched_event_ids) return d.matched_event_ids.length
    if (d.event_id) return 1
    return 0
  }

  let lastUpdated = $state(new Date())
  $effect(() => {
    if (!loading) lastUpdated = kpis ? new Date(kpis.computed_at) : new Date()
  })

  // ── Triage panel ──
  let triageResult = $state<TriageResult | null>(null)
  let triageRunning = $state(false)
  let triagePanelOpen = $state(true)

  async function loadTriage() {
    try {
      const { result } = await api.triage.latest()
      triageResult = result
    } catch { /* triage fetch failure is non-critical */ }
  }

  $effect(() => {
    loadTriage()
    const interval = setInterval(loadTriage, 15_000)
    return () => clearInterval(interval)
  })

  async function runTriageNow() {
    triageRunning = true
    try {
      await api.triage.run()
      await loadTriage()
    } finally {
      triageRunning = false
    }
  }

  function fmtUpdated(d: Date) {
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }
</script>

<div class="view">
  <!-- ── Triage panel ── -->
  <div class="triage-panel">
    <div class="triage-header" role="button" tabindex="0"
      onclick={() => triagePanelOpen = !triagePanelOpen}
      onkeydown={(e) => e.key === 'Enter' && (triagePanelOpen = !triagePanelOpen)}
    >
      <span class="triage-title">
        AI Triage
        {#if triageRunning}<span class="triage-running">— Analyzing…</span>{/if}
      </span>
      {#if triageRunning}<span class="triage-spinner"></span>{/if}
      <button
        class="btn btn-sm"
        onclick={(e) => { e.stopPropagation(); runTriageNow() }}
        disabled={triageRunning}
      >
        Run Triage Now
      </button>
      <span class="collapse-icon">{triagePanelOpen ? '▲' : '▼'}</span>
    </div>
    {#if triagePanelOpen}
      <div class="triage-body">
        {#if triageResult}
          <div class="triage-summary">
            <strong>{triageResult.severity_summary}</strong>
            <span class="triage-meta">
              {triageResult.detection_count} detections
              · {triageResult.model_name}
              · {triageResult.created_at}
            </span>
          </div>
        {:else}
          <span class="triage-empty">
            No triage results yet. Click "Run Triage Now" to analyze detections.
          </span>
        {/if}
      </div>
    {/if}
  </div>

  <!-- ── Operational KPI bar ── -->
  <div class="kpi-bar">
    <!-- Severity pills -->
    <div class="kpi-group severity-group">
      <div class="severity-pill critical" class:alert={criticalCount > 0}>
        <span class="sev-dot"></span>
        <span class="sev-count">{criticalCount}</span>
        <span class="sev-label">Critical</span>
        <div class="sev-underline"></div>
      </div>
      <div class="severity-pill high" class:alert={highCount > 0}>
        <span class="sev-dot"></span>
        <span class="sev-count">{highCount}</span>
        <span class="sev-label">High</span>
        <div class="sev-underline"></div>
      </div>
      <div class="severity-pill medium" class:alert={mediumCount > 0}>
        <span class="sev-dot"></span>
        <span class="sev-count">{mediumCount}</span>
        <span class="sev-label">Medium</span>
        <div class="sev-underline"></div>
      </div>
      <div class="severity-pill low">
        <span class="sev-dot"></span>
        <span class="sev-count">{lowCount}</span>
        <span class="sev-label">Low</span>
        <div class="sev-underline"></div>
      </div>
    </div>

    <div class="kpi-divider"></div>

    <!-- Operational metrics -->
    <div class="kpi-group ops-group">
      <div class="kpi-stat" title="Mean Time to Detect">
        <span class="kpi-value">{kpis ? kpis.mttd.value.toFixed(1) + ' min' : '—'}</span>
        <span class="kpi-key">MTTD</span>
      </div>
      <div class="kpi-stat" title="Mean Time to Respond">
        <span class="kpi-value">{kpis ? kpis.mttr.value.toFixed(1) + ' min' : '—'}</span>
        <span class="kpi-key">MTTR</span>
      </div>
      <div class="kpi-stat" title="Mean Time to Contain">
        <span class="kpi-value">{kpis ? kpis.mttc.value.toFixed(1) + ' min' : '—'}</span>
        <span class="kpi-key">MTTC</span>
      </div>
      <div class="kpi-stat" title="False Positive Rate">
        <span class="kpi-value">{kpis ? (kpis.false_positive_rate.value * 100).toFixed(0) + '%' : '—'}</span>
        <span class="kpi-key">FP Rate</span>
      </div>
      <div class="kpi-stat" title="Active detection rules">
        <span class="kpi-value">{kpis ? kpis.active_rules.value : '—'}</span>
        <span class="kpi-key">Active Rules</span>
      </div>
      <div class="kpi-stat" title="Open investigation cases">
        <span class="kpi-value">{kpis ? kpis.open_cases.value : activeCases}</span>
        <span class="kpi-key">Active Cases</span>
      </div>
      <div class="kpi-stat" title="Alerts in last 24 hours">
        <span class="kpi-value">{kpis ? kpis.alert_volume_24h.value : total}</span>
        <span class="kpi-key">24h Alerts</span>
      </div>
      <div class="kpi-stat" title="Total detections loaded">
        <span class="kpi-value">{total}</span>
        <span class="kpi-key">Total</span>
      </div>
      <div class="kpi-stat ingestion" title="Ingestion pipeline health">
        {#if ingestionOk === null}
          <span class="kpi-value muted">—</span>
        {:else if ingestionOk}
          <span class="kpi-value ok">● Online</span>
        {:else}
          <span class="kpi-value warn">● Offline</span>
        {/if}
        <span class="kpi-key">Pipeline</span>
      </div>
    </div>

    <!-- Actions -->
    <div class="kpi-actions">
      <span class="last-updated" title="Last refreshed">
        {fmtUpdated(lastUpdated)}
      </span>
      <select bind:value={severityFilter} onchange={load} class="severity-select">
        <option value="">All severities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <button class="btn" onclick={load} disabled={loading}>
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
          <path d="M13.5 8A5.5 5.5 0 1 1 8 2.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
          <path d="M8 1v3.5L10.5 3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Refresh
      </button>
      <button class="btn btn-primary" onclick={runDetection} disabled={runningDetection}>
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
          <path d="M9 1.5L3.5 9H7.5L7 14.5L12.5 7H8.5L9 1.5Z" fill="currentColor"/>
        </svg>
        {runningDetection ? 'Running…' : 'Run Detection'}
      </button>
    </div>
  </div>

  {#if error}
    <div class="error-banner">
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none" style="flex-shrink:0">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.5"/>
        <line x1="8" y1="5" x2="8" y2="8.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="8" cy="11" r="0.8" fill="currentColor"/>
      </svg>
      {error}
    </div>
  {/if}

  {#if loading}
    <div class="state-wrap">
      <div class="spinner"></div>
      <span class="state-text">Loading detections…</span>
    </div>
  {:else if detections.length === 0}
    <div class="empty-state">
      <div class="empty-icon">
        <svg width="90" height="100" viewBox="0 0 90 100" fill="none">
          <path d="M45 6L10 19V46C10 66 26 82 45 92C64 82 80 66 80 46V19L45 6Z"
            fill="rgba(0,212,255,0.06)" stroke="#00d4ff" stroke-width="1.8"/>
          <circle cx="45" cy="48" r="16" fill="none" stroke="#00d4ff" stroke-width="1.4" opacity="0.5"/>
          <circle cx="45" cy="48" r="9"  fill="none" stroke="#00d4ff" stroke-width="1.2" opacity="0.35"/>
          <circle cx="45" cy="48" r="3.5" fill="#00d4ff" opacity="0.6"/>
          <line x1="29" y1="48" x2="23" y2="48" stroke="#00d4ff" stroke-width="1.2" opacity="0.5" stroke-linecap="round"/>
          <line x1="61" y1="48" x2="67" y2="48" stroke="#00d4ff" stroke-width="1.2" opacity="0.5" stroke-linecap="round"/>
          <line x1="45" y1="32" x2="45" y2="26" stroke="#00d4ff" stroke-width="1.2" opacity="0.5" stroke-linecap="round"/>
          <line x1="45" y1="64" x2="45" y2="70" stroke="#00d4ff" stroke-width="1.2" opacity="0.5" stroke-linecap="round"/>
          <circle cx="23" cy="48" r="1.5" fill="#00d4ff" opacity="0.5"/>
          <circle cx="67" cy="48" r="1.5" fill="#00d4ff" opacity="0.5"/>
          <circle cx="45" cy="26" r="1.5" fill="#00d4ff" opacity="0.5"/>
          <circle cx="45" cy="70" r="1.5" fill="#00d4ff" opacity="0.5"/>
        </svg>
      </div>
      <h2 class="empty-title">No threats detected — All systems secure</h2>
      <p class="empty-sub">
        Events ingested and detection rules are running smoothly.<br>
        New detections will appear here in real time.
      </p>
    </div>
  {:else}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Rule</th>
            <th>Severity</th>
            <th>Tactic</th>
            <th>Technique</th>
            <th>Events</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each detections as d}
            <tr>
              <td class="mono ts">{fmtTime(d.fired_at)}</td>
              <td class="rule-name">
                {d.rule_name}
                {#if d.explanation}
                  <span class="info-tip" title={d.explanation}>
                    <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
                      <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.4"/>
                      <line x1="8" y1="7" x2="8" y2="11" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
                      <circle cx="8" cy="5" r="0.8" fill="currentColor"/>
                    </svg>
                  </span>
                {/if}
              </td>
              <td><span class={severityClass(d.severity)}>{d.severity}</span></td>
              <td class="tactic">
                {#if d.attack_tactic}
                  <span class="tactic-text">{d.attack_tactic}</span>
                {:else}
                  <span class="muted">—</span>
                {/if}
              </td>
              <td class="mono technique">
                {#if d.attack_technique}
                  <span class="technique-badge" title={d.attack_tactic ?? ''}>{d.attack_technique}</span>
                {:else}
                  <span class="muted">—</span>
                {/if}
              </td>
              <td class="event-count">{getEventCount(d)}</td>
              <td>
                {#if onInvestigate}
                  <button
                    class="btn-investigate"
                    onclick={() => onInvestigate!(getDetectionId(d))}
                    disabled={!getDetectionId(d)}
                  >
                    Investigate →
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

  /* ── Triage panel ── */
  .triage-panel {
    flex-shrink: 0;
    border-bottom: 1px solid var(--border);
    background: rgba(0,212,255,0.03);
  }

  .triage-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 18px;
    cursor: pointer;
    user-select: none;
  }

  .triage-header:hover { background: rgba(255,255,255,0.02); }

  .triage-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    flex: 1;
  }

  .triage-running {
    font-weight: 400;
    color: var(--accent-cyan, #00d4ff);
    font-size: 12px;
  }

  .triage-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid var(--border);
    border-top-color: var(--accent-cyan, #00d4ff);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    flex-shrink: 0;
  }

  .collapse-icon {
    font-size: 10px;
    color: var(--text-muted);
  }

  .triage-body {
    padding: 4px 18px 10px;
  }

  .triage-summary {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .triage-summary strong {
    font-size: 13px;
    color: var(--text-primary);
  }

  .triage-meta {
    font-size: 11px;
    color: var(--text-muted);
  }

  .triage-empty {
    font-size: 12px;
    color: var(--text-muted);
  }

  .btn-sm {
    font-size: 11px;
    padding: 3px 10px;
    height: 26px;
  }

  /* ── KPI bar ── */
  .kpi-bar {
    display: flex;
    align-items: center;
    gap: 0;
    padding: 0 18px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
    flex-shrink: 0;
    flex-wrap: wrap;
    min-height: 54px;
  }

  .kpi-group { display: flex; align-items: center; gap: 6px; padding: 10px 0; }
  .kpi-divider {
    width: 1px;
    height: 28px;
    background: var(--border);
    margin: 0 14px;
    flex-shrink: 0;
  }

  /* Severity pills */
  .severity-pill {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px 5px 9px;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: var(--bg-tertiary);
    position: relative;
    overflow: hidden;
    cursor: default;
    transition: border-color 0.2s;
  }

  .sev-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .sev-count {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }

  .sev-label { font-size: 11px; color: var(--text-secondary); }

  .sev-underline {
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 2px;
    border-radius: 0 0 20px 20px;
    opacity: 0.5;
  }

  .severity-pill.critical .sev-dot      { background: var(--severity-critical); box-shadow: 0 0 4px var(--severity-critical); }
  .severity-pill.critical .sev-underline { background: var(--severity-critical); }
  .severity-pill.critical.alert          { border-color: rgba(239,68,68,0.5); }

  .severity-pill.high .sev-dot          { background: var(--severity-high); box-shadow: 0 0 4px var(--severity-high); }
  .severity-pill.high .sev-underline    { background: var(--severity-high); }
  .severity-pill.high.alert             { border-color: rgba(249,115,22,0.5); }

  .severity-pill.medium .sev-dot        { background: var(--severity-medium); box-shadow: 0 0 4px var(--severity-medium); }
  .severity-pill.medium .sev-underline  { background: var(--severity-medium); }
  .severity-pill.medium.alert           { border-color: rgba(234,179,8,0.5); }

  .severity-pill.low .sev-dot           { background: var(--severity-low); }
  .severity-pill.low .sev-underline     { background: var(--severity-low); }

  /* Operational stats */
  .ops-group { gap: 16px; }

  .kpi-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    cursor: default;
  }

  .kpi-value {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
  }
  .kpi-value.ok   { color: var(--accent-green); font-size: 12px; font-weight: 600; }
  .kpi-value.warn { color: var(--accent-red);   font-size: 12px; font-weight: 600; }
  .kpi-value.muted { color: var(--text-muted); }

  .kpi-key {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: var(--text-muted);
    white-space: nowrap;
  }

  /* Actions */
  .kpi-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
    padding: 10px 0;
  }

  .last-updated {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    white-space: nowrap;
  }

  .severity-select {
    height: 32px;
    font-size: 12px;
    padding: 0 8px;
    border-radius: var(--radius-md);
  }

  /* ── States ── */
  .state-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
  }

  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--border);
    border-top-color: var(--accent-cyan);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .state-text { font-size: 13px; color: var(--text-secondary); }

  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 18px;
    padding: 40px;
  }

  .empty-icon { filter: drop-shadow(0 0 18px rgba(0,212,255,0.2)); }

  .empty-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.3px;
  }

  .empty-sub {
    font-size: 13px;
    color: var(--text-secondary);
    text-align: center;
    line-height: 1.7;
  }

  /* ── Table ── */
  .table-wrap { flex: 1; overflow-y: auto; }

  .ts { color: var(--text-secondary); font-size: 11px; white-space: nowrap; }
  .rule-name { font-weight: 500; }
  .muted { color: var(--text-muted); }
  .event-count { text-align: center; color: var(--text-secondary); }

  .tactic { font-size: 11px; }
  .tactic-text {
    color: var(--text-secondary);
    font-style: italic;
  }

  .info-tip {
    cursor: help;
    color: var(--text-muted);
    margin-left: 4px;
    vertical-align: middle;
    display: inline-flex;
  }
  .info-tip:hover { color: var(--text-secondary); }

  .technique { font-size: 11px; }
  .technique-badge {
    background: rgba(167,139,250,0.12);
    color: #a78bfa;
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 4px;
    font-family: var(--font-mono, monospace);
    border: 1px solid rgba(167,139,250,0.2);
  }

  .btn-investigate {
    font-size: 11px;
    padding: 4px 10px;
    background: rgba(0,212,255,0.07);
    color: var(--accent-cyan);
    border: 1px solid rgba(0,212,255,0.2);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-family: var(--font-sans);
    font-weight: 500;
    transition: background 0.12s, border-color 0.12s;
    white-space: nowrap;
  }
  .btn-investigate:hover { background: rgba(0,212,255,0.14); border-color: rgba(0,212,255,0.4); }
  .btn-investigate:disabled { opacity: 0.35; cursor: not-allowed; }

  .error-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 18px;
    background: rgba(239,68,68,0.08);
    color: var(--severity-critical);
    border-bottom: 1px solid rgba(239,68,68,0.2);
    font-size: 13px;
    flex-shrink: 0;
  }
</style>
