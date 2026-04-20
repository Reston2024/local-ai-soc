<script lang="ts">
  /**
   * LiveHeader — 44px top bar spanning the full width.
   * Shows: logo breadcrumb · ⌘K search trigger · status chips · live clock.
   */

  interface Props {
    healthStatus:   'healthy' | 'degraded' | 'unhealthy' | 'loading'
    postureScore:   number
    networkDevices: Record<string, 'up' | 'down' | 'unknown'>
    onOpenPalette:  () => void
    currentView?:   string
  }

  let {
    healthStatus,
    postureScore,
    networkDevices,
    onOpenPalette,
    currentView = 'overview',
  }: Props = $props()

  // Live clock — updates every second
  let clockStr = $state(formatClock())

  function formatClock(): string {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  }

  $effect(() => {
    const id = setInterval(() => { clockStr = formatClock() }, 1000)
    return () => clearInterval(id)
  })

  // Status chip helpers
  const statusColor: Record<string, string> = {
    healthy:   '#22c55e',
    degraded:  '#eab308',
    unhealthy: '#ef4444',
    loading:   '#4a5d7a',
  }

  const postureColor = $derived(
    postureScore >= 80 ? '#22c55e' : postureScore >= 50 ? '#eab308' : '#ef4444'
  )

  const postureLabel = $derived(
    postureScore >= 80 ? 'Secure' : postureScore >= 50 ? 'Elevated' : 'Critical'
  )

  // Pretty-print the current view name
  const viewLabel: Record<string, string> = {
    'overview': 'Overview', 'detections': 'Detections', 'investigation': 'Investigation',
    'events': 'Events', 'graph': 'Attack Graph', 'query': 'AI Query', 'ingest': 'Ingest',
    'intel': 'Threat Intel', 'hunting': 'Hunting', 'playbooks': 'Playbooks',
    'reports': 'Reports', 'assets': 'Assets', 'provenance': 'Provenance',
    'recommendations': 'Recommendations', 'settings': 'Settings', 'map': 'Threat Map',
    'attack-coverage': 'ATT&CK Coverage', 'atomics': 'Atomics', 'anomaly': 'Anomaly',
    'performance': 'Performance', 'privacy': 'Privacy',
  }

  const networkUp = $derived(
    Object.values(networkDevices).filter(s => s === 'up').length
  )
  const networkTotal = $derived(Object.keys(networkDevices).length)
</script>

<header class="live-header">
  <!-- Left: logo + breadcrumb -->
  <div class="lh-left">
    <div class="lh-logo">
      <svg width="16" height="16" viewBox="0 0 22 22" fill="none">
        <path d="M11 2L3 5.5V11C3 15.4 6.6 19.4 11 20.5C15.4 19.4 19 15.4 19 11V5.5L11 2Z"
          fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.4)" stroke-width="1.3"/>
        <circle cx="11" cy="11" r="3" fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="1.1"/>
        <circle cx="11" cy="11" r="1.2" fill="rgba(255,255,255,0.75)"/>
      </svg>
      <span class="lh-logo-text">SOC Brain</span>
    </div>
    {#if currentView !== 'overview'}
      <span class="lh-sep">/</span>
      <span class="lh-breadcrumb">{viewLabel[currentView] ?? currentView}</span>
    {/if}
  </div>

  <!-- Center: ⌘K search trigger -->
  <div class="lh-center">
    <button class="lh-search-btn" onclick={onOpenPalette} title="Command palette (Ctrl+K)">
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
        <circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="1.5"/>
        <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
      <span class="lh-search-placeholder">Search everything…</span>
      <kbd class="lh-kbd">⌘K</kbd>
    </button>
  </div>

  <!-- Right: status chips + clock -->
  <div class="lh-right">
    <!-- Backend health chip -->
    <div
      class="lh-chip"
      title="Backend: {healthStatus}"
      style="--chip-color: {statusColor[healthStatus]}"
    >
      <span class="lh-chip-dot"></span>
      <span class="lh-chip-label">
        {healthStatus === 'loading' ? '…' : healthStatus === 'healthy' ? 'OK' : healthStatus}
      </span>
    </div>

    <!-- Network chip (only when we have data) -->
    {#if networkTotal > 0}
      <div
        class="lh-chip"
        title="Network: {networkUp}/{networkTotal} up"
        style="--chip-color: {networkUp === networkTotal ? '#22c55e' : networkUp > 0 ? '#eab308' : '#ef4444'}"
      >
        <span class="lh-chip-dot"></span>
        <span class="lh-chip-label">{networkUp}/{networkTotal}</span>
      </div>
    {/if}

    <!-- Posture chip -->
    <div
      class="lh-chip"
      title="Security posture: {postureScore}/100 — {postureLabel}"
      style="--chip-color: {postureColor}"
    >
      <span class="lh-chip-icon">⊙</span>
      <span class="lh-chip-label">{postureLabel}</span>
    </div>

    <!-- Live clock -->
    <span class="lh-clock">{clockStr}</span>
  </div>
</header>

<style>
  .live-header {
    height: 44px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 0;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    padding: 0 12px;
    z-index: 100;
  }

  /* ── Left ── */
  .lh-left {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 180px;
    flex-shrink: 0;
  }

  .lh-logo {
    display: flex;
    align-items: center;
    gap: 7px;
  }

  .lh-logo-text {
    font-size: 13px;
    font-weight: 600;
    color: rgba(255,255,255,0.85);
    letter-spacing: -0.2px;
    white-space: nowrap;
  }

  .lh-sep {
    color: rgba(255,255,255,0.18);
    font-size: 14px;
  }

  .lh-breadcrumb {
    font-size: 12.5px;
    color: rgba(255,255,255,0.45);
    white-space: nowrap;
  }

  /* ── Center ── */
  .lh-center {
    flex: 1;
    display: flex;
    justify-content: center;
    padding: 0 16px;
  }

  .lh-search-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    max-width: 320px;
    height: 28px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 7px;
    padding: 0 10px;
    cursor: pointer;
    color: rgba(255,255,255,0.28);
    font-family: var(--font-sans);
    transition: background 0.12s, border-color 0.12s;
  }

  .lh-search-btn:hover {
    background: rgba(255,255,255,0.08);
    border-color: rgba(255,255,255,0.14);
    color: rgba(255,255,255,0.5);
  }

  .lh-search-placeholder {
    flex: 1;
    text-align: left;
    font-size: 12px;
  }

  .lh-kbd {
    font-size: 10px;
    font-family: var(--font-sans);
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 3px;
    padding: 1px 4px;
    flex-shrink: 0;
  }

  /* ── Right ── */
  .lh-right {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 180px;
    justify-content: flex-end;
    flex-shrink: 0;
  }

  /* ── Status chip ── */
  .lh-chip {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border-radius: 20px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    cursor: default;
    white-space: nowrap;
  }

  .lh-chip-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--chip-color, #4a5d7a);
    flex-shrink: 0;
  }

  .lh-chip-icon {
    font-size: 10px;
    color: var(--chip-color, #4a5d7a);
    flex-shrink: 0;
  }

  .lh-chip-label {
    font-size: 10.5px;
    color: rgba(255,255,255,0.45);
    font-family: var(--font-mono);
    text-transform: capitalize;
  }

  /* ── Clock ── */
  .lh-clock {
    font-size: 11.5px;
    color: rgba(255,255,255,0.28);
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.3px;
    white-space: nowrap;
  }
</style>
