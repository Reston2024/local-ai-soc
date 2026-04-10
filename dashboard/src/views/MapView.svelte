<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import { api } from '../lib/api.ts'
  import type { OsintResult, Detection } from '../lib/api.ts'
  import 'leaflet/dist/leaflet.css'

  let mapContainer: HTMLDivElement
  // Module-level typed variables — set once in onMount
  let L: typeof import('leaflet') | null = null
  let map: import('leaflet').Map | null = null
  let markerLayer: import('leaflet').LayerGroup | null = null

  let selectedIp = $state<string | null>(null)
  let osintData = $state<OsintResult | null>(null)
  let osintLoading = $state(false)
  let markerCount = $state(0)
  let lastRefresh = $state('')
  let refreshInterval: ReturnType<typeof setInterval> | null = null

  const SEV_COLORS: Record<string, string> = {
    critical: '#ef4444',
    high:     '#f97316',
    medium:   '#eab308',
    low:      '#3b82f6',
    info:     '#94a3b8',
  }

  async function loadMarkers() {
    // Guard: only run after onMount has initialised L, map, markerLayer
    if (!L || !map || !markerLayer) return
    try {
      const resp = await api.detections.list({ limit: 200 })
      const detections: Detection[] = resp.detections ?? []

      // Deduplicate IPs, keeping highest severity for each
      const ipMap = new Map<string, { severity: string; count: number }>()
      for (const d of detections) {
        if (!d.src_ip) continue
        const existing = ipMap.get(d.src_ip)
        const sevOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 }
        const newSev = (d.severity ?? 'info').toLowerCase()
        if (!existing || (sevOrder[newSev] ?? 4) < (sevOrder[existing.severity] ?? 4)) {
          ipMap.set(d.src_ip, { severity: newSev, count: (existing?.count ?? 0) + 1 })
        } else {
          ipMap.set(d.src_ip, { ...existing, count: existing.count + 1 })
        }
      }

      markerLayer.clearLayers()
      let plotted = 0

      // For each unique IP, fetch geo from OSINT cache (or skip if private/no data)
      const geoFetches = Array.from(ipMap.entries()).map(async ([ip, meta]) => {
        try {
          const osint = await api.osint.get(ip)
          if (!osint.geo?.latitude || !osint.geo?.longitude) return
          const lat = osint.geo.latitude
          const lon = osint.geo.longitude
          const color = SEV_COLORS[meta.severity] ?? SEV_COLORS.info
          // Use module-level L directly — no window.L
          const marker = L!.circleMarker([lat, lon], {
            color,
            fillColor: color,
            fillOpacity: 0.75,
            radius: Math.min(6 + meta.count, 14),
            weight: 1.5,
          })
          marker.on('click', () => selectIp(ip))
          marker.bindTooltip(`${ip} (${meta.count} detection${meta.count > 1 ? 's' : ''}, ${meta.severity})`, { permanent: false })
          markerLayer!.addLayer(marker)
          plotted++
        } catch {
          // Private/invalid IP — skip silently
        }
      })

      await Promise.allSettled(geoFetches)
      markerCount = plotted
      lastRefresh = new Date().toLocaleTimeString()
    } catch (e) {
      console.error('MapView: failed to load markers', e)
    }
  }

  async function selectIp(ip: string) {
    selectedIp = ip
    osintLoading = true
    osintData = null
    try {
      osintData = await api.osint.get(ip)
    } catch {
      osintData = null
    } finally {
      osintLoading = false
    }
  }

  onMount(async () => {
    // Dynamic import of Leaflet module — CSS is imported statically above
    const leafletModule = await import('leaflet')
    L = leafletModule.default

    map = L.map(mapContainer, { center: [20, 10], zoom: 2, zoomControl: true })

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
    }).addTo(map)

    markerLayer = L.layerGroup().addTo(map)

    // Force Leaflet to recalculate container size after flex layout resolves
    requestAnimationFrame(() => { map?.invalidateSize() })

    await loadMarkers()
    refreshInterval = setInterval(loadMarkers, 60_000)
  })

  onDestroy(() => {
    if (refreshInterval) clearInterval(refreshInterval)
    if (map) map.remove()
  })
</script>

