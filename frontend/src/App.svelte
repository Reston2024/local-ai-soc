<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import ThreatGraph from './components/graph/ThreatGraph.svelte'
  import EventTimeline from './components/timeline/EventTimeline.svelte'
  import EvidencePanel from './components/panels/EvidencePanel.svelte'
  import { getHealth, getAlerts, loadFixtures } from './lib/api'

  // ── State (Svelte 5 runes) ──────────────────────────────────────────────
  let health = $state<{ status: string; ingestion_sources?: string[] } | null>(null)
  let alerts = $state<any[]>([])
  let selectedNode = $state<any>(null)
  let lastRefresh = $state<Date | null>(null)
  let ingestSources = $state<string[]>([])

  // ── Polling ────────────────────────────────────────────────────────────
  // Graph (ThreatGraph) and Timeline (EventTimeline) each poll internally.
  // App.svelte polls alerts + health so the status bar stays current.
  let pollTimer: ReturnType<typeof setInterval>

  async function pollStatus() {
    try {
      const h = await getHealth()
      health = h
      ingestSources = h.ingestion_sources ?? []
    } catch {
      health = { status: 'error' }
    }
    try {
      alerts = await getAlerts()
    } catch {}
    lastRefresh = new Date()
  }

  async function handleLoadFixtures() {
    await loadFixtures()
    await pollStatus()
  }

  onMount(async () => {
    await pollStatus()
    pollTimer = setInterval(pollStatus, 10_000)
  })

  onDestroy(() => clearInterval(pollTimer))

  // ── Derived ────────────────────────────────────────────────────────────
  const highAlerts = $derived(alerts.filter(a => a.severity === 'high' || a.severity === 'critical'))
  const refreshLabel = $derived(
    lastRefresh
      ? lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      : '—'
  )
</script>

<div class="soc-layout">
  <!-- Status Bar -->
  <header class="status-bar">
    <span class="title">AI SOC Brain — Phase 2</span>

    <!-- Health indicator -->
    <span class="health">
      <span class="dot {health?.status === 'ok' ? 'dot-green' : 'dot-red'}"></span>
      {health?.status ?? 'connecting…'}
    </span>

    <!-- Live ingestion sources -->
    {#if ingestSources.length > 0}
      <span class="sources" title="Active ingestion sources this session">
        {#each ingestSources as src}
          <span class="source-badge">{src}</span>
        {/each}
      </span>
    {/if}

    <!-- Alert counts -->
    <span class="alert-count">
      {#if highAlerts.length > 0}
        <span class="dot dot-red"></span>
      {/if}
      {alerts.length} alerts
      {#if highAlerts.length > 0}
        <span class="high-badge">({highAlerts.length} high)</span>
      {/if}
    </span>

    <!-- Refresh timestamp -->
    <span class="refresh-time" title="Last poll">↻ {refreshLabel}</span>

    <button onclick={handleLoadFixtures}>Load Fixtures</button>
  </header>

  <div class="main-content">
    <!-- Left Rail — Alert feed -->
    <aside class="left-rail card">
      <h3>Alerts</h3>
      {#each alerts.slice(0, 30) as alert}
        <div class="alert-item">
          <span class="badge badge-{alert.severity}">{alert.severity}</span>
          <span class="rule">{alert.rule}</span>
        </div>
      {/each}
      {#if alerts.length === 0}
        <p class="muted">No alerts — load fixtures or send live events</p>
      {/if}
      {#if alerts.length > 30}
        <p class="muted">+{alerts.length - 30} more…</p>
      {/if}
    </aside>

    <!-- Center — Threat Graph (polls /graph every 10s internally) -->
    <main class="center-panel">
      <ThreatGraph onNodeSelect={(n: any) => selectedNode = n} />
    </main>

    <!-- Right — Evidence Panel -->
    <EvidencePanel selected={selectedNode} />
  </div>

  <!-- Bottom — Event Timeline (polls /timeline every 10s internally) -->
  <footer class="timeline-bar">
    <EventTimeline />
  </footer>
</div>

<style>
  .soc-layout { height: 100vh; display: flex; flex-direction: column; }

  .status-bar {
    display: flex; align-items: center; gap: 12px;
    padding: 6px 14px;
    background: var(--surface); border-bottom: 1px solid var(--border);
    flex-shrink: 0; flex-wrap: wrap;
    font-size: 12px;
  }
  .title { font-weight: 700; color: var(--accent); }

  .health { display: flex; align-items: center; gap: 5px; }

  .sources { display: flex; gap: 4px; align-items: center; }
  .source-badge {
    background: #1e3a5f; color: #93c5fd;
    font-size: 10px; padding: 1px 5px; border-radius: 3px;
    text-transform: uppercase; letter-spacing: 0.5px;
  }

  .alert-count {
    display: flex; align-items: center; gap: 5px;
    color: var(--warn); font-weight: 600; margin-left: auto;
  }
  .high-badge { color: #ef4444; font-size: 11px; }

  .refresh-time { color: var(--muted); font-size: 10px; }

  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
  .dot-green { background: #10b981; box-shadow: 0 0 6px #10b981; }
  .dot-red   { background: #ef4444; box-shadow: 0 0 6px #ef4444; }

  .main-content { flex: 1; display: flex; overflow: hidden; }

  .left-rail {
    width: 230px; flex-shrink: 0; overflow-y: auto;
    border-radius: 0; border-top: none; border-bottom: none; border-left: none;
  }
  .left-rail h3 {
    margin-bottom: 8px; color: var(--muted);
    font-size: 10px; text-transform: uppercase; letter-spacing: 1px;
  }
  .alert-item {
    display: flex; align-items: center; gap: 5px;
    padding: 3px 0; border-bottom: 1px solid var(--border);
  }
  .rule { font-size: 10px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .muted { color: var(--muted); font-size: 10px; margin-top: 6px; }

  .center-panel { flex: 1; overflow: hidden; }
  .timeline-bar { height: 140px; flex-shrink: 0; border-top: 1px solid var(--border); }
</style>
