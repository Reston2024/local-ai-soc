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

  type View =
    | 'detections' | 'investigation' | 'events' | 'graph' | 'query' | 'ingest'
    | 'intel' | 'hunting' | 'playbooks' | 'reports' | 'assets'

  let currentView = $state<View>('detections')
  let healthStatus = $state<'healthy' | 'degraded' | 'unhealthy' | 'loading'>('loading')
  let investigatingId = $state<string>('')
  let postureScore = $state(100) // 0–100; updated once detections load

  function handleInvestigate(detectionId: string) {
    investigatingId = detectionId
    currentView = 'investigation'
  }

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
        { id: 'detections',   label: 'Detections',   color: '#00d4ff' },
        { id: 'events',       label: 'Events',        color: '#a78bfa' },
        { id: 'assets',       label: 'Assets',        color: '#38bdf8' },
      ],
    },
    {
      label: 'Investigate',
      items: [
        { id: 'investigation', label: 'Investigation', color: '#3b82f6' },
        { id: 'graph',         label: 'Attack Graph',  color: '#22c55e' },
      ],
    },
    {
      label: 'Intelligence',
      items: [
        { id: 'intel',    label: 'Threat Intel', color: '#f97316', beta: true },
        { id: 'hunting',  label: 'Hunting',      color: '#e879f9', beta: true },
      ],
    },
    {
      label: 'Respond',
      items: [
        { id: 'playbooks', label: 'Playbooks', color: '#34d399', beta: true },
        { id: 'reports',   label: 'Reports',   color: '#fbbf24' },
      ],
    },
    {
      label: 'Platform',
      items: [
        { id: 'query',  label: 'AI Query', color: '#00d4ff' },
        { id: 'ingest', label: 'Ingest',   color: '#f97316' },
      ],
    },
  ]
</script>

