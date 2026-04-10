<script lang="ts">
  import { onMount } from 'svelte'
  import './app.css'
  import { api } from './lib/api.ts'
  import EventsView from './views/EventsView.svelte'
  import DetectionsView from './views/DetectionsView.svelte'
  import GraphView from './views/GraphView.svelte'
  import QueryView from './views/QueryView.svelte'
  import IngestView from './views/IngestView.svelte'
  import InvestigationPanel from './components/InvestigationPanel.svelte'
  import InvestigationView from './views/InvestigationView.svelte'
  import ThreatIntelView from './views/ThreatIntelView.svelte'
  import HuntingView from './views/HuntingView.svelte'
  import PlaybooksView from './views/PlaybooksView.svelte'
  import ReportsView from './views/ReportsView.svelte'
  import AssetsView from './views/AssetsView.svelte'
  import ProvenanceView from './views/ProvenanceView.svelte'
  import RecommendationsView from './views/RecommendationsView.svelte'
  import SettingsView from './views/SettingsView.svelte'
  import MapView from './views/MapView.svelte'

  type View =
    | 'detections' | 'investigation' | 'events' | 'graph' | 'query' | 'ingest'
    | 'intel' | 'hunting' | 'playbooks' | 'reports' | 'assets' | 'provenance'
    | 'recommendations' | 'settings' | 'map'

  let currentView = $state<View>('detections')
  let healthStatus = $state<'healthy' | 'degraded' | 'unhealthy' | 'loading'>('loading')
  let investigatingId = $state<string>('')
  let graphFocusEntityId = $state<string>('')
  let postureScore = $state(100) // 0–100; updated once detections load

  function handleInvestigate(detectionId: string) {
    investigatingId = detectionId
    currentView = 'investigation'
  }

  function handleOpenInGraph(entityId: string) {
    graphFocusEntityId = entityId
    currentView = 'graph'
  }

  function handleNavigateInvestigation(investigationId: string) {
    investigatingId = investigationId
    currentView = 'investigation'
  }

  let playbookInvestigationId = $state<string>('')

  function handleRunPlaybook(investigationId: string) {
    playbookInvestigationId = investigationId
    currentView = 'playbooks'
  }

  // Scroll active nav item into view whenever currentView changes
  $effect(() => {
    const _view = currentView  // track dependency
    requestAnimationFrame(() => {
      document.querySelector('.nav-item.active')?.scrollIntoView({ block: 'nearest' })
    })
  })

  function handlePostureUpdate(score: number) {
    postureScore = score
  }

  onMount(async () => {
    try {
      const h = await api.health()
      healthStatus = h.status
    } catch {
      healthStatus = 'unhealthy'
    }
    setInterval(async () => {
      try {
        const h = await api.health()
        healthStatus = h.status
      } catch {
        healthStatus = 'unhealthy'
      }
    }, 30_000)
  })

  // Posture: green ≥ 80, amber 50–79, red < 50
  const postureLabel = $derived(
    postureScore >= 80 ? 'Secure' : postureScore >= 50 ? 'Elevated Risk' : 'Critical Risk'
  )
  const postureColor = $derived(
    postureScore >= 80 ? '#22c55e' : postureScore >= 50 ? '#eab308' : '#ef4444'
  )

  const statusColor: Record<string, string> = {
    healthy:   '#22c55e',
    degraded:  '#eab308',
    unhealthy: '#ef4444',
    loading:   '#4a5d7a',
  }

  type NavGroup = {
    label: string
    items: { id: View; label: string; color: string; beta?: boolean }[]
  }

  const navGroups: NavGroup[] = [
    {
      label: 'Monitor',
      items: [
        { id: 'detections',   label: 'Detections',   color: '' },
        { id: 'events',       label: 'Events',        color: '' },
        { id: 'assets',       label: 'Assets',        color: '' },
      ],
    },
    {
      label: 'Investigate',
      items: [
        { id: 'investigation', label: 'Investigation', color: '' },
        { id: 'graph',         label: 'Attack Graph',  color: '' },
        { id: 'provenance',    label: 'Provenance',    color: '' },
      ],
    },
    {
      label: 'Intelligence',
      items: [
        { id: 'intel',    label: 'Threat Intel', color: '', beta: true },
        { id: 'hunting',  label: 'Hunting',      color: '', beta: true },
        { id: 'map',      label: 'Threat Map',   color: '', beta: true },
      ],
    },
    {
      label: 'Respond',
      items: [
        { id: 'playbooks',       label: 'Playbooks',       color: '', beta: true },
        { id: 'recommendations', label: 'Recommendations', color: '', beta: true },
        { id: 'reports',         label: 'Reports',         color: '' },
      ],
    },
    {
      label: 'Platform',
      items: [
        { id: 'query',    label: 'AI Query',  color: '' },
        { id: 'ingest',   label: 'Ingest',    color: '' },
        { id: 'settings', label: 'Settings',  color: '' },
      ],
    },
  ]
