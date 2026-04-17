<script lang="ts">
  import { api, type TelemetrySummary, type TriageResult, type Asset, type KpiSnapshot, type HealthResponse } from '../lib/api.ts'

  let {
    healthStatus,
    networkDevices,
  }: {
    healthStatus: string
    networkDevices: Record<string, string>
  } = $props()

  let summary = $state<TelemetrySummary | null>(null)
  let triageResult = $state<TriageResult | null>(null)
  let kpis = $state<KpiSnapshot | null>(null)
  let componentHealth = $state<HealthResponse | null>(null)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let triageExpanded = $state(false)
  let internalAssets = $state<Asset[]>([])

  let hayabusaFindingCount = $derived(
    (componentHealth?.components?.hayabusa?.detection_count as number | undefined) ?? 0
  )

  let chainsawFindingCount = $derived(
    (componentHealth?.components?.chainsaw?.detection_count as number | undefined) ?? 0
  )

  // Phase 53: Privacy detection count — loaded from /api/privacy/hits
  let privacyDetectionCount = $state(0)

  /** Strip markdown bold/italic asterisks from LLM output */
  function stripMd(text: string): string {
    return text.replace(/\*\*/g, '').replace(/\*/g, '').replace(/__/g, '').replace(/_/g, '')
  }

  type CompStatus = 'ok' | 'warning' | 'error' | 'unknown'

  /** Derive Malcolm health: ok if we see zeek/suricata event types in the summary */
  function malcolmStatus(s: TelemetrySummary | null): CompStatus {
    if (!s) return 'unknown'
    const types = Object.keys(s.event_type_counts)
    return types.some(t => t.includes('zeek') || t.includes('suricata') || t.includes('conn') || t.includes('dns'))
      ? 'ok' : 'warning'
  }

  /** Derive Zeek health from event_type_counts */
  function zeekStatus(s: TelemetrySummary | null): CompStatus {
    if (!s) return 'unknown'
    const types = Object.keys(s.event_type_counts)
    return types.some(t => t.startsWith('zeek') || ['conn','dns','ssl','http','files','weird','notice'].includes(t))
      ? 'ok' : 'warning'
  }

  function compDotClass(s: CompStatus | string): string {
    if (s === 'ok' || s === 'up') return 'dot-healthy'
    if (s === 'warning' || s === 'degraded') return 'dot-degraded'
    if (s === 'error' || s === 'down') return 'dot-unhealthy'
    return ''
  }
  function compStatusLabel(s: CompStatus | string): string {
    if (s === 'ok' || s === 'up') return 'ok'
    if (s === 'warning') return 'no data'
    if (s === 'error' || s === 'down') return 'error'
    return 'unknown'
  }

  // ── Topology ──────────────────────────────────────────────────
  type TopoNode = {
    id: string; label: string; sub: string
    kind: 'internet' | 'router' | 'firewall' | 'server' | 'device'
    status: 'up' | 'down' | 'unknown'
    x: number; y: number
  }

  const topoData = $derived.by(() => {
    const W = 800
    const NH = 40
    const nodes: TopoNode[] = []
    const edges: Array<{fx:number;fy:number;tx:number;ty:number}> = []

    const link = (a: TopoNode, b: TopoNode) =>
      edges.push({ fx: a.x, fy: a.y + NH/2, tx: b.x, ty: b.y - NH/2 })

    const st = (key: string): 'up'|'down'|'unknown' =>
      networkDevices[key] === 'up' ? 'up' : networkDevices[key] === 'down' ? 'down' : 'unknown'

    const internet: TopoNode = { id:'internet', label:'Internet', sub:'', kind:'internet', status:'up', x:W/2, y:30 }
    nodes.push(internet)

    const router: TopoNode = { id:'router', label:'Router', sub:'192.168.1.1', kind:'router', status:st('router'), x:W/2, y:115 }
    nodes.push(router)
    link(internet, router)

    let prev = router

    if (networkDevices.firewall !== undefined) {
      const fw: TopoNode = { id:'firewall', label:'Firewall', sub:'192.168.1.1:444', kind:'firewall', status:st('firewall'), x:W/2, y:200 }
      nodes.push(fw)
      link(router, fw)
      prev = fw
    }

    const leafY = prev.y + 85
    const knownIPs = new Set(['192.168.1.1', '192.168.1.22', '192.168.1.100'])

    type Leaf = Omit<TopoNode,'x'|'y'>
    const leaves: Leaf[] = []

    if (networkDevices.gmktec !== undefined) {
      leaves.push({ id:'gmktec', label:'GMKtec', sub:'192.168.1.22 · Malcolm', kind:'server', status:st('gmktec') })
    }

    for (const a of internalAssets) {
      if (!knownIPs.has(a.ip)) {
        leaves.push({ id:`a-${a.ip}`, label: a.hostname || a.ip, sub: a.ip, kind:'device', status:'unknown' })
        if (leaves.length >= 6) break  // cap at 6 to keep layout readable
      }
    }

    if (leaves.length === 0)
      leaves.push({ id:'lan', label:'LAN Devices', sub:'No assets discovered yet', kind:'device', status:'unknown' })

    const gap = Math.min(180, Math.max(140, (W - 60) / leaves.length))
    const startX = W/2 - (gap * (leaves.length - 1)) / 2
    for (let i = 0; i < leaves.length; i++) {
      const n: TopoNode = { ...leaves[i], x: startX + i * gap, y: leafY }
      nodes.push(n)
      link(prev, n)
    }

    return { nodes, edges, h: leafY + 55 }
  })

  function kindColor(k: TopoNode['kind']) {
    return k === 'internet'  ? { fill:'rgba(6,182,212,0.12)',  stroke:'rgba(6,182,212,0.4)'  }
         : k === 'router'    ? { fill:'rgba(99,102,241,0.12)', stroke:'rgba(99,102,241,0.5)' }
         : k === 'firewall'  ? { fill:'rgba(249,115,22,0.12)', stroke:'rgba(249,115,22,0.45)'}
         : k === 'server'    ? { fill:'rgba(16,185,129,0.12)', stroke:'rgba(16,185,129,0.45)'}
         : { fill:'rgba(255,255,255,0.04)', stroke:'rgba(255,255,255,0.12)' }
  }
  function statusDot(s: TopoNode['status']) {
    return s === 'up' ? '#22c55e' : s === 'down' ? '#ef4444' : '#64748b'
  }

  const maxCount = $derived(
    summary
      ? Math.max(1, ...Object.values(summary.event_type_counts))
      : 1
  )

  async function load() {
    try {
      const [summaryData, triageData, allAssets, kpisData, healthData] = await Promise.all([
        api.telemetry.summary(),
        api.triage.latest(),
        api.assets.list(200),
        api.metrics.kpis().catch(() => null),
        api.health().catch(() => null),
      ])
      summary = summaryData
      triageResult = triageData.result
      kpis = kpisData
      componentHealth = healthData
      // Deduplicate by hostname keeping best IP, filter out Docker bridge ranges
      const ipPriority = (ip: string) =>
        ip.startsWith('192.168.1.') ? 0 : ip.startsWith('192.168.') ? 1 : ip.startsWith('10.') ? 2 : 3
      const isRealLan = (ip: string) =>
        ip.startsWith('192.168.') || ip.startsWith('10.') ||
        (ip.startsWith('172.') && !ip.startsWith('172.16.') && !ip.startsWith('172.17.') &&
         !ip.startsWith('172.18.') && !ip.startsWith('172.19.') &&
         !ip.startsWith('172.2') && !ip.startsWith('172.3'))
      const hostMap = new Map<string, Asset>()
      for (const a of allAssets.filter(a => isRealLan(a.ip))) {
        const key = a.hostname || a.ip
        const prev = hostMap.get(key)
        if (!prev || ipPriority(a.ip) < ipPriority(prev.ip)) hostMap.set(key, a)
      }
      internalAssets = [...hostMap.values()].sort((a, b) => {
        const aLan = a.ip.startsWith('192.168.1.') ? 0 : 1
        const bLan = b.ip.startsWith('192.168.1.') ? 0 : 1
        if (aLan !== bLan) return aLan - bLan
        return a.ip.localeCompare(b.ip, undefined, { numeric: true })
      })
      error = null
      // Phase 53: Load privacy detection count (fire-and-forget, graceful fallback)
      api.privacy.hits().then(r => { privacyDetectionCount = r.hits.length }).catch(() => null)
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
            <div class="scorecard-tile">
              <span class="tile-value tile-hayabusa">{hayabusaFindingCount}</span>
              <span class="tile-label">Hayabusa<br>Findings</span>
            </div>
            <div class="scorecard-tile">
              <span class="tile-value tile-chainsaw">{chainsawFindingCount}</span>
              <span class="tile-label">Chainsaw<br>Findings</span>
            </div>
            <div class="scorecard-tile">
              <span class="tile-value tile-privacy">{privacyDetectionCount}</span>
              <span class="tile-label">Privacy<br>Detections</span>
            </div>
          </div>
        </div>

        <!-- Block 2b: Feedback KPI row (Phase 44) -->
        <div class="card scorecard-card">
          <div class="scorecard-row feedback-kpi-row">
            <div class="scorecard-tile">
              <span class="tile-value">{kpis?.verdicts_given ?? 0}</span>
              <span class="tile-label">Verdicts Given</span>
            </div>
            <div class="scorecard-tile">
              <span class="tile-value">{kpis?.verdicts_given ? ((kpis.tp_rate ?? 0) * 100).toFixed(1) + '%' : '—'}</span>
              <span class="tile-label">TP Rate</span>
            </div>
            <div class="scorecard-tile">
              <span class="tile-value">{kpis?.verdicts_given ? ((kpis.fp_rate ?? 0) * 100).toFixed(1) + '%' : '—'}</span>
              <span class="tile-label">FP Rate</span>
            </div>
            {#if (kpis?.training_samples ?? 0) >= 10}
              <div class="scorecard-tile">
                <span class="tile-value">{kpis?.classifier_accuracy != null ? (kpis.classifier_accuracy * 100).toFixed(1) + '%' : '—'}</span>
                <span class="tile-label">Classifier Accuracy</span>
              </div>
            {/if}
            <div class="scorecard-tile">
              <span class="tile-value">{kpis?.training_samples ?? 0}</span>
              <span class="tile-label">Training Samples</span>
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
            <!-- Backend overall -->
            <div class="health-row">
              <span class="health-dot" class:dot-healthy={healthStatus === 'healthy'} class:dot-degraded={healthStatus === 'degraded'} class:dot-unhealthy={healthStatus === 'unhealthy' || healthStatus === 'loading'}></span>
              <span class="health-label">API Backend</span>
              <span class="health-status">{healthStatus}</span>
            </div>

            <!-- Core service components from /health -->
            {#if componentHealth}
              <!-- Ollama — shows version + update badge -->
              {#if componentHealth.components.ollama}
                {@const ol = componentHealth.components.ollama}
                <div class="health-row">
                  <span class="health-dot {compDotClass(ol.status)}"></span>
                  <span class="health-label">Ollama LLM</span>
                  <span class="health-status">
                    {#if ol.status === 'ok' && ol.version}
                      v{ol.version}
                      {#if ol.update_available}
                        <span class="version-badge update" title="v{ol.latest} available — run: winget upgrade Ollama.Ollama">⬆ update</span>
                      {:else if ol.latest}
                        <span class="version-badge current">✓ latest</span>
                      {/if}
                    {:else}
                      {ol.status === 'ok' ? 'ok' : ol.detail ?? ol.status}
                    {/if}
                  </span>
                </div>
              {/if}
              <!-- Other core components -->
              {#each [['duckdb','DuckDB'],['chroma','ChromaDB'],['sqlite','SQLite']] as [key, label]}
                {@const comp = componentHealth.components[key]}
                {#if comp}
                  <div class="health-row">
                    <span class="health-dot {compDotClass(comp.status)}"></span>
                    <span class="health-label">{label}</span>
                    <span class="health-status">{comp.status === 'ok' ? 'ok' : comp.detail ?? comp.status}</span>
                  </div>
                {/if}
              {/each}
            {/if}

            <!-- Malcolm NSM (inferred from event types) -->
            <div class="health-row">
              <span class="health-dot {compDotClass(malcolmStatus(summary))}"></span>
              <span class="health-label">Malcolm NSM</span>
              <span class="health-status" title="Inferred from event type presence">{compStatusLabel(malcolmStatus(summary))}</span>
            </div>

            <!-- Zeek (inferred from event types) -->
            <div class="health-row">
              <span class="health-dot {compDotClass(zeekStatus(summary))}"></span>
              <span class="health-label">Zeek</span>
              <span class="health-status" title="Inferred from event type presence">{compStatusLabel(zeekStatus(summary))}</span>
            </div>

            <!-- Hayabusa EVTX scanner (from /health component) -->
            {#if componentHealth?.components?.hayabusa}
              {@const hay = componentHealth.components.hayabusa}
              {@const hayCount = (hay.detection_count as number) ?? 0}
              <div class="health-row">
                <span class="health-dot {hay.status === 'ok' ? 'dot-healthy' : 'dot-degraded'}"></span>
                <span class="health-label">Hayabusa</span>
                <span class="health-status hayabusa-status" title={hay.binary as string ?? 'binary not found'}>
                  {#if hay.status === 'ok'}
                    {hayCount > 0 ? `${hayCount} findings` : 'ready'}
                  {:else}
                    not found
                  {/if}
                </span>
              </div>
            {/if}

            <!-- Chainsaw EVTX scanner (from /health component) -->
            {#if componentHealth?.components?.chainsaw}
              {@const saw = componentHealth.components.chainsaw}
              {@const sawCount = (saw.detection_count as number) ?? 0}
              <div class="health-row">
                <span class="health-dot {saw.status === 'ok' ? 'dot-healthy' : 'dot-degraded'}"></span>
                <span class="health-label">Chainsaw</span>
                <span class="health-status chainsaw-status" title={saw.binary as string ?? 'binary not found'}>
                  {#if saw.status === 'ok'}
                    {sawCount > 0 ? `${sawCount} findings` : 'ready'}
                  {:else}
                    not found
                  {/if}
                </span>
              </div>
            {/if}

            <!-- MISP Threat Intelligence feed -->
            {#if componentHealth?.components?.misp}
              {@const misp = componentHealth.components.misp}
              <div class="health-row">
                <span class="health-dot {misp.status === 'ok' ? 'dot-healthy' : misp.status === 'disabled' || misp.status === 'never' ? '' : 'dot-degraded'}"></span>
                <span class="health-label">MISP TI</span>
                <span class="health-status misp-status">
                  {#if misp.status === 'disabled'}
                    disabled
                  {:else if misp.status === 'never'}
                    never synced
                  {:else if misp.status === 'ok'}
                    {(misp.ioc_count as number).toLocaleString()} IOCs
                  {:else if misp.status === 'stale'}
                    {(misp.ioc_count as number).toLocaleString()} IOCs · stale
                  {:else}
                    {misp.status}
                  {/if}
                </span>
              </div>
            {/if}

            <!-- SpiderFoot OSINT (Phase 51) -->
            {#if componentHealth?.components?.spiderfoot}
              {@const sf = componentHealth.components.spiderfoot}
              <div class="health-row">
                <span class="health-dot {sf.status === 'ok' ? 'dot-healthy' : 'dot-degraded'}"></span>
                <span class="health-label">SpiderFoot</span>
                <span class="health-status">{sf.status === 'ok' ? 'ready' : 'offline'}</span>
              </div>
            {/if}

            <!-- Reranker (Phase 54) -->
            {#if componentHealth?.components?.reranker}
              {@const rr = componentHealth.components.reranker}
              <div class="health-row">
                <span class="health-dot {rr.status === 'ok' ? 'dot-healthy' : rr.status === 'disabled' ? '' : 'dot-degraded'}"></span>
                <span class="health-label">Reranker</span>
                <span class="health-status">{rr.status === 'ok' ? 'ready' : rr.status === 'disabled' ? 'disabled' : 'offline'}</span>
              </div>
            {/if}

            <!-- Network devices -->
            {#each [['router','Router'],['firewall','Firewall'],['gmktec','GMKtec / Malcolm']] as [key, label]}
              {#if networkDevices[key] !== undefined}
                <div class="health-row">
                  <span class="health-dot" class:dot-healthy={networkDevices[key] === 'up'} class:dot-unhealthy={networkDevices[key] === 'down'}></span>
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
                <strong class="triage-sev">{stripMd(triageResult.severity_summary)}</strong>
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
                <pre class="triage-text">{stripMd(triageResult.result_text ?? '')}</pre>
              {/if}
            </div>
          {:else}
            <p class="empty-msg">No triage results yet. Run triage from the Detections page.</p>
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

    <!-- Network Topology -->
    <div class="card topo-card">
      <h3 class="card-title">Network Topology <span class="card-sub">LAN devices</span></h3>
      <svg
        class="topo-svg"
        viewBox="0 0 800 {topoData.h}"
        preserveAspectRatio="xMidYMid meet"
        xmlns="http://www.w3.org/2000/svg"
      >
        <!-- Edges -->
        {#each topoData.edges as e}
          <line x1={e.fx} y1={e.fy} x2={e.tx} y2={e.ty}
            stroke="rgba(255,255,255,0.12)" stroke-width="1.5" stroke-dasharray="5 3"/>
        {/each}

        <!-- Nodes -->
        {#each topoData.nodes as n}
          {@const c = kindColor(n.kind)}
          <g transform="translate({n.x - 65},{n.y - 20})">
            <rect width="130" height="40" rx="7" fill={c.fill} stroke={c.stroke} stroke-width="1"/>

            <!-- Kind icon -->
            {#if n.kind === 'internet'}
              <path d="M12 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0zM8 4C8 4 6 6 6 8a2 2 0 0 0 4 0c0-2-2-4-2-4z M4 8h8" stroke={c.stroke} stroke-width="1.2" fill="none" transform="translate(9,10)"/>
            {:else if n.kind === 'router'}
              <rect x="9" y="13" width="14" height="10" rx="2" stroke={c.stroke} stroke-width="1.2" fill="none"/>
              <path d="M12 13V11M16 13V10M20 13V11" stroke={c.stroke} stroke-width="1.1" stroke-linecap="round"/>
            {:else if n.kind === 'firewall'}
              <path d="M16 11L12 9v5c0 2.5 1.5 4.5 4 5 2.5-.5 4-2.5 4-5V9l-4 2z" stroke={c.stroke} stroke-width="1.2" fill="none"/>
            {:else if n.kind === 'server'}
              <rect x="9" y="11" width="14" height="4" rx="1.5" stroke={c.stroke} stroke-width="1.1" fill="none"/>
              <rect x="9" y="17" width="14" height="4" rx="1.5" stroke={c.stroke} stroke-width="1.1" fill="none"/>
              <circle cx="21" cy="13" r="1" fill={c.stroke}/>
              <circle cx="21" cy="19" r="1" fill={c.stroke}/>
            {:else}
              <rect x="9" y="12" width="14" height="10" rx="2" stroke={c.stroke} stroke-width="1.1" fill="none"/>
              <line x1="9" y1="16" x2="23" y2="16" stroke={c.stroke} stroke-width="0.9"/>
            {/if}

            <!-- Label -->
            <text x="30" y="16" font-size="10.5" font-weight="600" fill="rgba(255,255,255,0.88)" font-family="inherit">{n.label}</text>
            {#if n.sub}
              <text x="30" y="28" font-size="9" fill="rgba(255,255,255,0.38)" font-family="inherit">{n.sub}</text>
            {/if}

            <!-- Status dot (only for infra nodes) -->
            {#if n.kind !== 'device' && n.kind !== 'internet'}
              <circle cx="121" cy="8" r="4.5" fill={statusDot(n.status)}/>
            {/if}
          </g>
        {/each}
      </svg>
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
  .tile-hayabusa { color: #fbbf24; }  /* amber — matches HAYABUSA chip in DetectionsView */
  .tile-chainsaw { color: #14b8a6; }  /* teal — matches CHAINSAW chip in DetectionsView */
  .tile-privacy { color: #22d3ee; }   /* cyan — matches PRIVACY chip in DetectionsView */

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

  .hayabusa-status { color: #fbbf24; }  /* amber accent for hayabusa findings count */
  .chainsaw-status { color: #14b8a6; }  /* teal accent for chainsaw findings count */
  .misp-status     { color: #a78bfa; }  /* purple accent for MISP IOC count */

  .version-badge {
    display: inline-block;
    margin-left: 5px;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    vertical-align: middle;
  }
  .version-badge.update  { background: #f59e0b22; color: #f59e0b; border: 1px solid #f59e0b44; }
  .version-badge.current { background: #22c55e22; color: #22c55e; border: 1px solid #22c55e44; }

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

  /* ── Network topology ── */
  .topo-card { margin-top: 0; }

  .topo-svg {
    width: 100%;
    height: auto;
    display: block;
    min-height: 180px;
  }

  /* Phase 44: Feedback KPI row — flexible columns for conditional Classifier Accuracy tile */
  .feedback-kpi-row {
    grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
  }
</style>
