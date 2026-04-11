<script lang="ts">
  import { api, getDownloadUrl } from '../lib/api.ts'
  import type { Report, MitreCoverageResponse, TrendsResponse, TemplateMeta } from '../lib/api.ts'
  import * as d3 from 'd3'

  let {
    initialTab = '',
    initialCaseId = '',
    initialRunId = '',
  }: { initialTab?: string; initialCaseId?: string; initialRunId?: string } = $props()

  let activeTab = $state<'reports' | 'mitre' | 'trends' | 'compliance' | 'templates'>(
    (initialTab as any) || 'reports'
  )

  // Reports tab
  let reports = $state<Report[]>([])
  let reportsLoading = $state(false)
  let reportsError = $state('')
  let generating = $state(false)
  let execPeriodStart = $state(new Date(Date.now() - 30*24*3600*1000).toISOString().slice(0,10))
  let execPeriodEnd   = $state(new Date().toISOString().slice(0,10))

  // MITRE tab
  let mitreCoverage = $state<MitreCoverageResponse | null>(null)
  let mitreLoading = $state(false)
  let mitreError = $state('')

  // Trends tab
  let trendsData = $state<TrendsResponse | null>(null)
  let trendsLoading = $state(false)
  let trendsError = $state('')
  let trendsSvgEl = $state<SVGSVGElement | null>(null)

  // Compliance tab
  let complianceFramework = $state<'nist-csf' | 'thehive'>('nist-csf')
  let complianceDownloading = $state(false)

  // Templates tab
  let templateMeta = $state<TemplateMeta | null>(null)
  let templateMetaLoading = $state(false)
  let templateMetaError = $state('')
  let cardGenerating = $state<Record<string, boolean>>({})
  let cardLastReport = $state<Record<string, Report | null>>({})
  let selectedCaseId = $state(initialCaseId)
  let selectedRunId = $state(initialRunId)
  let selectedActorName = $state('')

  $effect(() => {
    if (activeTab === 'reports' && reports.length === 0 && !reportsLoading) loadReports()
    if (activeTab === 'mitre' && !mitreCoverage && !mitreLoading) loadMitre()
    if (activeTab === 'trends' && !trendsData && !trendsLoading) loadTrends()
    if (activeTab === 'templates' && !templateMeta && !templateMetaLoading) loadTemplateMeta()
  })

  $effect(() => {
    if (trendsData && trendsSvgEl) renderTrendsChart()
  })

  async function loadReports() {
    reportsLoading = true; reportsError = ''
    try { const r = await api.reports.list(); reports = r.reports }
    catch (e: any) { reportsError = e.message }
    finally { reportsLoading = false }
  }

  async function generateExecutive() {
    generating = true
    try {
      await api.reports.generateExecutive({ period_start: execPeriodStart, period_end: execPeriodEnd })
      await loadReports()
    } catch (e: any) { reportsError = e.message }
    finally { generating = false }
  }

  async function loadMitre() {
    mitreLoading = true; mitreError = ''
    try { mitreCoverage = await api.analytics.mitreCoverage() }
    catch (e: any) { mitreError = e.message }
    finally { mitreLoading = false }
  }

  async function loadTrends() {
    trendsLoading = true; trendsError = ''
    try { trendsData = await api.analytics.trends({ metric: 'mttd,mttr,alert_volume', days: 30 }) }
    catch (e: any) { trendsError = e.message }
    finally { trendsLoading = false }
  }

  async function loadTemplateMeta() {
    templateMetaLoading = true; templateMetaError = ''
    try { templateMeta = await api.reports.templateMeta() }
    catch (e: any) { templateMetaError = e.message }
    finally { templateMetaLoading = false }
  }

  async function generateTemplate(type: string, params?: Record<string, string>) {
    cardGenerating = { ...cardGenerating, [type]: true }
    try {
      const report = await api.reports.generateTemplate(type, params)
      cardLastReport = { ...cardLastReport, [type]: report }
      // refresh reports list so generated template appears there
      reports = []
    } catch (e: any) {
      templateMetaError = e.message
    } finally {
      cardGenerating = { ...cardGenerating, [type]: false }
    }
  }

  function renderTrendsChart() {
    if (!trendsSvgEl || !trendsData) return
    const svg = d3.select(trendsSvgEl)
    svg.selectAll('*').remove()
    const W = 640, H = 220, margin = { top: 20, right: 20, bottom: 30, left: 50 }
    const w = W - margin.left - margin.right
    const h = H - margin.top - margin.bottom
    svg.attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('height', H)
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
    const COLORS: Record<string, string> = { mttd: '#f87171', mttr: '#60a5fa', alert_volume: '#34d399' }
    const metricKeys = Object.keys(trendsData).filter(k => (trendsData as TrendsResponse)[k]?.length > 0)
    if (metricKeys.length === 0) {
      g.append('text').attr('x', w/2).attr('y', h/2).attr('text-anchor', 'middle')
        .attr('fill', '#6b7280').attr('font-size', '13px').text('No trend data yet — snapshots will accumulate daily')
      return
    }
    const allDates = metricKeys.flatMap(k => (trendsData as TrendsResponse)[k].map(d => new Date(d.date)))
    const xScale = d3.scaleTime().domain(d3.extent(allDates) as [Date,Date]).range([0, w])
    const allValues = metricKeys.flatMap(k => (trendsData as TrendsResponse)[k].map(d => d.value))
    const yScale = d3.scaleLinear().domain([0, d3.max(allValues) ?? 1]).nice().range([h, 0])
    g.append('g').attr('transform', `translate(0,${h})`).call(d3.axisBottom(xScale).ticks(6))
    g.append('g').call(d3.axisLeft(yScale).ticks(4))
    const line = d3.line<{date: string; value: number}>()
      .x(d => xScale(new Date(d.date)))
      .y(d => yScale(d.value))
      .curve(d3.curveMonotoneX)
    metricKeys.forEach(key => {
      g.append('path')
        .datum((trendsData as TrendsResponse)[key])
        .attr('fill', 'none')
        .attr('stroke', COLORS[key] ?? '#a78bfa')
        .attr('stroke-width', 2)
        .attr('d', line)
    })
    metricKeys.forEach((key, i) => {
      const lx = w - 120, ly = i * 18
      g.append('line').attr('x1', lx).attr('x2', lx+16).attr('y1', ly+7).attr('y2', ly+7)
        .attr('stroke', COLORS[key] ?? '#a78bfa').attr('stroke-width', 2)
      g.append('text').attr('x', lx+20).attr('y', ly+11).attr('fill', '#d1d5db').attr('font-size', '11px').text(key)
    })
  }

  function downloadCompliance() {
    complianceDownloading = true
    const url = api.reports.complianceDownloadUrl(complianceFramework)
    const a = document.createElement('a')
    a.href = url; a.download = `${complianceFramework}-evidence.zip`
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
    setTimeout(() => { complianceDownloading = false }, 1500)
  }

  function openPdf(reportId: string) {
    window.open(api.reports.pdfUrl(reportId), '_blank')
  }

  function humanizeType(type: string): string {
    return type.replace(/^template_/, '').replace(/_/g, ' ')
  }

  function typeBadgeClass(type: string): string {
    if (type === 'investigation') return 'badge-investigation'
    if (type === 'executive') return 'badge-executive'
    return 'badge-template'
  }
