<script lang="ts">
  import { api, type PerfMetrics } from '../lib/api.ts'
  import ArcGauge from '../components/ArcGauge.svelte'

  let metrics = $state<PerfMetrics | null>(null)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let lastUpdated = $state<Date | null>(null)

  async function load() {
    try {
      metrics = await api.metrics.perf()
      lastUpdated = new Date()
      error = null
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  $effect(() => {
    load()
    const interval = setInterval(load, 5_000)
    return () => clearInterval(interval)
  })

  function fmtTime(d: Date | null): string {
    if (!d) return '—'
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }
</script>

<div class="perf-view">
  <div class="perf-header">
    <h2 class="perf-title">System Performance</h2>
    <span class="perf-updated">
      {#if loading && !metrics}
        Loading…
      {:else}
        Last updated {fmtTime(lastUpdated)}
        <span class="refresh-dot" class:pulse={!loading}></span>
      {/if}
    </span>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if metrics}
    <!-- ── SOC Brain panel ──────────────────────────────────────── -->
    <div class="machine-panel">
      <div class="panel-header">
        <span class="panel-icon">🖥️</span>
        <div>
          <h3 class="panel-name">SOC Brain</h3>
          <p class="panel-sub">This machine · AI-SOC-Brain backend</p>
        </div>
        <span class="panel-badge badge-online">online</span>
      </div>

      <div class="gauge-row">
        <div class="gauge-cell">
          <ArcGauge
            value={metrics.soc_brain.cpu_pct}
            label="CPU"
            size={180}
          />
        </div>
        <div class="gauge-cell">
          <ArcGauge
            value={metrics.soc_brain.ram_pct}
            label="RAM"
            detail={metrics.soc_brain.ram_detail}
            size={180}
          />
        </div>
        <div class="gauge-cell">
          <ArcGauge
            value={metrics.soc_brain.disk_pct}
            label="DISK"
            detail={metrics.soc_brain.disk_detail}
            size={180}
          />
        </div>
      </div>
    </div>

    <!-- ── GMKtec / Malcolm panel ──────────────────────────────── -->
    <div class="machine-panel">
      <div class="panel-header">
        <span class="panel-icon">🔬</span>
        <div>
          <h3 class="panel-name">GMKtec / Malcolm</h3>
          <p class="panel-sub">192.168.1.22 · Malcolm NSM · OpenSearch node</p>
        </div>
        {#if metrics.gmktec.cpu_pct !== null}
          <span class="panel-badge badge-online">online</span>
        {:else}
          <span class="panel-badge badge-offline">unreachable</span>
        {/if}
      </div>

      <div class="gauge-row">
        <div class="gauge-cell">
          <ArcGauge
            value={metrics.gmktec.cpu_pct}
            label="CPU"
            size={180}
            nullLabel="N/A"
          />
        </div>
        <div class="gauge-cell">
          <ArcGauge
            value={metrics.gmktec.heap_pct}
            label="HEAP"
            detail={metrics.gmktec.heap_detail}
            size={180}
            nullLabel="N/A"
          />
        </div>
        <div class="gauge-cell">
          <ArcGauge
            value={metrics.gmktec.disk_pct}
            label="DISK"
            detail={metrics.gmktec.disk_detail}
            size={180}
            nullLabel="N/A"
          />
        </div>
      </div>

      {#if metrics.gmktec.cpu_pct === null}
        <p class="panel-note">
          Malcolm OpenSearch is unreachable — ensure <code>MALCOLM_ENABLED=True</code> and
          the GMKtec is powered on.
        </p>
      {/if}
    </div>

  {:else if loading}
    <div class="loading-wrap">
      <div class="spinner"></div>
      <span>Loading metrics…</span>
    </div>
  {/if}
</div>

<style>
  .perf-view {
    height: 100%;
    overflow-y: auto;
    padding: 24px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  /* ── Header ── */
  .perf-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
  }

  .perf-title {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
  }

  .perf-updated {
    font-size: 12px;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .refresh-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: rgba(34,197,94,0.4);
  }

  .refresh-dot.pulse {
    background: #22c55e;
    animation: blink 2s ease-in-out infinite;
  }

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.3; }
  }

  /* ── Error ── */
  .error-banner {
    padding: 10px 14px;
    background: rgba(239,68,68,0.08);
    color: #ef4444;
    border: 1px solid rgba(239,68,68,0.2);
    border-radius: 6px;
    font-size: 13px;
  }

  /* ── Machine panel ── */
  .machine-panel {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px 24px;
  }

  .panel-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
  }

  .panel-icon {
    font-size: 24px;
    line-height: 1;
  }

  .panel-name {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0 0 2px 0;
  }

  .panel-sub {
    font-size: 11px;
    color: var(--text-muted);
    margin: 0;
  }

  .panel-badge {
    margin-left: auto;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }

  .badge-online  { background: rgba(34,197,94,0.12);  color: #22c55e; border: 1px solid rgba(34,197,94,0.25); }
  .badge-offline { background: rgba(239,68,68,0.10);  color: #f87171; border: 1px solid rgba(239,68,68,0.2);  }

  /* ── Gauge row ── */
  .gauge-row {
    display: flex;
    justify-content: center;
    gap: 32px;
    flex-wrap: wrap;
  }

  .gauge-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  /* ── Offline note ── */
  .panel-note {
    margin: 16px 0 0 0;
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
  }

  .panel-note code {
    font-family: var(--font-mono, monospace);
    background: rgba(255,255,255,0.06);
    padding: 1px 5px;
    border-radius: 3px;
  }

  /* ── Loading ── */
  .loading-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    height: 200px;
    color: var(--text-muted);
    font-size: 13px;
  }

  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--border);
    border-top-color: var(--accent-cyan, #00d4ff);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }
</style>