<div class="app-shell">
  <!-- Sidebar -->
  <nav class="sidebar">
    <div class="sidebar-header">
      <div class="logo-row">
        <svg class="logo-icon" width="22" height="22" viewBox="0 0 22 22" fill="none">
          <path d="M11 2L3 5.5V11C3 15.4 6.6 19.4 11 20.5C15.4 19.4 19 15.4 19 11V5.5L11 2Z"
            fill="rgba(0,212,255,0.12)" stroke="#00d4ff" stroke-width="1.4"/>
          <circle cx="11" cy="11" r="3.5" fill="none" stroke="#00d4ff" stroke-width="1.2"/>
          <circle cx="11" cy="11" r="1.2" fill="#00d4ff"/>
          <line x1="7.5" y1="11" x2="5.5" y2="11" stroke="#00d4ff" stroke-width="1" opacity="0.6"/>
          <line x1="14.5" y1="11" x2="16.5" y2="11" stroke="#00d4ff" stroke-width="1" opacity="0.6"/>
          <line x1="11" y1="7.5" x2="11" y2="5.5" stroke="#00d4ff" stroke-width="1" opacity="0.6"/>
          <line x1="11" y1="14.5" x2="11" y2="16.5" stroke="#00d4ff" stroke-width="1" opacity="0.6"/>
        </svg>
        <span class="logo-text">SOC BRAIN</span>
      </div>
      <span
        class="health-dot"
        style="background: {statusColor[healthStatus]}; box-shadow: 0 0 6px {statusColor[healthStatus]}"
        title="Backend: {healthStatus}"
      ></span>
    </div>

    <!-- Security posture score -->
    <div class="posture-block">
      <div class="posture-header">
        <span class="posture-label-text">Security Posture</span>
        <span class="posture-badge" style="color: {postureColor}">{postureLabel}</span>
      </div>
      <div class="posture-bar-bg">
        <div
          class="posture-bar-fill"
          style="width: {postureScore}%; background: {postureColor};"
        ></div>
      </div>
      <div class="posture-score" style="color: {postureColor}">{postureScore}<span class="posture-denom">/100</span></div>
    </div>

    <!-- Nav groups -->
    <div class="nav-scroll">
      {#each navGroups as group}
        <div class="nav-group">
          <span class="nav-group-label">{group.label}</span>
          <ul class="nav-list">
            {#each group.items as item}
              <li>
                <button
                  class="nav-item"
                  class:active={currentView === item.id}
                  onclick={() => { currentView = item.id }}
                  style="--item-color: {item.color}"
                >
                  <span class="nav-icon-wrap" class:active-icon={currentView === item.id}>
                    {#if item.id === 'detections'}
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M9 1.5L3.5 9H7.5L7 14.5L12.5 7H8.5L9 1.5Z" fill="currentColor"/></svg>
                    {:else if item.id === 'investigation'}
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="1.6"/><line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
                    {:else if item.id === 'events'}
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><rect x="2" y="3" width="12" height="2" rx="1" fill="currentColor"/><rect x="2" y="7" width="12" height="2" rx="1" fill="currentColor"/><rect x="2" y="11" width="8" height="2" rx="1" fill="currentColor"/></svg>
                    {:else if item.id === 'graph'}
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="2" fill="currentColor"/><circle cx="2.5" cy="4" r="1.5" fill="currentColor"/><circle cx="13.5" cy="4" r="1.5" fill="currentColor"/><circle cx="8" cy="13.5" r="1.5" fill="currentColor"/><line x1="3.8" y1="5.2" x2="6.6" y2="7" stroke="currentColor" stroke-width="1.2"/><line x1="12.2" y1="5.2" x2="9.4" y2="7" stroke="currentColor" stroke-width="1.2"/><line x1="8" y1="10" x2="8" y2="12" stroke="currentColor" stroke-width="1.2"/></svg>
                    {:else if item.id === 'query'}
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><rect x="2.5" y="5" width="11" height="8" rx="2" stroke="currentColor" stroke-width="1.5"/><circle cx="6" cy="9" r="1" fill="currentColor"/><circle cx="10" cy="9" r="1" fill="currentColor"/><line x1="8" y1="5" x2="8" y2="2.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="8" cy="2" r="0.9" fill="currentColor"/></svg>
                    {:else if item.id === 'ingest'}
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><line x1="8" y1="2" x2="8" y2="10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M5 7.5L8 11L11 7.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><line x1="3" y1="13" x2="13" y2="13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
                    {:else if item.id === 'intel'}
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 2a6 6 0 1 1 0 12A6 6 0 0 1 8 2Z" stroke="currentColor" stroke-width="1.4"/><path d="M8 5v3.5l2 1.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    {:else if item.id === 'hunting'}
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="7.5" cy="7.5" r="5" stroke="currentColor" stroke-width="1.4"/><line x1="7.5" y1="2.5" x2="7.5" y2="4.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><line x1="7.5" y1="10.5" x2="7.5" y2="12.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><line x1="2.5" y1="7.5" x2="4.5" y2="7.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><line x1="10.5" y1="7.5" x2="12.5" y2="7.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><circle cx="7.5" cy="7.5" r="1.5" fill="currentColor"/></svg>
                    {:else if item.id === 'playbooks'}
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><rect x="3" y="2" width="10" height="12" rx="1.5" stroke="currentColor" stroke-width="1.4"/><line x1="6" y1="6" x2="10" y2="6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><line x1="6" y1="9" x2="9" y2="9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
                    {:else if item.id === 'reports'}
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><rect x="2" y="10" width="3" height="4" rx="1" fill="currentColor" opacity="0.5"/><rect x="6.5" y="6" width="3" height="8" rx="1" fill="currentColor" opacity="0.75"/><rect x="11" y="2" width="3" height="12" rx="1" fill="currentColor"/></svg>
                    {:else if item.id === 'assets'}
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><rect x="2" y="2" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/><rect x="9" y="2" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/><rect x="2" y="9" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/><rect x="9" y="9" width="5" height="5" rx="1.2" stroke="currentColor" stroke-width="1.4"/></svg>
                    {/if}
                  </span>
                  <span class="nav-label">{item.label}</span>
                  {#if item.beta}
                    <span class="beta-tag">BETA</span>
                  {/if}
                  {#if item.id === 'investigation' && investigatingId}
                    <span class="inv-dot"></span>
                  {/if}
                </button>
              </li>
            {/each}
          </ul>
        </div>
      {/each}
    </div>

    <div class="sidebar-footer">
      <span class="version">v0.1.0</span>
      <span class="footer-status" title="Backend: {healthStatus}">{healthStatus}</span>
    </div>
  </nav>

  <!-- Main content -->
  <main class="main-content">
    {#if currentView === 'detections'}
      <DetectionsView onInvestigate={handleInvestigate} onPostureUpdate={handlePostureUpdate} />
    {:else if currentView === 'investigation'}
      <InvestigationView investigationId={investigatingId} />
    {:else if currentView === 'events'}
      <EventsView />
    {:else if currentView === 'graph'}
      <GraphView />
    {:else if currentView === 'query'}
      <QueryView />
    {:else if currentView === 'ingest'}
      <IngestView />
    {:else if currentView === 'intel'}
      <ThreatIntelView />
    {:else if currentView === 'hunting'}
      <HuntingView />
    {:else if currentView === 'playbooks'}
      <PlaybooksView />
    {:else if currentView === 'reports'}
      <ReportsView />
    {:else if currentView === 'assets'}
      <AssetsView />
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
    width: 224px;
    flex-shrink: 0;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .sidebar-header {
    padding: 16px 14px 12px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }

  .logo-row { display: flex; align-items: center; gap: 8px; }
  .logo-icon { flex-shrink: 0; }
  .logo-text {
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 2px;
    color: var(--text-primary);
  }

  .health-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
    transition: background 0.4s;
  }

  /* ── Posture block ── */
  .posture-block {
    padding: 12px 14px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .posture-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }

  .posture-label-text {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .posture-badge {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.3px;
  }

  .posture-bar-bg {
    height: 3px;
    background: var(--bg-tertiary);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 5px;
  }

  .posture-bar-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.6s ease, background 0.4s;
  }

  .posture-score {
    font-size: 18px;
    font-weight: 700;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }
  .posture-denom {
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 400;
    margin-left: 2px;
  }

  /* ── Nav ── */
  .nav-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 6px 8px 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .nav-group { margin-bottom: 2px; }

  .nav-group-label {
    display: block;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.9px;
    text-transform: uppercase;
    color: var(--text-muted);
    padding: 8px 8px 4px;
  }

  .nav-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 7px 8px;
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 13px;
    font-family: var(--font-sans);
    cursor: pointer;
    text-align: left;
    border-radius: var(--radius-md);
    transition: background 0.12s, color 0.12s;
    position: relative;
  }

  .nav-item:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }

  .nav-item.active {
    background: rgba(0, 212, 255, 0.07);
    color: var(--item-color, var(--accent-cyan));
    border-left: 2px solid var(--item-color, var(--accent-cyan));
    padding-left: 6px;
  }

  .nav-icon-wrap {
    width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    background: var(--bg-tertiary);
    flex-shrink: 0;
    color: var(--text-muted);
    transition: background 0.12s, color 0.12s;
  }

  .nav-item:hover .nav-icon-wrap { background: var(--bg-hover); color: var(--text-secondary); }
  .nav-item.active .nav-icon-wrap,
  .active-icon { background: rgba(0, 212, 255, 0.1); color: var(--item-color, var(--accent-cyan)); }

  .nav-label { flex: 1; }

  .beta-tag {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: var(--accent-purple);
    background: rgba(167,139,250,0.1);
    border: 1px solid rgba(167,139,250,0.2);
    padding: 1px 5px;
    border-radius: 4px;
    flex-shrink: 0;
  }

  .inv-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent-green);
    box-shadow: 0 0 5px var(--accent-green);
    flex-shrink: 0;
  }

  /* ── Footer ── */
  .sidebar-footer {
    padding: 10px 14px;
    border-top: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }

  .version {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .footer-status {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: capitalize;
    letter-spacing: 0.3px;
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
