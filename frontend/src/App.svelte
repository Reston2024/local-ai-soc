<script lang="ts">
  import { onMount } from 'svelte'
  import ThreatGraph from './components/graph/ThreatGraph.svelte'
  import EventTimeline from './components/timeline/EventTimeline.svelte'
  import EvidencePanel from './components/panels/EvidencePanel.svelte'

  let health = $state<{status:string}|null>(null)
  let alerts = $state<any[]>([])
  let selectedNode = $state<any>(null)

  onMount(async () => {
    try {
      const r = await fetch('/health')
      health = await r.json()
    } catch { health = { status: 'error' } }
    try {
      const r = await fetch('/alerts')
      alerts = await r.json()
    } catch {}
  })

  async function loadFixtures() {
    await fetch('/fixtures/load', { method: 'POST' })
    const r = await fetch('/alerts')
    alerts = await r.json()
  }
</script>

<div class="soc-layout">
  <!-- Status Bar -->
  <header class="status-bar">
    <span class="title">AI SOC Brain — Wave 1</span>
    <span class="health">
      <span class="dot {health?.status === 'ok' ? 'dot-green' : 'dot-red'}"></span>
      {health?.status ?? 'connecting...'}
    </span>
    <span class="alert-count">{alerts.length} alerts</span>
    <button onclick={loadFixtures}>Load Fixtures</button>
  </header>

  <div class="main-content">
    <!-- Left Rail -->
    <aside class="left-rail card">
      <h3>Alerts</h3>
      {#each alerts.slice(0, 20) as alert}
        <div class="alert-item">
          <span class="badge badge-{alert.severity}">{alert.severity}</span>
          <span class="rule">{alert.rule}</span>
        </div>
      {/each}
      {#if alerts.length === 0}
        <p class="muted">No alerts</p>
      {/if}
    </aside>

    <!-- Center Graph -->
    <main class="center-panel">
      <ThreatGraph onNodeSelect={(n: any) => selectedNode = n} />
    </main>

    <!-- Right Evidence Panel -->
    <EvidencePanel selected={selectedNode} />
  </div>

  <!-- Bottom Timeline -->
  <footer class="timeline-bar">
    <EventTimeline />
  </footer>
</div>

<style>
  .soc-layout { height: 100vh; display: flex; flex-direction: column; }
  .status-bar { display: flex; align-items: center; gap: 16px; padding: 8px 16px; background: var(--surface); border-bottom: 1px solid var(--border); flex-shrink: 0; }
  .title { font-weight: 700; color: var(--accent); }
  .health { display: flex; align-items: center; gap: 6px; }
  .alert-count { color: var(--warn); font-weight: 600; margin-left: auto; }
  .main-content { flex: 1; display: flex; overflow: hidden; }
  .left-rail { width: 220px; flex-shrink: 0; overflow-y: auto; border-radius: 0; border-top: none; border-bottom: none; border-left: none; }
  .left-rail h3 { margin-bottom: 8px; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
  .alert-item { display: flex; align-items: center; gap: 6px; padding: 4px 0; border-bottom: 1px solid var(--border); }
  .rule { font-size: 11px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .muted { color: var(--muted); font-size: 11px; }
  .center-panel { flex: 1; overflow: hidden; }
  .timeline-bar { height: 140px; flex-shrink: 0; border-top: 1px solid var(--border); }
</style>
