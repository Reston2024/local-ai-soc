<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type Detection, type KpiSnapshot, type TriageResult, type Playbook, type CARAnalytic } from '../lib/api.ts'

  let {
    onInvestigate,
    onPostureUpdate,
    onSuggestPlaybook,
  }: {
    onInvestigate?: (id: string) => void
    onPostureUpdate?: (score: number) => void
    onSuggestPlaybook?: (pb: Playbook, detectionId: string, technique: string) => void
  } = $props()

  let detections = $state<Detection[]>([])
  let total = $state(0)
  let loading = $state(true)
  let expandedId = $state<string | null>(null)
  let runningDetection = $state(false)
  let error = $state<string | null>(null)
  let severityFilter = $state('')
  let typeFilter = $state('')   // '' | 'CORR' | 'ANOMALY' | 'SIGMA'

  // Phase 44: Verdict state
  let verdicts = $state<Map<string, 'TP' | 'FP'>>(new Map())
  let toastMessage = $state<string | null>(null)
  let toastTimer: ReturnType<typeof setTimeout> | null = null
  let verdictFilter = $state(false)

  // Severity breakdowns
  let criticalCount = $derived(detections.filter(d => d.severity?.toLowerCase() === 'critical').length)
  let highCount     = $derived(detections.filter(d => d.severity?.toLowerCase() === 'high').length)
  let mediumCount   = $derived(detections.filter(d => d.severity?.toLowerCase() === 'medium').length)
  let lowCount      = $derived(detections.filter(d => d.severity?.toLowerCase() === 'low').length)

  // Naive posture: 100 - (critical*25 + high*10 + medium*4 + low*1), floored at 0
  let postureScore = $derived(
    Math.max(0, 100 - criticalCount * 25 - highCount * 10 - mediumCount * 4 - lowCount * 1)
  )

  // Type-filtered + verdict-filtered detection list for display
  let displayDetections = $derived(
    (() => {
      let base = typeFilter === 'CORR'
        ? detections.filter(d => d.rule_id?.startsWith('corr-'))
        : typeFilter === 'ANOMALY'
        ? detections.filter(d => d.rule_id?.startsWith('anomaly-'))
        : typeFilter === 'SIGMA'
        ? detections.filter(d => !d.rule_id?.startsWith('corr-') && !d.rule_id?.startsWith('anomaly-'))
        : detections
      if (verdictFilter) {
        base = base.filter(d => !verdicts.has(getDetectionId(d)))
      }
      return base
    })()
  )

  // Correlation count for badge
  let corrCount = $derived(detections.filter(d => d.rule_id?.startsWith('corr-')).length)

  // Push posture to parent whenever it changes
  $effect(() => { onPostureUpdate?.(postureScore) })

  // Live KPI state — replaces mock mttd/mttr stubs
  let kpis = $state<KpiSnapshot | null>(null)
  let kpiError = $state<string | null>(null)
  let kpiPollingInterval: ReturnType<typeof setInterval> | null = null
  // Keep activeCases as a fallback for open_cases when kpis is null
  let activeCases = $state(0)
  let ingestionOk = $state<boolean | null>(null)

  async function load() {
    loading = true
    error = null
    try {
      const res = await api.detections.list({ limit: 100, severity: severityFilter || undefined })
      detections = res.detections ?? []
      total = res.total
      // Phase 44: initialize verdicts from backend response
      const newVerdicts = new Map<string, 'TP' | 'FP'>()
      for (const det of detections) {
        if (det.verdict === 'TP' || det.verdict === 'FP') {
          newVerdicts.set(getDetectionId(det), det.verdict as 'TP' | 'FP')
        }
      }
      verdicts = newVerdicts
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  async function checkIngestion() {
    try {
      await api.health()
      ingestionOk = true
    } catch {
      ingestionOk = false
    }
  }

  async function loadKpis() {
    try {
      kpis = await api.metrics.kpis()
      kpiError = null
    } catch (e) {
      kpiError = String(e)
      // Keep stale kpis rather than nulling on transient error
    }
  }

  async function runDetection() {
    runningDetection = true
    error = null
    try {
      await api.detections.run()
      await load()
    } catch (e) {
      error = String(e)
    } finally {
      runningDetection = false
    }
  }

  onMount(async () => {
    await Promise.all([load(), checkIngestion(), loadKpis()])
  })

  $effect(() => {
    kpiPollingInterval = setInterval(loadKpis, 60_000)
    return () => { if (kpiPollingInterval) clearInterval(kpiPollingInterval) }
  })

  function severityClass(s: string) { return `badge badge-${s.toLowerCase()}` }

  function fmtTime(ts: string | undefined) {
    if (!ts) return '—'
    return new Date(ts).toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  }

  function getDetectionId(d: Detection): string { return d.detection_id ?? d.id ?? '' }

  function getEventCount(d: Detection): number {
    if (d.matched_event_ids) return d.matched_event_ids.length
    if (d.event_id) return 1
    return 0
  }

  let lastUpdated = $state(new Date())
  $effect(() => {
    if (!loading) lastUpdated = kpis ? new Date(kpis.computed_at) : new Date()
  })

  // ── Triage panel ──
  let triageResult = $state<TriageResult | null>(null)
  let triageRunning = $state(false)
  let triagePanelOpen = $state(true)
  let triageError = $state<string | null>(null)

  async function loadTriage() {
    try {
      const { result } = await api.triage.latest()
      triageResult = result
    } catch { /* triage fetch failure is non-critical */ }
  }

  $effect(() => {
    loadTriage()
    const interval = setInterval(loadTriage, 15_000)
    return () => clearInterval(interval)
  })

  async function runTriageNow() {
    triageRunning = true
    triageError = null
    try {
      await api.triage.run()
      await loadTriage()
    } catch (e) {
      triageError = String(e)
    } finally {
      triageRunning = false
    }
  }

  function fmtUpdated(d: Date) {
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  function stripMd(text: string): string {
    return text
      .replace(/\*\*/g, '')
      .replace(/\*/g, '')
      .replace(/__/g, '')
      .replace(/_/g, '')
      .trim()
  }

  // Toggle full triage report text
  let triageExpanded = $state(false)

  // Phase 38: Suggested playbook CTA
  let availablePlaybooks = $state<Playbook[]>([])
  $effect(() => {
    api.playbooks.list().then(r => { availablePlaybooks = r.playbooks }).catch(() => {})
  })

  function corrBadgeLabel(ruleId: string): string | null {
    if (!ruleId?.startsWith('corr-')) return null
    if (ruleId.startsWith('corr-portscan')) return 'PORT_SCAN'
    if (ruleId.startsWith('corr-bruteforce')) return 'BRUTE_FORCE'
    if (ruleId.startsWith('corr-beacon')) return 'BEACON'
    if (ruleId.startsWith('corr-chain')) return 'CHAIN'
    return 'CORR'
  }

  function suggestPlaybook(detection: Detection): Playbook | null {
    if (!detection.attack_technique) return null
    return availablePlaybooks.find(pb =>
      pb.trigger_conditions.some(tc =>
        tc === detection.attack_technique ||
        tc.toLowerCase() === (detection.attack_technique ?? '').toLowerCase()
      )
    ) ?? null
  }

  // Phase 44: verdict helpers
  function showToast(msg: string) {
    toastMessage = msg
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => { toastMessage = null }, 3000)
  }

  async function submitVerdict(d: Detection, newVerdict: 'TP' | 'FP') {
    const id = getDetectionId(d)
    verdicts = new Map(verdicts).set(id, newVerdict)
    showToast(newVerdict === 'TP' ? 'Marked as True Positive' : 'Marked as False Positive')
    try {
      await api.feedback.submit({
        detection_id: id, verdict: newVerdict,
        rule_id: d.rule_id, rule_name: d.rule_name, severity: d.severity
      })
    } catch { /* ML errors are silent */ }
  }
</script>

<div class="view">
  <!-- ── Triage panel ── -->
  <div class="triage-panel">
    <div class="triage-header" role="button" tabindex="0"
      onclick={() => triagePanelOpen = !triagePanelOpen}
      onkeydown={(e) => e.key === 'Enter' && (triagePanelOpen = !triagePanelOpen)}
    >
      <span class="triage-title">
        AI Triage
        {#if triageRunning}<span class="triage-running">— Analyzing…</span>{/if}
      </span>
      {#if triageRunning}<span class="triage-spinner"></span>{/if}
      <button
        class="btn btn-sm"
        style={triageRunning ? 'cursor: wait; opacity: 0.6;' : ''}
        onclick={(e) => { e.stopPropagation(); if (!triageRunning) runTriageNow() }}
      >
        Run Triage Now
      </button>
      <span class="collapse-icon">{triagePanelOpen ? '▲' : '▼'}</span>
    </div>
    {#if triagePanelOpen}
      <div class="triage-body">
        {#if triageError}
          <span class="triage-err">{triageError}</span>
        {:else if triageResult}
          <div class="triage-summary">
            <strong>{stripMd(triageResult.severity_summary)}</strong>
            <span class="triage-meta">
              {triageResult.detection_count} detections
              · {triageResult.model_name}
              · {fmtUpdated(new Date(triageResult.created_at))}
            </span>
            {#if triageResult.result_text}
              <button
                class="triage-expand-btn"
                onclick={() => triageExpanded = !triageExpanded}
              >{triageExpanded ? 'Hide Report ▲' : 'Show Full Report ▼'}</button>
              {#if triageExpanded}
                <pre class="triage-report">{stripMd(triageResult.result_text)}</pre>
              {/if}
            {/if}
          </div>
        {:else}
          <span class="triage-empty">
            No triage results yet. Click "Run Triage Now" to analyze detections.
          </span>
        {/if}
      </div>
    {/if}
  </div>

  <!-- ── Operational KPI bar ── -->
  <div class="kpi-bar">
    <!-- Severity pills -->
    <div class="kpi-group severity-group">
      <div class="severity-pill critical" class:alert={criticalCount > 0}>
        <span class="sev-dot"></span>
        <span class="sev-count">{criticalCount}</span>
        <span class="sev-label">Critical</span>
        <div class="sev-underline"></div>
      </div>
      <div class="severity-pill high" class:alert={highCount > 0}>
        <span class="sev-dot"></span>
        <span class="sev-count">{highCount}</span>
        <span class="sev-label">High</span>
        <div class="sev-underline"></div>
      </div>
      <div class="severity-pill medium" class:alert={mediumCount > 0}>
        <span class="sev-dot"></span>
        <span class="sev-count">{mediumCount}</span>
        <span class="sev-label">Medium</span>
        <div class="sev-underline"></div>
      </div>
      <div class="severity-pill low">
        <span class="sev-dot"></span>
        <span class="sev-count">{lowCount}</span>
        <span class="sev-label">Low</span>
        <div class="sev-underline"></div>
      </div>
    </div>

    <div class="kpi-divider"></div>

    <!-- Operational metrics -->
    <div class="kpi-group ops-group">
      <div class="kpi-stat" title="Mean Time to Detect">
        <span class="kpi-value">{kpis ? kpis.mttd.value.toFixed(1) + ' min' : '—'}</span>
        <span class="kpi-key">MTTD</span>
      </div>
      <div class="kpi-stat" title="Mean Time to Respond">
        <span class="kpi-value">{kpis ? kpis.mttr.value.toFixed(1) + ' min' : '—'}</span>
        <span class="kpi-key">MTTR</span>
      </div>
      <div class="kpi-stat" title="Mean Time to Contain">
        <span class="kpi-value">{kpis ? kpis.mttc.value.toFixed(1) + ' min' : '—'}</span>
        <span class="kpi-key">MTTC</span>
      </div>
      <div class="kpi-stat" title="False Positive Rate">
        <span class="kpi-value">{kpis ? (kpis.false_positive_rate.value * 100).toFixed(0) + '%' : '—'}</span>
        <span class="kpi-key">FP Rate</span>
      </div>
      <div class="kpi-stat" title="Active detection rules">
        <span class="kpi-value">{kpis ? kpis.active_rules.value : '—'}</span>
        <span class="kpi-key">Active Rules</span>
      </div>
      <div class="kpi-stat" title="Open investigation cases">
        <span class="kpi-value">{kpis ? kpis.open_cases.value : activeCases}</span>
        <span class="kpi-key">Active Cases</span>
      </div>
      <div class="kpi-stat" title="Alerts in last 24 hours">
        <span class="kpi-value">{kpis ? kpis.alert_volume_24h.value : total}</span>
        <span class="kpi-key">24h Alerts</span>
      </div>
      <div class="kpi-stat" title="Total detections loaded">
        <span class="kpi-value">{total}</span>
        <span class="kpi-key">Total</span>
      </div>
      <div class="kpi-stat ingestion" title="Ingestion pipeline health">
        {#if ingestionOk === null}
          <span class="kpi-value muted">—</span>
        {:else if ingestionOk}
          <span class="kpi-value ok">● Online</span>
        {:else}
          <span class="kpi-value warn">● Offline</span>
        {/if}
        <span class="kpi-key">Pipeline</span>
      </div>
    </div>

    <!-- Actions -->
    <div class="kpi-actions">
      <span class="last-updated" title="Last refreshed">
        {fmtUpdated(lastUpdated)}
      </span>
      <select bind:value={severityFilter} onchange={load} class="severity-select">
        <option value="">All severities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <div class="type-filter-chips">
        <button
          class="chip {typeFilter === '' ? 'chip-active' : ''}"
          onclick={() => { typeFilter = ''; }}
        >All</button>
        <button
          class="chip chip-corr {typeFilter === 'CORR' ? 'chip-active' : ''}"
          onclick={() => { typeFilter = typeFilter === 'CORR' ? '' : 'CORR'; }}
        >CORR {corrCount > 0 ? `(${corrCount})` : ''}</button>
        <button
          class="chip chip-anomaly {typeFilter === 'ANOMALY' ? 'chip-active' : ''}"
          onclick={() => { typeFilter = typeFilter === 'ANOMALY' ? '' : 'ANOMALY'; }}
        >ANOMALY</button>
        <button
          class="chip chip-sigma {typeFilter === 'SIGMA' ? 'chip-active' : ''}"
          onclick={() => { typeFilter = typeFilter === 'SIGMA' ? '' : 'SIGMA'; }}
        >SIGMA</button>
        <button
          class="chip filter-chip {verdictFilter ? 'chip-active chip-unreviewed' : ''}"
          onclick={() => verdictFilter = !verdictFilter}
        >Unreviewed</button>
      </div>
      <button class="btn" onclick={load} disabled={loading}>
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
          <path d="M13.5 8A5.5 5.5 0 1 1 8 2.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
          <path d="M8 1v3.5L10.5 3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Refresh
      </button>
      <button class="btn btn-primary" onclick={runDetection} disabled={runningDetection}>
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
          <path d="M9 1.5L3.5 9H7.5L7 14.5L12.5 7H8.5L9 1.5Z" fill="currentColor"/>
        </svg>
        {runningDetection ? 'Running…' : 'Run Detection'}
      </button>
    </div>
  </div>

  {#if error}
    <div class="error-banner">
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none" style="flex-shrink:0">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.5"/>
        <line x1="8" y1="5" x2="8" y2="8.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="8" cy="11" r="0.8" fill="currentColor"/>
      </svg>
      {error}
    </div>
  {/if}

  {#if loading}
    <div class="state-wrap">
      <div class="spinner"></div>
      <span class="state-text">Loading detections…</span>
    </div>
  {:else if detections.length === 0}
    <div class="empty-state">
      <div class="empty-icon">
        <svg width="90" height="100" viewBox="0 0 90 100" fill="none">
          <path d="M45 6L10 19V46C10 66 26 82 45 92C64 82 80 66 80 46V19L45 6Z"
            fill="rgba(0,212,255,0.06)" stroke="#00d4ff" stroke-width="1.8"/>
          <circle cx="45" cy="48" r="16" fill="none" stroke="#00d4ff" stroke-width="1.4" opacity="0.5"/>
          <circle cx="45" cy="48" r="9"  fill="none" stroke="#00d4ff" stroke-width="1.2" opacity="0.35"/>
          <circle cx="45" cy="48" r="3.5" fill="#00d4ff" opacity="0.6"/>
          <line x1="29" y1="48" x2="23" y2="48" stroke="#00d4ff" stroke-width="1.2" opacity="0.5" stroke-linecap="round"/>
          <line x1="61" y1="48" x2="67" y2="48" stroke="#00d4ff" stroke-width="1.2" opacity="0.5" stroke-linecap="round"/>
          <line x1="45" y1="32" x2="45" y2="26" stroke="#00d4ff" stroke-width="1.2" opacity="0.5" stroke-linecap="round"/>
          <line x1="45" y1="64" x2="45" y2="70" stroke="#00d4ff" stroke-width="1.2" opacity="0.5" stroke-linecap="round"/>
          <circle cx="23" cy="48" r="1.5" fill="#00d4ff" opacity="0.5"/>
          <circle cx="67" cy="48" r="1.5" fill="#00d4ff" opacity="0.5"/>
          <circle cx="45" cy="26" r="1.5" fill="#00d4ff" opacity="0.5"/>
          <circle cx="45" cy="70" r="1.5" fill="#00d4ff" opacity="0.5"/>
        </svg>
      </div>
      <h2 class="empty-title">No threats detected — All systems secure</h2>
      <p class="empty-sub">
        Events ingested and detection rules are running smoothly.<br>
        New detections will appear here in real time.
      </p>
    </div>
  {:else}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Rule</th>
            <th>Severity</th>
            <th>Tactic</th>
            <th>Technique</th>
            <th>Events</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each displayDetections as d}
            <tr
              onclick={() => { const id = getDetectionId(d); expandedId = expandedId === id ? null : id }}
              style="cursor: pointer;"
              class:row-expanded={expandedId === getDetectionId(d)}
            >
              <td class="mono ts">{fmtTime(d.fired_at)}</td>
              <td class="rule-name">
                {d.rule_name}
                {#if corrBadgeLabel(d.rule_id)}
                  <span class="corr-type-badge corr-badge-{corrBadgeLabel(d.rule_id)?.toLowerCase().replace('_', '-')}">
                    {corrBadgeLabel(d.rule_id)}
                  </span>
                {/if}
                {#if d.explanation}
                  <span class="info-tip" title={d.explanation}>
                    <svg width="11" height="11" viewBox="0 0 16 16" fill="none">
                      <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.4"/>
                      <line x1="8" y1="7" x2="8" y2="11" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
                      <circle cx="8" cy="5" r="0.8" fill="currentColor"/>
                    </svg>
                  </span>
                {/if}
                {#if verdicts.get(getDetectionId(d)) === 'TP'}
                  <span class="verdict-badge verdict-tp">TP</span>
                {:else if verdicts.get(getDetectionId(d)) === 'FP'}
                  <span class="verdict-badge verdict-fp">FP</span>
                {/if}
              </td>
              <td><span class={severityClass(d.severity)}>{d.severity}</span></td>
              <td class="tactic">
                {#if d.attack_tactic}
                  <span class="tactic-text">{d.attack_tactic}</span>
                {:else}
                  <span class="muted">—</span>
                {/if}
              </td>
              <td class="mono technique">
                {#if d.attack_technique}
                  <span class="technique-badge" title={d.attack_tactic ?? ''}>{d.attack_technique}</span>
                {:else}
                  <span class="muted">—</span>
                {/if}
              </td>
              <td class="event-count">{getEventCount(d)}</td>
              <td class="actions-cell">
                <span class="expand-chevron" title="Toggle CAR analytics">{expandedId === getDetectionId(d) ? '▾' : '▸'}</span>
                {#if onInvestigate}
                  <button
                    class="btn-investigate"
                    onclick={() => onInvestigate!(getDetectionId(d))}
                    disabled={!getDetectionId(d)}
                  >
                    Investigate →
                  </button>
                {/if}
                <!-- Phase 38: Suggested playbook CTA -->
                {#if onSuggestPlaybook}
                  {@const suggested = suggestPlaybook(d)}
                  {#if suggested}
                    <p class="suggest-cta">
                      Suggested: <button class="suggest-link"
                        onclick={() => onSuggestPlaybook!(suggested, getDetectionId(d), d.attack_technique ?? '')}>
                        {suggested.name}
                      </button>
                    </p>
                  {/if}
                {/if}
              </td>
            </tr>
            {#if expandedId === getDetectionId(d)}
              <tr class="car-panel-row">
                <td colspan="99" class="car-panel-cell">
                  {#if d.rule_id?.startsWith('corr-')}
                    <!-- Correlation expand panel -->
                    <div class="corr-expand-panel">
                      <div class="corr-expand-header">
                        <span class="corr-expand-label">Matched Event IDs</span>
                        <span class="corr-expand-count">
                          {d.matched_event_ids?.length ?? 0} events
                        </span>
                      </div>
                      {#if d.matched_event_ids && d.matched_event_ids.length > 0}
                        <div class="corr-event-id-list">
                          {#each d.matched_event_ids as eid}
                            <code class="corr-event-id">{eid}</code>
                          {/each}
                        </div>
                      {:else}
                        <p class="corr-no-events">No event IDs available for this correlation detection.</p>
                      {/if}
                      {#if d.explanation}
                        <p class="corr-explanation">{d.explanation}</p>
                      {/if}
                      <div class="verdict-row">
                        <button
                          class="verdict-btn {verdicts.get(getDetectionId(d)) === 'TP' ? 'verdict-active-tp' : ''}"
                          onclick={() => submitVerdict(d, 'TP')}
                        >&#10003; True Positive</button>
                        <button
                          class="verdict-btn {verdicts.get(getDetectionId(d)) === 'FP' ? 'verdict-active-fp' : ''}"
                          onclick={() => submitVerdict(d, 'FP')}
                        >&#10007; False Positive</button>
                      </div>
                    </div>
                  {:else}
                    <!-- Existing CAR analytics panel -->
                    {#if d.car_analytics && d.car_analytics.length > 0}
                      <div class="car-panel">
                        {#each d.car_analytics as analytic (analytic.analytic_id + analytic.technique_id)}
                          <div class="car-card">
                            <div class="car-card-header">
                              <code class="car-id-badge">{analytic.analytic_id}</code>
                              <span class="car-title">{analytic.title}</span>
                              <span class="car-coverage coverage-{analytic.coverage_level.toLowerCase()}">{analytic.coverage_level}</span>
                              <a href="https://car.mitre.org/analytics/{analytic.analytic_id}/" target="_blank" rel="noopener noreferrer" class="car-link">CAR ↗</a>
                              <a href="https://attack.mitre.org/techniques/{analytic.technique_id}/" target="_blank" rel="noopener noreferrer" class="car-link">ATT&CK ↗</a>
                            </div>
                            {#if analytic.description}
                              <p class="car-description">{analytic.description}</p>
                            {/if}
                            {#if analytic.log_sources}
                              <div class="car-meta"><span class="car-label">Log Sources:</span> {analytic.log_sources}</div>
                            {/if}
                            {#if analytic.analyst_notes}
                              <div class="car-meta"><span class="car-label">Analyst Notes:</span> {analytic.analyst_notes}</div>
                            {/if}
                            {#if analytic.pseudocode}
                              <pre class="car-pseudocode">{analytic.pseudocode}</pre>
                            {/if}
                          </div>
                        {/each}
                      </div>
                    {:else}
                      <p class="car-no-analytics">No CAR analytics available for {d.attack_technique ?? 'this detection'}.</p>
                    {/if}
                    <div class="verdict-row">
                      <button
                        class="verdict-btn {verdicts.get(getDetectionId(d)) === 'TP' ? 'verdict-active-tp' : ''}"
                        onclick={() => submitVerdict(d, 'TP')}
                      >&#10003; True Positive</button>
                      <button
                        class="verdict-btn {verdicts.get(getDetectionId(d)) === 'FP' ? 'verdict-active-fp' : ''}"
                        onclick={() => submitVerdict(d, 'FP')}
                      >&#10007; False Positive</button>
                    </div>
                  {/if}
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if toastMessage}
    <div class="verdict-toast">{toastMessage}</div>
  {/if}
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

  /* ── Triage panel ── */
  .triage-panel {
    flex-shrink: 0;
    border-bottom: 1px solid var(--border);
    background: rgba(0,212,255,0.03);
  }

  .triage-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 18px;
    cursor: pointer;
    user-select: none;
  }

  .triage-header:hover { background: rgba(255,255,255,0.02); }

  .triage-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    flex: 1;
  }

  .triage-running {
    font-weight: 400;
    color: var(--accent-cyan, #00d4ff);
    font-size: 12px;
  }

  .triage-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid var(--border);
    border-top-color: var(--accent-cyan, #00d4ff);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    flex-shrink: 0;
  }

  .collapse-icon {
    font-size: 10px;
    color: var(--text-muted);
  }

  .triage-body {
    padding: 4px 18px 10px;
  }

  .triage-summary {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .triage-summary strong {
    font-size: 13px;
    color: var(--text-primary);
  }

  .triage-meta {
    font-size: 11px;
    color: var(--text-muted);
  }

  .triage-empty {
    font-size: 12px;
    color: var(--text-muted);
  }

  .triage-err {
    font-size: 12px;
    color: var(--severity-high, #f97316);
  }

  .triage-expand-btn {
    margin-top: 6px;
    background: none;
    border: none;
    color: var(--accent, #60a5fa);
    font-size: 11px;
    cursor: pointer;
    padding: 0;
    display: block;
  }
  .triage-expand-btn:hover { text-decoration: underline; }

  .triage-report {
    margin-top: 8px;
    padding: 10px 12px;
    background: var(--bg-tertiary, #111827);
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 11px;
    line-height: 1.6;
    color: var(--text-secondary);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 320px;
    overflow-y: auto;
  }

  .btn-sm {
    font-size: 11px;
    padding: 3px 10px;
    height: 26px;
  }

  /* ── KPI bar ── */
  .kpi-bar {
    display: flex;
    align-items: center;
    gap: 0;
    padding: 0 18px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
    flex-shrink: 0;
    flex-wrap: wrap;
    min-height: 54px;
  }

  .kpi-group { display: flex; align-items: center; gap: 6px; padding: 10px 0; }
  .kpi-divider {
    width: 1px;
    height: 28px;
    background: var(--border);
    margin: 0 14px;
    flex-shrink: 0;
  }

  /* Severity pills */
  .severity-pill {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px 5px 9px;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: var(--bg-tertiary);
    position: relative;
    overflow: hidden;
    cursor: default;
    transition: border-color 0.2s;
  }

  .sev-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .sev-count {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }

  .sev-label { font-size: 11px; color: var(--text-secondary); }

  .sev-underline {
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 2px;
    border-radius: 0 0 20px 20px;
    opacity: 0.5;
  }

  .severity-pill.critical .sev-dot      { background: var(--severity-critical); box-shadow: 0 0 4px var(--severity-critical); }
  .severity-pill.critical .sev-underline { background: var(--severity-critical); }
  .severity-pill.critical.alert          { border-color: rgba(239,68,68,0.5); }

  .severity-pill.high .sev-dot          { background: var(--severity-high); box-shadow: 0 0 4px var(--severity-high); }
  .severity-pill.high .sev-underline    { background: var(--severity-high); }
  .severity-pill.high.alert             { border-color: rgba(249,115,22,0.5); }

  .severity-pill.medium .sev-dot        { background: var(--severity-medium); box-shadow: 0 0 4px var(--severity-medium); }
  .severity-pill.medium .sev-underline  { background: var(--severity-medium); }
  .severity-pill.medium.alert           { border-color: rgba(234,179,8,0.5); }

  .severity-pill.low .sev-dot           { background: var(--severity-low); }
  .severity-pill.low .sev-underline     { background: var(--severity-low); }

  /* Operational stats */
  .ops-group { gap: 16px; }

  .kpi-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    cursor: default;
  }

  .kpi-value {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
  }
  .kpi-value.ok   { color: var(--accent-green); font-size: 12px; font-weight: 600; }
  .kpi-value.warn { color: var(--accent-red);   font-size: 12px; font-weight: 600; }
  .kpi-value.muted { color: var(--text-muted); }

  .kpi-key {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: var(--text-muted);
    white-space: nowrap;
  }

  /* Actions */
  .kpi-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
    padding: 10px 0;
  }

  .last-updated {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    white-space: nowrap;
  }

  .severity-select {
    height: 32px;
    font-size: 12px;
    padding: 0 8px;
    border-radius: var(--radius-md);
  }

  /* ── States ── */
  .state-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
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

  .state-text { font-size: 13px; color: var(--text-secondary); }

  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 18px;
    padding: 40px;
  }

  .empty-icon { filter: drop-shadow(0 0 18px rgba(0,212,255,0.2)); }

  .empty-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.3px;
  }

  .empty-sub {
    font-size: 13px;
    color: var(--text-secondary);
    text-align: center;
    line-height: 1.7;
  }

  /* ── Table ── */
  .table-wrap { flex: 1; overflow-y: auto; }

  .ts { color: var(--text-secondary); font-size: 11px; white-space: nowrap; }
  .rule-name { font-weight: 500; }
  .muted { color: var(--text-muted); }
  .event-count { text-align: center; color: var(--text-secondary); }

  .tactic { font-size: 11px; }
  .tactic-text {
    color: var(--text-secondary);
    font-style: italic;
  }

  .info-tip {
    cursor: help;
    color: var(--text-muted);
    margin-left: 4px;
    vertical-align: middle;
    display: inline-flex;
  }
  .info-tip:hover { color: var(--text-secondary); }

  .technique { font-size: 11px; }
  .technique-badge {
    background: rgba(167,139,250,0.12);
    color: #a78bfa;
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 4px;
    font-family: var(--font-mono, monospace);
    border: 1px solid rgba(167,139,250,0.2);
  }

  .btn-investigate {
    font-size: 11px;
    padding: 4px 10px;
    background: rgba(0,212,255,0.07);
    color: var(--accent-cyan);
    border: 1px solid rgba(0,212,255,0.2);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-family: var(--font-sans);
    font-weight: 500;
    transition: background 0.12s, border-color 0.12s;
    white-space: nowrap;
  }
  .btn-investigate:hover { background: rgba(0,212,255,0.14); border-color: rgba(0,212,255,0.4); }
  .btn-investigate:disabled { opacity: 0.35; cursor: not-allowed; }

  .error-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 18px;
    background: rgba(239,68,68,0.08);
    color: var(--severity-critical);
    border-bottom: 1px solid rgba(239,68,68,0.2);
    font-size: 13px;
    flex-shrink: 0;
  }

  /* Phase 38: suggested playbook CTA */
  .actions-cell { vertical-align: top; }
  .suggest-cta { font-size: 11px; color: rgba(255,255,255,0.5); margin: 4px 0 0; }
  .suggest-link { background: none; border: none; color: #60a5fa; cursor: pointer; text-decoration: underline; font-size: 11px; padding: 0; }
  .suggest-link:hover { color: #93c5fd; }

  /* Phase 39: CAR analytics panel */
  .expand-chevron { margin-right: 6px; font-size: 0.75rem; color: rgba(255,255,255,0.48); }
  .row-expanded { background: rgba(255,255,255,0.04); }
  .car-panel-row td { padding: 0; }
  .car-panel-cell { padding: 8px 16px 16px 32px !important; background: rgba(0,0,0,0.25); }
  .car-panel { display: flex; flex-direction: column; gap: 12px; }
  .car-card { border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 12px; background: rgba(255,255,255,0.02); }
  .car-card-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
  .car-id-badge { font-family: monospace; font-size: 0.75rem; background: rgba(99,102,241,0.15); color: #a5b4fc; padding: 2px 6px; border-radius: 4px; }
  .car-title { font-weight: 500; font-size: 0.875rem; color: rgba(255,255,255,0.87); flex: 1; }
  .car-coverage { font-size: 0.7rem; padding: 2px 6px; border-radius: 10px; text-transform: uppercase; letter-spacing: 0.05em; }
  .coverage-low { background: rgba(245,158,11,0.15); color: #fbbf24; }
  .coverage-moderate { background: rgba(59,130,246,0.15); color: #60a5fa; }
  .coverage-high { background: rgba(34,197,94,0.15); color: #4ade80; }
  .car-link { font-size: 0.75rem; color: rgba(99,130,246,0.8); text-decoration: none; }
  .car-link:hover { text-decoration: underline; }
  .car-description { font-size: 0.8rem; color: rgba(255,255,255,0.65); margin: 0 0 8px; line-height: 1.5; }
  .car-meta { font-size: 0.78rem; color: rgba(255,255,255,0.55); margin-bottom: 4px; }
  .car-label { color: rgba(255,255,255,0.45); font-weight: 500; }
  .car-pseudocode { font-family: monospace; font-size: 0.75rem; background: rgba(0,0,0,0.4); color: #a5b4fc; padding: 10px; border-radius: 4px; overflow-x: auto; white-space: pre; margin: 8px 0 0; max-height: 200px; overflow-y: auto; }
  .car-no-analytics { font-size: 0.8rem; color: rgba(255,255,255,0.4); margin: 0; padding: 8px 0; }

  /* Phase 43: CORR type filter chips */
  .type-filter-chips {
    display: flex;
    gap: 0.4rem;
    margin-left: 0.75rem;
    align-items: center;
  }
  .chip {
    padding: 0.2rem 0.6rem;
    border-radius: 9999px;
    border: 1px solid rgba(255,255,255,0.15);
    background: transparent;
    color: rgba(255,255,255,0.6);
    font-size: 0.7rem;
    cursor: pointer;
    transition: background 0.15s;
  }
  .chip:hover { background: rgba(255,255,255,0.08); }
  .chip.chip-active { background: rgba(255,255,255,0.15); color: #fff; border-color: rgba(255,255,255,0.35); }
  .chip-corr.chip-active { background: rgba(239,68,68,0.2); border-color: rgba(239,68,68,0.5); color: #fca5a5; }
  .chip-anomaly.chip-active { background: rgba(245,158,11,0.2); border-color: rgba(245,158,11,0.4); color: #fcd34d; }
  .chip-sigma.chip-active { background: rgba(59,130,246,0.2); border-color: rgba(59,130,246,0.4); color: #93c5fd; }

  /* Phase 43: Correlation type badge on detection rows */
  .corr-type-badge {
    display: inline-block;
    padding: 0.1rem 0.45rem;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    margin-left: 0.4rem;
    vertical-align: middle;
  }
  .corr-badge-port-scan { background: rgba(239,68,68,0.2); color: #fca5a5; border: 1px solid rgba(239,68,68,0.35); }
  .corr-badge-brute-force { background: rgba(239,68,68,0.3); color: #ef4444; border: 1px solid rgba(239,68,68,0.5); }
  .corr-badge-beacon { background: rgba(168,85,247,0.2); color: #d8b4fe; border: 1px solid rgba(168,85,247,0.35); }
  .corr-badge-chain { background: rgba(239,68,68,0.4); color: #fff; border: 1px solid rgba(239,68,68,0.6); }

  /* Phase 43: Correlation expand panel */
  .corr-expand-panel {
    padding: 0.75rem 1rem;
    background: rgba(239,68,68,0.05);
    border-top: 1px solid rgba(239,68,68,0.15);
  }
  .corr-expand-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }
  .corr-expand-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: rgba(255,255,255,0.7);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .corr-expand-count {
    font-size: 0.7rem;
    color: rgba(255,255,255,0.4);
  }
  .corr-event-id-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    max-height: 200px;
    overflow-y: auto;
  }
  .corr-event-id {
    display: inline-block;
    padding: 0.15rem 0.4rem;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 4px;
    font-size: 0.65rem;
    font-family: monospace;
    color: rgba(255,255,255,0.6);
    cursor: default;
  }
  .corr-no-events {
    font-size: 0.75rem;
    color: rgba(255,255,255,0.35);
    margin: 0;
  }
  .corr-explanation {
    margin-top: 0.5rem;
    font-size: 0.75rem;
    color: rgba(255,255,255,0.5);
    font-style: italic;
  }

  /* Phase 44: verdict badges, buttons, toast */
  .verdict-badge { display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-left: 4px; }
  .verdict-tp { background: rgba(34,197,94,0.2); color: #22c55e; }
  .verdict-fp { background: rgba(239,68,68,0.2); color: #ef4444; }
  .verdict-row { display: flex; gap: 8px; padding: 12px 0 4px; border-top: 1px solid rgba(255,255,255,0.08); margin-top: 12px; }
  .verdict-btn { padding: 6px 14px; border: 1px solid rgba(255,255,255,0.2); border-radius: 6px; background: transparent; color: rgba(255,255,255,0.7); cursor: pointer; font-size: 13px; }
  .verdict-btn:hover { background: rgba(255,255,255,0.06); }
  .verdict-active-tp { border-color: #22c55e; color: #22c55e; background: rgba(34,197,94,0.1); }
  .verdict-active-fp { border-color: #ef4444; color: #ef4444; background: rgba(239,68,68,0.1); }
  .verdict-toast { position: fixed; bottom: 24px; right: 24px; background: rgba(30,30,30,0.95); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; padding: 10px 18px; color: rgba(255,255,255,0.9); font-size: 13px; z-index: 1000; box-shadow: 0 4px 16px rgba(0,0,0,0.4); }
  .chip-unreviewed.chip-active { background: rgba(99,102,241,0.2); border-color: rgba(99,102,241,0.4); color: #a5b4fc; }
</style>
