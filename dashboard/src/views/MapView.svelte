<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import { api } from '../lib/api.ts'
  import type { MapData, MapIpInfo, MapFlow } from '../lib/api.ts'

  // --- State (Svelte 5 runes) ---
  let map: any = null
  let L: any = null
  let clusterGroup: any = null
  let arcLayer: any = null
  let lanMarker: any = null
  let mapData = $state<MapData | null>(null)
  let selectedIp = $state<string | null>(null)
  let selectedWindow = $state('24h')
  let loading = $state(false)
  let refreshPaused = $state(false)
  let refreshTimer: ReturnType<typeof setInterval> | null = null
  let filterMode = $state<'all' | 'tor' | 'vpn' | 'datacenter'>('all')

  // --- Color helpers ---
  function markerColor(info: MapIpInfo): string {
    if (info.is_tor || info.ipsum_tier !== null) return '#ef4444'  // red — known bad
    if (info.is_datacenter) return '#f97316'                        // orange — hosting
    if (info.is_proxy) return '#eab308'                             // yellow — VPN/proxy
    return '#3b82f6'                                                // blue — clean
  }

  function threatColor(info: MapIpInfo | null, _flow: MapFlow): string {
    if (!info) return '#3b82f6'
    return markerColor(info)
  }

  function ipRingWeight(info: MapIpInfo): number {
    if (info.ipsum_tier === null) return 1
    return Math.min(6, 1 + info.ipsum_tier)  // tier 1→2, tier 8→6 (max ring weight)
  }

  function matchesFilter(info: MapIpInfo): boolean {
    if (filterMode === 'all') return true
    if (filterMode === 'tor') return !!info.is_tor
    if (filterMode === 'vpn') return !!info.is_proxy
    if (filterMode === 'datacenter') return !!info.is_datacenter
    return true
  }

  function setFilter(mode: 'all' | 'tor' | 'vpn' | 'datacenter') {
    filterMode = mode
    renderMap()
  }

  // --- Data loading ---
  async function loadMapData() {
    loading = true
    try {
      mapData = await api.map.getData(selectedWindow)
      renderMap()
    } catch (e) {
      console.error('Map data fetch failed', e)
    } finally {
      loading = false
    }
  }

  // --- Render ---
  function renderMap() {
    if (!L || !map || !mapData) return
    clusterGroup.clearLayers()
    arcLayer.clearLayers()

    const PRIVATE_PREFIXES = [
      '10.', '172.16.', '172.17.', '172.18.', '172.19.',
      '172.20.', '172.21.', '172.22.', '172.23.', '172.24.',
      '172.25.', '172.26.', '172.27.', '172.28.', '172.29.',
      '172.30.', '172.31.', '192.168.', '127.'
    ]
    function isPrivate(ip: string): boolean {
      return PRIVATE_PREFIXES.some(p => ip.startsWith(p))
    }

    // LAN node at server's actual geographic location (falls back to [0, 0] if unavailable)
    const homeLat = mapData.home_lat ?? 0
    const homeLon = mapData.home_lon ?? 0
    lanMarker = L.circleMarker([homeLat, homeLon], {
      radius: 14,
      color: '#6366f1',
      fillColor: '#6366f1',
      fillOpacity: 0.9,
      weight: 3,
    })
    lanMarker.bindTooltip('LAN (internal hosts)', { permanent: false })
    lanMarker.addTo(clusterGroup)

    // Pan map to home location on first load (only if map hasn't been moved by user)
    if (mapData.home_lat !== null && mapData.home_lon !== null) {
      map.setView([homeLat, homeLon], map.getZoom(), { animate: false })
    }

    // External IP markers — apply filterMode
    for (const [ip, info] of Object.entries(mapData.ips as Record<string, MapIpInfo>)) {
      if (!info.lat || !info.lon) continue
      if (!matchesFilter(info)) continue
      const color = markerColor(info)
      const weight = ipRingWeight(info)
      const marker = L.circleMarker([info.lat, info.lon], {
        radius: 8,
        color,
        fillColor: color,
        fillOpacity: 0.7,
        weight,
      })
      marker.bindTooltip(ip, { permanent: false })
      marker.on('click', () => {
        selectedIp = ip
        refreshPaused = true
      })
      marker.on('mouseover', () => { refreshPaused = true })
      marker.on('mouseout', () => { if (selectedIp !== ip) refreshPaused = false })
      clusterGroup.addLayer(marker)
    }

    // Arc lines for top-50 flows by connection count
    const topFlows = [...mapData.flows]
      .sort((a, b) => b.conn_count - a.conn_count)
      .slice(0, 50)
    const maxConn = topFlows[0]?.conn_count ?? 1

    for (const flow of topFlows) {
      const srcIsPrivate = isPrivate(flow.src_ip)
      const dstIsPrivate = isPrivate(flow.dst_ip)
      const srcInfo = srcIsPrivate ? null : (mapData.ips[flow.src_ip] as MapIpInfo | undefined)
      const dstInfo = dstIsPrivate ? null : (mapData.ips[flow.dst_ip] as MapIpInfo | undefined)

      // Both ends need coordinates (use LAN node coords for private IPs)
      const srcLatLng = srcIsPrivate
        ? [homeLat, homeLon]
        : (srcInfo?.lat && srcInfo?.lon ? [srcInfo.lat, srcInfo.lon] : null)
      const dstLatLng = dstIsPrivate
        ? [homeLat, homeLon]
        : (dstInfo?.lat && dstInfo?.lon ? [dstInfo.lat, dstInfo.lon] : null)

      if (!srcLatLng || !dstLatLng) continue

      // Antimeridian guard: adjust lon if |lon_a - lon_b| > 180
      let sLon = srcLatLng[1]
      let dLon = dstLatLng[1]
      const sLat = srcLatLng[0]
      const dLat = dstLatLng[0]
      if (Math.abs(sLon - dLon) > 180) {
        if (sLon > dLon) dLon += 360; else dLon -= 360
      }

      // Threat signal color
      const threatIp = srcIsPrivate ? dstInfo : srcInfo
      const arcColor = threatColor(threatIp ?? null, flow)
      const arcWeight = Math.max(1, Math.round((flow.conn_count / maxConn) * 5))
      const arcOpacity = flow.conn_count / maxConn >= 0.1 ? 0.7 : 0.3

      const line = L.polyline([[sLat, sLon], [dLat, dLon]], {
        color: arcColor,
        weight: arcWeight,
        opacity: arcOpacity,
      })
      line.addTo(arcLayer)

      const decorator = (L as any).polylineDecorator(line, {
        patterns: [{
          offset: '100%',
          repeat: 0,
          symbol: (L as any).Symbol.arrowHead({
            pixelSize: 8,
            headAngle: 40,
            fill: true,
            fillOpacity: 0.8,
            pathOptions: { color: arcColor, weight: 0 },
          }),
        }],
      })
      decorator.addTo(arcLayer)
    }
  }

  // --- Lifecycle ---
  onMount(async () => {
    // 1. Import Leaflet first (CRITICAL: sequential — not Promise.all)
    const leafletModule = await import('leaflet')
    L = leafletModule.default
    await import('leaflet/dist/leaflet.css')

    // 2. MarkerCluster — AFTER Leaflet resolves
    await import('leaflet.markercluster')
    await import('leaflet.markercluster/dist/MarkerCluster.css')
    await import('leaflet.markercluster/dist/MarkerCluster.Default.css')

    // 3. PolylineDecorator — AFTER Leaflet resolves
    await import('leaflet-polylinedecorator')

    // 4. Init map
    map = L.map('threat-map', { center: [20, 10], zoom: 2, zoomControl: true })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 18,
    }).addTo(map)

    // 5. Init layers
    clusterGroup = (L as any).markerClusterGroup({ maxClusterRadius: 40 })
    arcLayer = L.layerGroup()
    map.addLayer(clusterGroup)
    map.addLayer(arcLayer)

    // Force Leaflet to recalculate container size after flex layout resolves.
    // Two rAF passes: first lets the DOM paint, second catches any reflow.
    requestAnimationFrame(() => {
      map?.invalidateSize()
      requestAnimationFrame(() => { map?.invalidateSize() })
    })

    // 6. Initial data load + start refresh timer
    await loadMapData()
    refreshTimer = setInterval(async () => {
      if (!refreshPaused) await loadMapData()
    }, 60_000)
  })

  onDestroy(() => {
    if (refreshTimer) clearInterval(refreshTimer)
    if (map) map.remove()
  })
