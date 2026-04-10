<script lang="ts">
  import { api, type TelemetrySummary, type TriageResult } from '../lib/api.ts'

  let {
    healthStatus,
    networkDevices,
  }: {
    healthStatus: string
    networkDevices: Record<string, string>
  } = $props()

  let summary = $state<TelemetrySummary | null>(null)
  let triageResult = $state<TriageResult | null>(null)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let triageExpanded = $state(false)

  const maxCount = $derived(
    summary
      ? Math.max(1, ...Object.values(summary.event_type_counts))
      : 1
  )

  async function load() {
    try {
      const [summaryData, triageData] = await Promise.all([
        api.telemetry.summary(),
        api.triage.latest(),
      ])
      summary = summaryData
      triageResult = triageData.result
      error = null
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  $effect(() => {
    load()
    const interval = setInterval(load, 60_000)
    return () => clearInterval(interval)
  })

  function fmtTime(ts: string) {
    try {
      return new Date(ts).toLocaleString('en-US', {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    } catch {
      return ts
    }
  }

  function severityBadgeClass(sev: string) {
    return `badge badge-${sev.toLowerCase()}`
  }
</script>

<div class="overview">
  {#if loading}
    <div class="loading-wrap">
      <div class="spinner"></div>
      <span class="loading-text">Loading overview…</span>
    </div>
  {:else}
    {#if error}
      <div class="error-banner">{error}</div>
    {/if}

    <div class="overview-grid">
      <!-- Left column -->
      <div class="col-left">

        <!-- Block 1: EVE Type Bar Chart -->
        <div class="card">
          <h3 class="card-title">EVE Type Breakdown <span class="card-sub">last 24h</span></h3>
          {#if !summary || Object.keys(summary.event_type_counts).length === 0}
            <p class="empty-msg">No events in last 24h</p>
          {:else}
            <div class="bar-chart">
              {#each Object.entries(summary.event_type_counts) as [evType, count]}
                <div class="bar-row">
                  <span class="bar-label">{evType}</span>
                  <div class="bar-track">
                    <div
                      class="bar-fill"
                      style="width: {(count / maxCount * 100).toFixed(1)}%"
                    ></div>
                  </div>
                  <span class="bar-count">{count}</span>
                </div>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Block 2: Scorecard row -->
        <div class="card scorecard-card">
          <div class="scorecard-row">
            <div class="scorecard-tile">
              <span class="tile-value">{summary?.total_events ?? 0}</span>
              <span class="tile-label">Total Events</span>
            </div>
            <div class="scorecard-tile">
              <span class="tile-value">{summary?.total_detections ?? 0}</span>
              <span class="tile-label">Detections</span>
            </div>
            <div class="scorecard-tile">
              <span class="tile-value tile-ioc">{summary?.ioc_matches ?? 0}</span>
              <span class="tile-label">IOC Matches</span>
            </div>
            <div class="scorecard-tile">
              <span class="tile-value">{summary?.assets_count ?? 0}</span>
              <span class="tile-label">Assets</span>
            </div>
          </div>
        </div>

      </div>

      <!-- Right column -->
      <div class="col-right">

        <!-- Block 3: System health -->
        <div class="card">
          <h3 class="card-title">System Health</h3>
          <div class="health-list">
            <div class="health-row">
              <span
                class="health-dot"
                class:dot-healthy={healthStatus === 'healthy'}
                class:dot-degraded={healthStatus === 'degraded'}
                class:dot-unhealthy={healthStatus === 'unhealthy' || healthStatus === 'loading'}
              ></span>
              <span class="health-label">API Backend</span>
              <span class="health-status">{healthStatus}</span>
            </div>
            {#each [['router','Router'],['firewall','Firewall'],['gmktec','GMKtec']] as [key, label]}
              {#if networkDevices[key] !== undefined}
                <div class="health-row">
                  <span
                    class="health-dot"
                    class:dot-healthy={networkDevices[key] === 'up'}
                    class:dot-unhealthy={networkDevices[key] === 'down'}
                  ></span>
                  <span class="health-label">{label}</span>
                  <span class="health-status">{networkDevices[key]}</span>
                </div>
              {/if}
            {/each}
          </div>
        </div>

        <!-- Block 4: Latest triage result -->
        <div class="card">
          <h3 class="card-title">Latest AI Triage</h3>
          {#if triageResult}
            <div class="triage-result">
              <div class="triage-summary-row">
                <strong class="triage-sev">{triageResult.severity_summary}</strong>
                <span class="triage-meta">
                  {triageResult.detection_count} detections
                  · {triageResult.model_name}
                  · {fmtTime(triageResult.created_at)}
                </span>
              </div>
              <button
                class="expand-btn"
                onclick={() => triageExpanded = !triageExpanded}
              >
                {triageExpanded ? 'Collapse' : 'View full analysis'} {triageExpanded ? '▲' : '▼'}
              </button>
              {#if triageExpanded}
                <pre class="triage-text">{triageResult.result_text}</pre>
              {/if}
            </div>
          {:else}
            <p class="empty-msg">No triage results yet.</p>
          {/if}
        </div>

        <!-- Block 5: Top detected rules -->
        <div class="card">
          <h3 class="card-title">Top Detected Rules <span class="card-sub">last 24h</span></h3>
          {#if !summary || summary.top_rules.length === 0}
            <p class="empty-msg">No detections in last 24h</p>
          {:else}
            <table class="rules-table">
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>Count</th>
                  <th>Severity</th>
                </tr>
              </thead>
              <tbody>
                {#each summary.top_rules as rule}
                  <tr>
                    <td class="rule-name">{rule.rule_name}</td>
                    <td class="rule-count">{rule.count}</td>
                    <td><span class={severityBadgeClass(rule.severity)}>{rule.severity}</span></td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </div>

      </div>
    </div>
  {/if}
</div>

<style>
  .overview {
    height: 100%;
    overflow-y: auto;
    padding: 20px;
    box-sizing: border-box;
  }

  /* ── Loading ── */
  .loading-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    height: 200px;
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

  .loading-text { font-size: 13px; color: var(--text-secondary); }

  /* ── Error ── */
  .error-banner {
    padding: 10px 14px;
    background: rgba(239,68,68,0.08);
    color: var(--severity-critical, #ef4444);
    border: 1px solid rgba(239,68,68,0.2);
    border-radius: var(--radius-md, 6px);
    font-size: 13px;
    margin-bottom: 16px;
  }

  /* ── Grid ── */
  .overview-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    align-items: start;
  }

  @media (max-width: 900px) {
    .overview-grid { grid-template-columns: 1fr; }
  }

  .col-left, .col-right {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  /* ── Card ── */
  .card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md, 8px);
    padding: 16px;
  }

  .card-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 12px 0;
  }

  .card-sub {
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 400;
    margin-left: 6px;
  }

  .empty-msg {
    font-size: 13px;
    color: var(--text-muted);
    margin: 0;
  }

  /* ── Bar chart ── */
  .bar-chart {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .bar-row {
    display: grid;
    grid-template-columns: 90px 1fr 48px;
    align-items: center;
    gap: 8px;
  }

  .bar-label {
    font-size: 12px;
    color: var(--text-secondary);
    text-align: right;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-transform: capitalize;
  }

  .bar-track {
    height: 10px;
    background: rgba(255,255,255,0.05);
    border-radius: 4px;
    overflow: hidden;
  }

  .bar-fill {
    height: 100%;
    background: var(--accent-cyan, #00d4ff);
    border-radius: 4px;
    min-width: 2px;
    transition: width 0.4s ease;
  }

  .bar-count {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }

  /* ── Scorecard ── */
  .scorecard-card { padding: 12px 16px; }

  .scorecard-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
  }

  .scorecard-tile {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 10px 6px;
    background: var(--bg-tertiary, rgba(255,255,255,0.03));
    border-radius: 6px;
    border: 1px solid var(--border);
    gap: 3px;
  }

  .tile-value {
    font-size: 22px;
    font-weight: 700;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }

  .tile-ioc { color: var(--severity-high, #f97316); }

  .tile-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
    text-align: center;
    line-height: 1.3;
  }

  /* ── Health ── */
  .health-list { display: flex; flex-direction: column; gap: 8px; }

  .health-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .health-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgba(255,255,255,0.15);
    flex-shrink: 0;
  }

  .health-dot.dot-healthy   { background: #22c55e; }
  .health-dot.dot-degraded  { background: #eab308; }
  .health-dot.dot-unhealthy { background: #ef4444; }

  .health-label {
    font-size: 13px;
    color: var(--text-secondary);
    flex: 1;
  }

  .health-status {
    font-size: 12px;
    color: var(--text-muted);
    text-transform: capitalize;
  }

  /* ── Triage result ── */
  .triage-result { display: flex; flex-direction: column; gap: 8px; }

  .triage-summary-row { display: flex; flex-direction: column; gap: 4px; }

  .triage-sev { font-size: 14px; color: var(--text-primary); }

  .triage-meta {
    font-size: 11px;
    color: var(--text-muted);
  }

  .expand-btn {
    font-size: 11px;
    color: var(--accent-cyan, #00d4ff);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
    text-align: left;
    font-family: var(--font-sans);
  }

  .expand-btn:hover { opacity: 0.8; }

  .triage-text {
    font-size: 12px;
    color: var(--text-secondary);
    font-family: var(--font-mono, monospace);
    white-space: pre-wrap;
    word-break: break-word;
    background: var(--bg-tertiary, rgba(255,255,255,0.03));
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px;
    margin: 0;
    max-height: 300px;
    overflow-y: auto;
  }

  /* ── Top rules table ── */
  .rules-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  .rules-table th {
    text-align: left;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: var(--text-muted);
    padding: 0 8px 6px 0;
    border-bottom: 1px solid var(--border);
  }

  .rules-table td {
    padding: 6px 8px 6px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    color: var(--text-secondary);
  }

  .rule-name { font-weight: 500; color: var(--text-primary); }
  .rule-count { font-variant-numeric: tabular-nums; text-align: right; padding-right: 12px; }
</style>