</script>

<div class="app-shell">
  <!-- Sidebar -->
  <nav class="sidebar">
    <!-- Header -->
    <div class="sidebar-header">
      <div class="logo-row">
        <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
          <path d="M11 2L3 5.5V11C3 15.4 6.6 19.4 11 20.5C15.4 19.4 19 15.4 19 11V5.5L11 2Z"
            fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.35)" stroke-width="1.3"/>
          <circle cx="11" cy="11" r="3" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="1.1"/>
          <circle cx="11" cy="11" r="1.1" fill="rgba(255,255,255,0.7)"/>
        </svg>
        <span class="logo-text">SOC Brain</span>
      </div>
      <span
        class="health-dot"
        style="background: {statusColor[healthStatus]}"
        title="Backend: {healthStatus}"
      ></span>
    </div>

    <!-- Posture strip -->
    <div class="posture-strip">
      <span class="posture-label">Posture</span>
      <div class="posture-bar-bg">
        <div class="posture-bar-fill" style="width:{postureScore}%; background:{postureColor}"></div>
      </div>
      <span class="posture-num" style="color:{postureColor}">{postureScore}</span>
    </div>

    <!-- Nav -->
    <div class="nav-scroll">
      {#each navGroups as group}
        <div class="nav-group">
          <span class="nav-group-label">{group.label}</span>
          {#each group.items as item}
            <button
              class="nav-item"
              class:active={currentView === item.id}
              onclick={() => { currentView = item.id }}
            >
              <span class="nav-icon">
                {#if item.id === 'detections'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><path d="M9 1.5L3.5 9H7.5L7 14.5L12.5 7H8.5L9 1.5Z" fill="currentColor"/></svg>
                {:else if item.id === 'investigation'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="1.6"/><line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
                {:else if item.id === 'events'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><rect x="2" y="3" width="12" height="2" rx="1" fill="currentColor"/><rect x="2" y="7" width="12" height="2" rx="1" fill="currentColor"/><rect x="2" y="11" width="8" height="2" rx="1" fill="currentColor"/></svg>
                {:else if item.id === 'graph'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="2" fill="currentColor"/><circle cx="2.5" cy="4" r="1.5" fill="currentColor"/><circle cx="13.5" cy="4" r="1.5" fill="currentColor"/><circle cx="8" cy="13.5" r="1.5" fill="currentColor"/><line x1="3.8" y1="5.2" x2="6.6" y2="7" stroke="currentColor" stroke-width="1.2"/><line x1="12.2" y1="5.2" x2="9.4" y2="7" stroke="currentColor" stroke-width="1.2"/><line x1="8" y1="10" x2="8" y2="12" stroke="currentColor" stroke-width="1.2"/></svg>
                {:else if item.id === 'assets'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><rect x="2" y="2" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/><rect x="9" y="2" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/><rect x="2" y="9" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/><rect x="9" y="9" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/></svg>
                {:else if item.id === 'provenance'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><path d="M4 14V9M8 14V5M12 14V2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
                {:else if item.id === 'intel'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><path d="M8 2a6 6 0 1 1 0 12A6 6 0 0 1 8 2Z" stroke="currentColor" stroke-width="1.4"/><path d="M8 5v3.5l2 1.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
                {:else if item.id === 'hunting'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><circle cx="7.5" cy="7.5" r="5" stroke="currentColor" stroke-width="1.4"/><line x1="7.5" y1="2.5" x2="7.5" y2="4.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><line x1="7.5" y1="10.5" x2="7.5" y2="12.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><line x1="2.5" y1="7.5" x2="4.5" y2="7.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><line x1="10.5" y1="7.5" x2="12.5" y2="7.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><circle cx="7.5" cy="7.5" r="1.5" fill="currentColor"/></svg>
                {:else if item.id === 'map'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.4"/><path d="M8 1.5C8 1.5 5 5 5 8a3 3 0 006 0c0-3-3-6.5-3-6.5z" stroke="currentColor" stroke-width="1.2"/><line x1="1.5" y1="8" x2="14.5" y2="8" stroke="currentColor" stroke-width="1" opacity="0.5"/></svg>
                {:else if item.id === 'playbooks'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><rect x="3" y="2" width="10" height="12" rx="1.5" stroke="currentColor" stroke-width="1.4"/><line x1="6" y1="6" x2="10" y2="6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><line x1="6" y1="9" x2="9" y2="9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
                {:else if item.id === 'recommendations'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><path d="M8 2.5a5.5 5.5 0 0 1 0 11 5.5 5.5 0 0 1 0-11z" stroke="currentColor" stroke-width="1.4"/><path d="M8 5.5v3h2.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
                {:else if item.id === 'reports'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><rect x="2" y="10" width="3" height="4" rx="1" fill="currentColor" opacity="0.45"/><rect x="6.5" y="6" width="3" height="8" rx="1" fill="currentColor" opacity="0.7"/><rect x="11" y="2" width="3" height="12" rx="1" fill="currentColor"/></svg>
                {:else if item.id === 'query'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><rect x="2.5" y="5" width="11" height="8" rx="2" stroke="currentColor" stroke-width="1.5"/><circle cx="6" cy="9" r="1" fill="currentColor"/><circle cx="10" cy="9" r="1" fill="currentColor"/><line x1="8" y1="5" x2="8" y2="2.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="8" cy="2" r="0.9" fill="currentColor"/></svg>
                {:else if item.id === 'ingest'}
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none"><line x1="8" y1="2" x2="8" y2="10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M5 7.5L8 11L11 7.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><line x1="3" y1="13" x2="13" y2="13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
                {:else if item.id === 'settings'}
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 15.5A3.5 3.5 0 0 1 8.5 12 3.5 3.5 0 0 1 12 8.5a3.5 3.5 0 0 1 3.5 3.5 3.5 3.5 0 0 1-3.5 3.5m7.43-2.92c.04-.33.07-.64.07-.97 0-.33-.03-.66-.07-1l2.11-1.63c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65C14.46 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1c-.23-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64L4.57 11c-.04.34-.07.67-.07 1 0 .33.03.65.07.97l-2.11 1.66c-.19.15-.25.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1.01c.52.4 1.08.73 1.69.98l.38 2.65c.03.24.24.42.49.42h4c.25 0 .46-.18.49-.42l.38-2.65c.61-.25 1.17-.58 1.69-.98l2.49 1.01c.22.08.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.66z"/></svg>
                {/if}
              </span>
              <span class="nav-label">{item.label}</span>
              {#if item.id === 'investigation' && investigatingId}
                <span class="inv-dot"></span>
              {/if}
              {#if item.beta}
                <span class="beta-tag">beta</span>
              {/if}
            </button>
          {/each}
        </div>
      {/each}
    </div>

    <div class="sidebar-footer">
      <span class="version">v0.1.0</span>
      <span class="footer-health" style="color:{statusColor[healthStatus]}">{healthStatus}</span>
    </div>
  </nav>

  <!-- Main content -->
  <main class="main-content">
    {#if currentView === 'detections'}
      <DetectionsView onInvestigate={handleInvestigate} onPostureUpdate={handlePostureUpdate} />
    {:else if currentView === 'investigation'}
      <InvestigationView
        investigationId={investigatingId}
        onOpenInGraph={handleOpenInGraph}
        onRunPlaybook={handleRunPlaybook}
      />
    {:else if currentView === 'events'}
      <EventsView />
    {:else if currentView === 'graph'}
      <GraphView
        focusEntityId={graphFocusEntityId}
        onNavigateInvestigation={handleNavigateInvestigation}
      />
    {:else if currentView === 'query'}
      <QueryView />
    {:else if currentView === 'ingest'}
      <IngestView />
    {:else if currentView === 'intel'}
      <ThreatIntelView />
    {:else if currentView === 'hunting'}
      <HuntingView />
    {:else if currentView === 'playbooks'}
      <PlaybooksView investigationId={playbookInvestigationId} />
    {:else if currentView === 'reports'}
      <ReportsView />
    {:else if currentView === 'assets'}
      <AssetsView />
    {:else if currentView === 'provenance'}
      <ProvenanceView />
    {:else if currentView === 'recommendations'}
      <RecommendationsView />
    {:else if currentView === 'settings'}
      <SettingsView />
    {:else if currentView === 'map'}
      <MapView />
    {/if}
  </main>
</div>

<style>
  .app-shell {
    display: flex;
    height: 100vh;
    overflow: hidden;
    background: var(--bg-primary);
  }

  /* ── Sidebar ── */
  .sidebar {
    width: 230px;
    flex-shrink: 0;
    background: #111111;
    border-right: 1px solid rgba(255,255,255,0.06);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .sidebar-header {
    padding: 16px 14px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }

  .logo-row {
    display: flex;
    align-items: center;
    gap: 9px;
  }

  .logo-text {
    font-size: 14px;
    font-weight: 600;
    color: rgba(255,255,255,0.88);
    letter-spacing: -0.2px;
  }

  .health-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    transition: background 0.4s;
    opacity: 0.85;
  }

  /* ── Posture strip ── */
  .posture-strip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 14px 12px;
    flex-shrink: 0;
  }

  .posture-label {
    font-size: 11px;
    color: rgba(255,255,255,0.28);
    flex-shrink: 0;
  }

  .posture-bar-bg {
    flex: 1;
    height: 2px;
    background: rgba(255,255,255,0.07);
    border-radius: 2px;
    overflow: hidden;
  }

  .posture-bar-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.6s ease, background 0.4s;
  }

  .posture-num {
    font-size: 11px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
    width: 24px;
    text-align: right;
  }

  /* ── Nav ── */
  .nav-scroll {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 4px 8px 8px;
  }

  .nav-scroll::-webkit-scrollbar { width: 3px; }
  .nav-scroll::-webkit-scrollbar-track { background: transparent; }
  .nav-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 2px; }

  .nav-group {
    margin-bottom: 4px;
  }

  .nav-group-label {
    display: block;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: rgba(255,255,255,0.25);
    padding: 10px 8px 3px;
    user-select: none;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 6px 8px;
    background: none;
    border: none;
    color: rgba(255,255,255,0.48);
    font-size: 13.5px;
    font-weight: 400;
    font-family: var(--font-sans);
    cursor: pointer;
    text-align: left;
    border-radius: 7px;
    transition: background 0.12s, color 0.12s;
  }

  .nav-item:hover {
    background: rgba(255,255,255,0.05);
    color: rgba(255,255,255,0.78);
  }

  .nav-item.active {
    background: rgba(255,255,255,0.09);
    color: rgba(255,255,255,0.95);
    font-weight: 500;
  }

  .nav-icon {
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    opacity: 0.7;
  }

  .nav-item.active .nav-icon { opacity: 1; }

  .nav-label { flex: 1; }

  .inv-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #22c55e;
    flex-shrink: 0;
  }

  .beta-tag {
    font-size: 9.5px;
    color: rgba(255,255,255,0.22);
    flex-shrink: 0;
  }

  /* ── Footer ── */
  .sidebar-footer {
    padding: 10px 14px;
    border-top: 1px solid rgba(255,255,255,0.05);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }

  .version {
    font-size: 10px;
    color: rgba(255,255,255,0.18);
    font-family: var(--font-mono);
  }

  .footer-health {
    font-size: 10px;
    text-transform: capitalize;
  }

  /* ── Main ── */
  .main-content {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: var(--bg-primary);
  }
</style>