</script>

<div class="map-container">
  <!-- Header stats bar -->
  <div class="map-header">
    <div class="map-stats">
      {#if mapData}
        <button
          class="stat-filter-btn {filterMode === 'all' ? 'active' : ''}"
          onclick={() => setFilter('all')}
          title="Show all IPs"
        >{mapData.stats.total_ips} IPs</button>
        <span class="sep">·</span>
        <button
          class="stat-filter-btn stat-tor {filterMode === 'tor' ? 'active' : ''}"
          onclick={() => setFilter('tor')}
          title="Filter: Tor exit nodes only"
        >{mapData.stats.tor_count} Tor</button>
        <span class="sep">·</span>
        <button
          class="stat-filter-btn stat-vpn {filterMode === 'vpn' ? 'active' : ''}"
          onclick={() => setFilter('vpn')}
          title="Filter: VPN/Proxy only"
        >{mapData.stats.vpn_count} VPN/Proxy</button>
        <span class="sep">·</span>
        <button
          class="stat-filter-btn stat-dc {filterMode === 'datacenter' ? 'active' : ''}"
          onclick={() => setFilter('datacenter')}
          title="Filter: Datacenter IPs only"
        >{mapData.stats.datacenter_count} Datacenter</button>
        {#if mapData.stats.top_src_country}
          <span class="sep">·</span>
          <span>Top source: {mapData.stats.top_src_country} ({mapData.stats.top_src_country_conn_count.toLocaleString()} conns)</span>
        {/if}
        <span class="sep">·</span>
        <span>{mapData.stats.flow_count} flows shown</span>
      {:else}
        <span class="stat-loading">{loading ? 'Loading...' : 'No data'}</span>
      {/if}
    </div>
    <!-- Time window buttons -->
    <div class="window-buttons">
      {#each ['1h', '6h', '24h', '7d'] as w}
        <button
          class="window-btn"
          class:active={selectedWindow === w}
          onclick={() => { selectedWindow = w; loadMapData() }}
        >{w}</button>
      {/each}
    </div>
  </div>

  <!-- Map canvas -->
  <div id="threat-map" class="map-canvas"></div>

  <!-- Side panel -->
  {#if selectedIp && mapData}
    {@const info = (mapData.ips as Record<string, MapIpInfo>)[selectedIp]}
    <div class="side-panel">
      <div class="panel-header">
        <span class="panel-ip">{selectedIp}</span>
        <button
          class="close-btn"
          onclick={() => { selectedIp = null; refreshPaused = false }}
        >×</button>
      </div>

      <!-- CLASSIFICATION section — first, per user decision -->
      <section class="panel-section classification">
        <h4>CLASSIFICATION</h4>
        {#if info}
          <div class="classification-badges">
            {#if info.ip_type}
              <span class="badge badge-{info.ip_type}">{info.ip_type.toUpperCase()}</span>
            {:else}
              <span class="badge badge-unknown">UNKNOWN</span>
            {/if}
            {#if info.ipsum_tier !== null}
              <span class="badge badge-ipsum">ipsum tier {info.ipsum_tier}/8</span>
            {/if}
          </div>
          <div class="classification-detail">
            {#if info.is_tor}<div class="flag flag-tor">Tor Exit Node</div>{/if}
            {#if info.is_proxy}<div class="flag flag-proxy">VPN / Proxy</div>{/if}
            {#if info.is_datacenter}<div class="flag flag-dc">Datacenter / Hosting</div>{/if}
          </div>
        {:else}
          <p class="no-data">No classification data</p>
        {/if}
      </section>

      <!-- Geo section -->
      <section class="panel-section">
        <h4>GEO</h4>
        {#if info?.lat}
          <div class="detail-row"><span>Country</span><span>{info.country ?? '—'} ({info.country_iso ?? '—'})</span></div>
          <div class="detail-row"><span>City</span><span>{info.city ?? '—'}</span></div>
          <div class="detail-row"><span>Lat/Lon</span><span>{info.lat?.toFixed(2)}, {info.lon?.toFixed(2)}</span></div>
        {:else}
          <p class="no-data">No geo data (enrichment pending)</p>
        {/if}
      </section>

      <!-- ASN section -->
      <section class="panel-section">
        <h4>ASN</h4>
        <div class="detail-row"><span>ASN</span><span>{info?.asn ?? '—'}</span></div>
      </section>
    </div>
  {/if}
</div>

<style>
  /* --- Layout --- */
  .map-container {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    overflow: hidden;
    position: relative;
  }

  /* --- Header stats bar --- */
  .map-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
    flex-shrink: 0;
    gap: 12px;
    flex-wrap: wrap;
  }

  .map-stats {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-secondary, rgba(255, 255, 255, 0.7));
    flex-wrap: wrap;
  }

  .sep {
    color: var(--text-muted, rgba(255, 255, 255, 0.3));
  }

  /* Clickable filter buttons in stats bar */
  .stat-filter-btn {
    background: none;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    color: var(--text-secondary, rgba(255, 255, 255, 0.7));
    padding: 1px 6px;
    transition: background 0.12s, border-color 0.12s;
  }
  .stat-filter-btn:hover {
    background: rgba(255, 255, 255, 0.07);
    border-color: rgba(255, 255, 255, 0.15);
  }
  .stat-filter-btn.active {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.25);
    font-weight: 600;
  }

  .stat-filter-btn.stat-tor { color: #ef4444; }
  .stat-filter-btn.stat-tor.active { background: rgba(239,68,68,0.15); border-color: #ef4444; }

  .stat-filter-btn.stat-vpn { color: #eab308; }
  .stat-filter-btn.stat-vpn.active { background: rgba(234,179,8,0.15); border-color: #eab308; }

  .stat-filter-btn.stat-dc { color: #f97316; }
  .stat-filter-btn.stat-dc.active { background: rgba(249,115,22,0.15); border-color: #f97316; }

  .stat-loading {
    color: var(--text-muted, rgba(255, 255, 255, 0.4));
    font-style: italic;
  }

  /* --- Time window buttons --- */
  .window-buttons {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
  }

  .window-btn {
    padding: 3px 10px;
    background: transparent;
    border: 1px solid var(--border, rgba(255, 255, 255, 0.12));
    border-radius: 4px;
    color: var(--text-muted, rgba(255, 255, 255, 0.5));
    font-size: 11px;
    cursor: pointer;
    transition: background 0.15s, color 0.15s, border-color 0.15s;
  }

  .window-btn:hover {
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-primary, rgba(255, 255, 255, 0.9));
  }

  .window-btn.active {
    background: rgba(99, 102, 241, 0.2);
    border-color: #6366f1;
    color: #a5b4fc;
    font-weight: 600;
  }

  /* --- Map canvas --- */
  .map-canvas {
    flex: 1;
    min-height: 0;
  }

  /* --- Side panel --- */
  .side-panel {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 320px;
    background: #1a1a1a;
    border-left: 1px solid var(--border, rgba(255, 255, 255, 0.12));
    overflow-y: auto;
    z-index: 1000;
    display: flex;
    flex-direction: column;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 14px;
    border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.12));
    flex-shrink: 0;
  }

  .panel-ip {
    font-family: monospace;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary, rgba(255, 255, 255, 0.9));
  }

  .close-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-muted, rgba(255, 255, 255, 0.4));
    font-size: 18px;
    line-height: 1;
    padding: 0 4px;
    transition: color 0.15s;
  }

  .close-btn:hover {
    color: var(--text-primary, rgba(255, 255, 255, 0.9));
  }

  /* --- Panel sections --- */
  .panel-section {
    padding: 12px 14px;
    border-bottom: 1px solid var(--border, rgba(255, 255, 255, 0.06));
  }

  .panel-section h4 {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    color: var(--accent-cyan, #22d3ee);
    text-transform: uppercase;
    margin: 0 0 8px 0;
  }

  .no-data {
    font-size: 11px;
    color: var(--text-muted, rgba(255, 255, 255, 0.4));
    margin: 0;
    font-style: italic;
  }

  /* --- Classification badges --- */
  .classification-badges {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }

  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }

  .badge-tor,
  .badge-vpn { /* tor uses same red as markerColor */
    background: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.4);
  }

  .badge-vpn {
    background: rgba(234, 179, 8, 0.2);
    color: #fbbf24;
    border: 1px solid rgba(234, 179, 8, 0.4);
  }

  .badge-datacenter {
    background: rgba(249, 115, 22, 0.2);
    color: #fb923c;
    border: 1px solid rgba(249, 115, 22, 0.4);
  }

  .badge-residential,
  .badge-isp {
    background: rgba(59, 130, 246, 0.2);
    color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.4);
  }

  .badge-unknown {
    background: rgba(148, 163, 184, 0.15);
    color: #94a3b8;
    border: 1px solid rgba(148, 163, 184, 0.2);
  }

  .badge-ipsum {
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
  }

  /* --- Classification flags --- */
  .classification-detail {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .flag {
    display: inline-flex;
    align-items: center;
    font-size: 11px;
    font-weight: 500;
    padding: 2px 0;
  }

  .flag::before {
    content: '●';
    margin-right: 6px;
    font-size: 8px;
  }

  .flag-tor {
    color: #f87171;
  }

  .flag-tor::before {
    color: #ef4444;
  }

  .flag-proxy {
    color: #fbbf24;
  }

  .flag-proxy::before {
    color: #eab308;
  }

  .flag-dc {
    color: #fb923c;
  }

  .flag-dc::before {
    color: #f97316;
  }

  /* --- Detail rows (Geo, ASN) --- */
  .detail-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 12px;
    padding: 3px 0;
    gap: 8px;
  }

  .detail-row span:first-child {
    color: var(--text-muted, rgba(255, 255, 255, 0.4));
    font-size: 11px;
    flex-shrink: 0;
  }

  .detail-row span:last-child {
    color: var(--text-primary, rgba(255, 255, 255, 0.87));
    text-align: right;
    word-break: break-all;
  }
</style>
