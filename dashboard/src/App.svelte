<script lang="ts">
  import { onMount } from 'svelte'
  import './app.css'
  import { api } from './lib/api.ts'
  import EventsView from './views/EventsView.svelte'
  import DetectionsView from './views/DetectionsView.svelte'
  import GraphView from './views/GraphView.svelte'
  import QueryView from './views/QueryView.svelte'
  import IngestView from './views/IngestView.svelte'

  type View = 'events' | 'detections' | 'graph' | 'query' | 'ingest'

  let currentView = $state<View>('detections')
  let healthStatus = $state<'healthy' | 'degraded' | 'unhealthy' | 'loading'>('loading')

  onMount(async () => {
    try {
      const h = await api.health()
      healthStatus = h.status
    } catch {
      healthStatus = 'unhealthy'
    }
    // Re-check every 30s
    setInterval(async () => {
      try {
        const h = await api.health()
        healthStatus = h.status
      } catch {
        healthStatus = 'unhealthy'
      }
    }, 30_000)
  })

  const nav = [
    { id: 'detections', label: 'Detections', icon: '⚡' },
    { id: 'events',     label: 'Events',     icon: '📋' },
    { id: 'graph',      label: 'Graph',      icon: '🔗' },
    { id: 'query',      label: 'AI Query',   icon: '🤖' },
    { id: 'ingest',     label: 'Ingest',     icon: '📥' },
  ] as const

  const statusColor = {
    healthy: 'var(--accent-green)',
    degraded: 'var(--accent-yellow)',
    unhealthy: 'var(--accent-red)',
    loading: 'var(--text-muted)',
  }
</script>

<div class="app-shell">
  <!-- Sidebar -->
  <nav class="sidebar">
    <div class="sidebar-header">
      <span class="logo">🧠 SOC Brain</span>
      <span class="health-dot" style="background: {statusColor[healthStatus]}" title="Backend: {healthStatus}"></span>
    </div>

    <ul class="nav-list">
      {#each nav as item}
        <li>
          <button
            class="nav-item"
            class:active={currentView === item.id}
            onclick={() => currentView = item.id}
          >
            <span class="nav-icon">{item.icon}</span>
            <span class="nav-label">{item.label}</span>
          </button>
        </li>
      {/each}
    </ul>

    <div class="sidebar-footer">
      <span class="version">v0.1.0</span>
    </div>
  </nav>

  <!-- Main content -->
  <main class="main-content">
    {#if currentView === 'detections'}
      <DetectionsView />
    {:else if currentView === 'events'}
      <EventsView />
    {:else if currentView === 'graph'}
      <GraphView />
    {:else if currentView === 'query'}
      <QueryView />
    {:else if currentView === 'ingest'}
      <IngestView />
    {/if}
  </main>
</div>

<style>
  .app-shell {
    display: flex;
    height: 100vh;
    overflow: hidden;
  }

  .sidebar {
    width: 200px;
    flex-shrink: 0;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
  }

  .sidebar-header {
    padding: 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .logo {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.3px;
  }

  .health-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    transition: background 0.3s;
  }

  .nav-list {
    list-style: none;
    padding: 8px 0;
    flex: 1;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 16px;
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 13px;
    font-family: var(--font-sans);
    cursor: pointer;
    text-align: left;
    transition: background 0.1s, color 0.1s;
    border-radius: 0;
  }

  .nav-item:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .nav-item.active {
    background: rgba(88, 166, 255, 0.1);
    color: var(--accent-blue);
    border-right: 2px solid var(--accent-blue);
  }

  .nav-icon { font-size: 15px; }

  .sidebar-footer {
    padding: 12px 16px;
    border-top: 1px solid var(--border);
  }

  .version {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .main-content {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
</style>