<div class="map-view">
  <div class="map-header">
    <h1>Threat Map</h1>
    <span class="map-meta">{markerCount} IPs plotted · refreshes every 60s{lastRefresh ? ` · last: ${lastRefresh}` : ''}</span>
  </div>
  <div class="map-body">
    <div class="map-container" bind:this={mapContainer}></div>
    {#if selectedIp}
      <div class="osint-side-panel">
        <div class="panel-header">
          <span class="panel-ip">{selectedIp}</span>
          <button class="panel-close" onclick={() => { selectedIp = null; osintData = null }}>✕</button>
        </div>
        {#if osintLoading}
          <div class="panel-loading">Loading OSINT…</div>
        {:else if osintData}
          <div class="panel-body">
            {#if osintData.geo}
              <div class="panel-section">
                <div class="panel-label">LOCATION</div>
                <div class="panel-value">{osintData.geo.country_name ?? '—'} / {osintData.geo.city ?? '—'}</div>
                <div class="panel-sub">{osintData.geo.autonomous_system_organization ?? '—'} (AS{osintData.geo.autonomous_system_number ?? '?'})</div>
              </div>
            {/if}
            {#if osintData.abuseipdb}
              <div class="panel-section">
                <div class="panel-label">ABUSEIPDB</div>
                <div class="panel-value">
                  <span class="abuse-score" class:abuse-red={(osintData.abuseipdb.abuseConfidenceScore ?? 0) > 50}>
                    {osintData.abuseipdb.abuseConfidenceScore ?? 0}% confidence
                  </span>
                </div>
                <div class="panel-sub">{osintData.abuseipdb.totalReports ?? 0} reports · {osintData.abuseipdb.isp ?? '—'}</div>
              </div>
            {/if}
            {#if osintData.virustotal}
              <div class="panel-section">
                <div class="panel-label">VIRUSTOTAL</div>
                <div class="panel-value">{osintData.virustotal.malicious ?? 0} malicious / {osintData.virustotal.suspicious ?? 0} suspicious</div>
              </div>
            {/if}
            {#if osintData.whois}
              <div class="panel-section">
                <div class="panel-label">WHOIS</div>
                <div class="panel-value">{osintData.whois.org ?? '—'}</div>
                <div class="panel-sub">Registrar: {osintData.whois.registrar ?? '—'}</div>
                <div class="panel-sub">Created: {osintData.whois.creation_date ?? '—'}</div>
              </div>
            {/if}
            {#if osintData.shodan}
              <div class="panel-section">
                <div class="panel-label">SHODAN</div>
                <div class="panel-value">Ports: {osintData.shodan.open_ports?.join(', ') || 'none'}</div>
                <div class="panel-sub">{osintData.shodan.org ?? '—'}</div>
              </div>
            {/if}
            <div class="panel-cache">{osintData.cached ? 'cached' : 'fresh'} · {osintData.fetched_at.slice(0, 19)}</div>
          </div>
        {:else}
          <div class="panel-empty">No enrichment data</div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .map-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
  .map-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; border-bottom: 1px solid var(--border); background: var(--bg-secondary); flex-shrink: 0; }
  .map-header h1 { font-size: 15px; font-weight: 600; }
  .map-meta { font-size: 11px; color: var(--text-muted); }
  .map-body { display: flex; flex: 1; overflow: hidden; }
  .map-container { flex: 1; min-height: 400px; }
  .osint-side-panel { width: 300px; border-left: 1px solid var(--border); background: var(--bg-secondary); overflow-y: auto; flex-shrink: 0; }
  .panel-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; border-bottom: 1px solid var(--border); }
  .panel-ip { font-family: monospace; font-size: 13px; font-weight: 600; }
  .panel-close { background: none; border: none; cursor: pointer; color: var(--text-muted); font-size: 14px; }
  .panel-loading, .panel-empty { padding: 20px 14px; font-size: 12px; color: var(--text-muted); }
  .panel-body { padding: 10px 14px; display: flex; flex-direction: column; gap: 14px; }
  .panel-section { display: flex; flex-direction: column; gap: 2px; }
  .panel-label { font-size: 10px; font-weight: 700; letter-spacing: 0.5px; color: var(--accent-cyan); }
  .panel-value { font-size: 12px; color: var(--text-primary); }
  .panel-sub { font-size: 11px; color: var(--text-muted); }
  .panel-cache { font-size: 10px; color: var(--text-muted); }
  .abuse-score { color: var(--text-secondary); }
  .abuse-score.abuse-red { color: #ef4444; font-weight: 600; }
</style>