</script>

<div class="view">
  <div class="view-header">
    <div class="header-left">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
      <h1>Reporting</h1>
    </div>
  </div>

  <div class="tab-bar">
    {#each [['reports','Reports'], ['mitre','ATT&CK Coverage'], ['trends','Trends'], ['compliance','Compliance Export'], ['templates','Templates']] as [id, label]}
      <button class="tab-btn" class:active={activeTab === id}
        onclick={() => activeTab = id as 'reports' | 'mitre' | 'trends' | 'compliance' | 'templates'}
      >{label}</button>
    {/each}
  </div>

  <div class="content">
    {#if activeTab === 'reports'}
      <div class="card">
        <h2>Generate Executive Report</h2>
        <div class="form-row">
          <label>From <input type="date" bind:value={execPeriodStart} /></label>
          <label>To <input type="date" bind:value={execPeriodEnd} /></label>
          <button class="btn btn-primary" onclick={generateExecutive} disabled={generating}>
            {generating ? 'Generating…' : 'Generate'}
          </button>
        </div>
        {#if reportsError}<p class="error">{reportsError}</p>{/if}
      </div>
      <div class="card">
        <div class="card-header">
          <h2>Generated Reports</h2>
          <button class="btn btn-sm" onclick={loadReports} disabled={reportsLoading}>Refresh</button>
        </div>
        {#if reportsLoading}<p class="muted">Loading…</p>
        {:else if reports.length === 0}<p class="muted">No reports generated yet.</p>
        {:else}
          <table class="data-table">
            <thead><tr><th>Title</th><th>Type</th><th>Created</th><th></th></tr></thead>
            <tbody>
              {#each reports as r}
                <tr>
                  <td>{r.title}</td>
                  <td><span class="badge {typeBadgeClass(r.type)}">{humanizeType(r.type)}</span></td>
                  <td class="muted">{new Date(r.created_at).toLocaleString()}</td>
                  <td><button class="btn btn-sm" onclick={() => openPdf(r.id)}>PDF</button></td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    {/if}

    {#if activeTab === 'mitre'}
      {#if mitreLoading}<p class="muted">Loading coverage matrix…</p>
      {:else if mitreError}<p class="error">{mitreError}</p>
      {:else if mitreCoverage}
        <div class="mitre-grid">
          {#each mitreCoverage.tactics as tactic}
            {@const techniques = Object.entries(mitreCoverage.coverage[tactic] ?? {})}
            <div class="tactic-col">
              <div class="tactic-header">{tactic}</div>
              {#if techniques.length === 0}
                <div class="technique-cell not_covered">—</div>
              {:else}
                {#each techniques as [tid, entry]}
                  <div class="technique-cell {entry.status}" title="{tid}: {entry.sources.join(', ')}">{tid}</div>
                {/each}
              {/if}
            </div>
          {/each}
        </div>
        <div class="legend">
          <span class="legend-item detected">Detected</span>
          <span class="legend-item playbook_covered">Playbook Covered</span>
          <span class="legend-item hunted">Hunted</span>
          <span class="legend-item not_covered">Not Covered</span>
        </div>
      {:else}
        <p class="muted">No coverage data available.</p>
      {/if}
    {/if}

    {#if activeTab === 'trends'}
      <div class="card">
        <div class="card-header">
          <h2>KPI Trends — Last 30 Days</h2>
          <button class="btn btn-sm" onclick={loadTrends} disabled={trendsLoading}>Refresh</button>
        </div>
        {#if trendsLoading}<p class="muted">Loading…</p>
        {:else if trendsError}<p class="error">{trendsError}</p>
        {:else}
          <svg bind:this={trendsSvgEl}></svg>
          <p class="muted chart-note">MTTD (red) · MTTR (blue) · Alert Volume (green). Snapshots computed daily at midnight.</p>
        {/if}
      </div>
    {/if}

    {#if activeTab === 'compliance'}
      <div class="card">
        <h2>Export Compliance Evidence Package</h2>
        <p class="muted">Download a ZIP archive of structured evidence mapped to a compliance framework.</p>
        <div class="form-row">
          <label>Framework
            <select bind:value={complianceFramework}>
              <option value="nist-csf">NIST CSF 2.0</option>
              <option value="thehive">TheHive Alert/Case (JSON)</option>
            </select>
          </label>
          <button class="btn btn-primary" onclick={downloadCompliance} disabled={complianceDownloading}>
            {complianceDownloading ? 'Preparing…' : 'Download ZIP'}
          </button>
        </div>
        <div class="framework-desc">
          {#if complianceFramework === 'nist-csf'}
            <p>Exports evidence JSON for each NIST CSF 2.0 function (GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER) plus a human-readable summary.html.</p>
          {:else}
            <p>Exports investigations as TheHive 5 Alert and Case JSON records — import directly into a TheHive instance.</p>
          {/if}
        </div>
      </div>
    {/if}

    {#if activeTab === 'templates'}
      {#if templateMetaLoading}
        <p class="muted">Loading template data…</p>
      {:else if templateMetaError}
        <p class="error">{templateMetaError}</p>
      {:else}
        <div class="template-grid">

          <!-- Card 1: Session Log -->
          <div class="template-card">
            <div class="card-header">
              <h3>Session Log</h3>
              <span class="data-badge">24h rolling window</span>
            </div>
            <p class="card-desc">Daily operational record covering the last 24 hours of SOC activity.</p>
            <div class="card-actions">
              {#if cardLastReport['template_session_log']}
                <a class="btn btn-primary"
                  href={api.reports.pdfUrl(cardLastReport['template_session_log']!.id)}
                  target="_blank">Download PDF</a>
                <button class="btn btn-secondary"
                  onclick={() => generateTemplate('template_session_log')}
                  disabled={cardGenerating['template_session_log']}>
                  {cardGenerating['template_session_log'] ? 'Generating…' : 'Re-generate'}
                </button>
              {:else}
                <button class="btn btn-primary"
                  onclick={() => generateTemplate('template_session_log')}
                  disabled={cardGenerating['template_session_log']}>
                  {cardGenerating['template_session_log'] ? 'Generating…' : 'Generate'}
                </button>
              {/if}
            </div>
          </div>

          <!-- Card 2: Security Incident Report -->
          <div class="template-card">
            <div class="card-header">
              <h3>Security Incident Report</h3>
              <span class="data-badge">{templateMeta?.investigations ?? 0} investigations available</span>
            </div>
            <p class="card-desc">Formal IR record tied to an investigation case.</p>
            {#if templateMeta && templateMeta.case_list.length > 0}
              <select class="card-select" bind:value={selectedCaseId}>
                <option value="">— select case —</option>
                {#each templateMeta.case_list as c}
                  <option value={c.case_id}>{c.title || c.case_id.slice(0,12)}</option>
                {/each}
              </select>
            {/if}
            <div class="card-actions">
              {#if cardLastReport['template_incident']}
                <a class="btn btn-primary"
                  href={api.reports.pdfUrl(cardLastReport['template_incident']!.id)}
                  target="_blank">Download PDF</a>
                <button class="btn btn-secondary"
                  onclick={() => generateTemplate('template_incident', { case_id: selectedCaseId })}
                  disabled={cardGenerating['template_incident']}>
                  {cardGenerating['template_incident'] ? 'Generating…' : 'Re-generate'}
                </button>
              {:else}
                <button class="btn btn-primary"
                  onclick={() => generateTemplate('template_incident', { case_id: selectedCaseId })}
                  disabled={cardGenerating['template_incident']}>
                  {cardGenerating['template_incident'] ? 'Generating…' : 'Generate'}
                </button>
              {/if}
            </div>
          </div>

          <!-- Card 3: Playbook Execution Log -->
          <div class="template-card">
            <div class="card-header">
              <h3>Playbook Execution Log</h3>
              <span class="data-badge">{templateMeta?.playbook_runs ?? 0} runs available</span>
            </div>
            <p class="card-desc">Step-by-step playbook run audit trail.</p>
            {#if templateMeta && templateMeta.run_list.length > 0}
              <select class="card-select" bind:value={selectedRunId}>
                <option value="">— select run —</option>
                {#each templateMeta.run_list as r}
                  <option value={r.run_id}>{r.playbook_id} · {r.status} · {new Date(r.started_at).toLocaleDateString()}</option>
                {/each}
              </select>
            {/if}
            <div class="card-actions">
              {#if cardLastReport['template_playbook_log']}
                <a class="btn btn-primary"
                  href={api.reports.pdfUrl(cardLastReport['template_playbook_log']!.id)}
                  target="_blank">Download PDF</a>
                <button class="btn btn-secondary"
                  onclick={() => generateTemplate('template_playbook_log', { run_id: selectedRunId })}
                  disabled={cardGenerating['template_playbook_log']}>
                  {cardGenerating['template_playbook_log'] ? 'Generating…' : 'Re-generate'}
                </button>
              {:else}
                <button class="btn btn-primary"
                  onclick={() => generateTemplate('template_playbook_log', { run_id: selectedRunId })}
                  disabled={cardGenerating['template_playbook_log']}>
                  {cardGenerating['template_playbook_log'] ? 'Generating…' : 'Generate'}
                </button>
              {/if}
            </div>
          </div>

          <!-- Card 4: Post-Incident Review -->
          <div class="template-card">
            <div class="card-header">
              <h3>Post-Incident Review</h3>
              <span class="data-badge">{templateMeta?.closed_cases ?? 0} closed cases</span>
            </div>
            <p class="card-desc">Closed-case retrospective analysis.</p>
            {#if templateMeta}
              {@const closedCases = templateMeta.case_list.filter(c => c.case_status === 'closed')}
              {#if closedCases.length > 0}
                <select class="card-select" bind:value={selectedCaseId}>
                  <option value="">— select closed case —</option>
                  {#each closedCases as c}
                    <option value={c.case_id}>{c.title || c.case_id.slice(0,12)}</option>
                  {/each}
                </select>
              {/if}
            {/if}
            <div class="card-actions">
              {#if cardLastReport['template_pir']}
                <a class="btn btn-primary"
                  href={api.reports.pdfUrl(cardLastReport['template_pir']!.id)}
                  target="_blank">Download PDF</a>
                <button class="btn btn-secondary"
                  onclick={() => generateTemplate('template_pir', { case_id: selectedCaseId })}
                  disabled={cardGenerating['template_pir']}>
                  {cardGenerating['template_pir'] ? 'Generating…' : 'Re-generate'}
                </button>
              {:else}
                <button class="btn btn-primary"
                  onclick={() => generateTemplate('template_pir', { case_id: selectedCaseId })}
                  disabled={cardGenerating['template_pir']}>
                  {cardGenerating['template_pir'] ? 'Generating…' : 'Generate'}
                </button>
              {/if}
            </div>
          </div>

          <!-- Card 5: Threat Intelligence Bulletin -->
          <div class="template-card">
            <div class="card-header">
              <h3>Threat Intelligence Bulletin</h3>
              <span class="data-badge">{templateMeta?.actors ?? 0} actors loaded</span>
            </div>
            <p class="card-desc">Actor-focused TTP + IOC bulletin.</p>
            {#if templateMeta && templateMeta.actor_list.length > 0}
              <select class="card-select" bind:value={selectedActorName}>
                <option value="">— select actor —</option>
                {#each templateMeta.actor_list as a}
                  <option value={a.name}>{a.name}</option>
                {/each}
              </select>
            {:else}
              <input class="card-select" type="text" placeholder="Actor name…" bind:value={selectedActorName} />
            {/if}
            <div class="card-actions">
              {#if cardLastReport['template_ti_bulletin']}
                <a class="btn btn-primary"
                  href={api.reports.pdfUrl(cardLastReport['template_ti_bulletin']!.id)}
                  target="_blank">Download PDF</a>
                <button class="btn btn-secondary"
                  onclick={() => generateTemplate('template_ti_bulletin', { actor_name: selectedActorName })}
                  disabled={cardGenerating['template_ti_bulletin']}>
                  {cardGenerating['template_ti_bulletin'] ? 'Generating…' : 'Re-generate'}
                </button>
              {:else}
                <button class="btn btn-primary"
                  onclick={() => generateTemplate('template_ti_bulletin', { actor_name: selectedActorName })}
                  disabled={cardGenerating['template_ti_bulletin']}>
                  {cardGenerating['template_ti_bulletin'] ? 'Generating…' : 'Generate'}
                </button>
              {/if}
            </div>
          </div>

          <!-- Card 6: Severity & Confidence Reference — single Download PDF button, no swap state -->
          <div class="template-card">
            <div class="card-header">
              <h3>Severity &amp; Confidence Reference</h3>
              <span class="data-badge">static reference card</span>
            </div>
            <p class="card-desc">Static SOC reference card for severity and confidence scoring.</p>
            <div class="card-actions">
              <button class="btn btn-primary"
                onclick={async () => {
                  cardGenerating = { ...cardGenerating, template_severity_ref: true }
                  try {
                    const report = await api.reports.generateTemplate('template_severity_ref')
                    window.open(api.reports.pdfUrl(report.id), '_blank')
                  } catch (e: any) { templateMetaError = e.message }
                  finally { cardGenerating = { ...cardGenerating, template_severity_ref: false } }
                }}
                disabled={cardGenerating['template_severity_ref']}>
                {cardGenerating['template_severity_ref'] ? 'Generating…' : 'Download PDF'}
              </button>
            </div>
          </div>

        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
  .view-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
  .header-left { display: flex; align-items: center; gap: 10px; }
  .header-left h1 { font-size: 18px; font-weight: 600; margin: 0; }
  .tab-bar { display: flex; border-bottom: 1px solid var(--border); background: var(--bg-secondary); flex-shrink: 0; }
  .tab-btn { font-size: 13px; padding: 10px 16px; border: none; background: transparent; cursor: pointer; color: var(--text-secondary); border-bottom: 2px solid transparent; }
  .tab-btn.active { color: #fbbf24; border-bottom-color: #fbbf24; }
  .tab-btn:hover:not(.active) { color: #e5e7eb; }
  .content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
  .card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md, 6px); padding: 16px; }
  .card h2 { font-size: 14px; font-weight: 600; margin: 0 0 12px; }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .card-header h2 { margin: 0; }
  .form-row { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }
  .form-row label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-secondary); }
  input[type=date], select { font-size: 12px; padding: 5px 8px; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-md, 4px); color: inherit; }
  .mitre-grid { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 8px; }
  .tactic-col { display: flex; flex-direction: column; gap: 3px; min-width: 90px; }
  .tactic-header { font-size: 10px; font-weight: 600; color: var(--text-secondary); text-transform: capitalize; padding: 4px; background: var(--bg-secondary); border-radius: 4px; text-align: center; }
  .technique-cell { font-size: 10px; padding: 4px 6px; border-radius: 3px; cursor: default; text-align: center; }
  .technique-cell.detected { background: rgba(34,197,94,0.2); color: #22c55e; border: 1px solid rgba(34,197,94,0.3); }
  .technique-cell.playbook_covered { background: rgba(59,130,246,0.2); color: #3b82f6; border: 1px solid rgba(59,130,246,0.3); }
  .technique-cell.hunted { background: rgba(234,179,8,0.2); color: #eab308; border: 1px solid rgba(234,179,8,0.3); }
  .technique-cell.not_covered { background: rgba(55,65,81,0.3); color: #6b7280; border: 1px solid rgba(55,65,81,0.4); }
  .legend { display: flex; gap: 16px; margin-top: 12px; flex-wrap: wrap; }
  .legend-item { font-size: 12px; padding: 3px 10px; border-radius: 3px; }
  .legend-item.detected { background: rgba(34,197,94,0.2); color: #22c55e; }
  .legend-item.playbook_covered { background: rgba(59,130,246,0.2); color: #3b82f6; }
  .legend-item.hunted { background: rgba(234,179,8,0.2); color: #eab308; }
  .legend-item.not_covered { background: rgba(55,65,81,0.3); color: #6b7280; }
  .data-table { width: 100%; border-collapse: collapse; }
  .data-table td, .data-table th { padding: 8px 10px; font-size: 13px; border-bottom: 1px solid var(--border); text-align: left; }
  .data-table th { font-weight: 600; }
  .badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
  .badge-investigation { background: rgba(251,191,36,0.2); color: #fbbf24; }
  .badge-executive { background: rgba(59,130,246,0.2); color: #60a5fa; }
  .badge-template { background: rgba(167,139,250,0.2); color: #a78bfa; }
  .btn { font-size: 13px; padding: 6px 14px; border-radius: var(--radius-md, 4px); border: 1px solid var(--border); cursor: pointer; background: var(--bg-secondary); color: inherit; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-primary { background: #fbbf24; color: #111; border-color: #fbbf24; font-weight: 600; }
  .btn-primary:hover:not(:disabled) { background: #f59e0b; }
  .btn-sm { font-size: 12px; padding: 4px 10px; }
  .muted { color: var(--text-secondary); font-size: 13px; margin: 0; }
  .error { color: #f87171; font-size: 13px; margin: 0; }
  .chart-note { font-size: 11px; margin-top: 8px; }
  .framework-desc { margin-top: 12px; padding: 12px; background: var(--bg-secondary); border-radius: var(--radius-md, 4px); }
  .framework-desc p { margin: 0; font-size: 13px; color: var(--text-secondary); }
  /* Template grid */
  .template-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  @media (max-width: 900px) { .template-grid { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 600px) { .template-grid { grid-template-columns: 1fr; } }
  .template-card { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 8px; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
  .template-card .card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 0; }
  .template-card .card-header h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--text-primary); }
  .data-badge { font-size: 11px; background: rgba(251,191,36,0.15); color: #fbbf24; border-radius: 4px; padding: 2px 6px; white-space: nowrap; flex-shrink: 0; }
  .card-desc { font-size: 12px; color: var(--text-secondary); margin: 0; line-height: 1.4; }
  .card-select { width: 100%; background: var(--bg-primary); border: 1px solid var(--border); color: var(--text-primary); padding: 5px 8px; border-radius: 4px; font-size: 12px; }
  .card-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: auto; }
  .btn-secondary { background: transparent; border: 1px solid var(--border); color: var(--text-secondary); font-size: 12px; padding: 5px 12px; }
  .btn-secondary:hover { color: var(--text-primary); }
</style>
