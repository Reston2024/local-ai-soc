<script lang="ts">
  import { onDestroy } from 'svelte'
  import { api } from '../lib/api.ts'
  import { score, topThreats, explain, type ThreatItem, type ExplainResponse } from '../lib/api.ts'

  let { detectionId = '' }: { detectionId?: string } = $props()

  let investigation = $state<any>(null)
  let loading = $state(false)
  let error = $state('')
  let selectedNode = $state<any>(null)
  let cytoscapeEl: HTMLElement | undefined = $state()
  let cy: any = null

  // Phase 9 state
  let topEntities = $state<ThreatItem[]>([])
  let explanation = $state<ExplainResponse | null>(null)
  let explainLoading = $state(false)
  let showExplanation = $state(false)

  // Load top threats when component mounts or detection changes
  $effect(() => {
    topThreats(5).then(r => { topEntities = r.threats }).catch(() => {})
  })

  async function loadExplanation(detectionId: string) {
    explainLoading = true
    try {
      explanation = await explain({ detection_id: detectionId })
    } catch {
      explanation = null
    } finally {
      explainLoading = false
    }
  }

  // Load investigation when detectionId changes
  $effect(() => {
    if (detectionId) {
      loadInvestigation(detectionId)
    } else {
      investigation = null
      selectedNode = null
    }
  })

  // Build Cytoscape graph after investigation loads
  $effect(() => {
    if (investigation?.graph && cytoscapeEl) {
      renderGraph()
    }
  })

  async function loadInvestigation(id: string) {
    loading = true
    error = ''
    investigation = null
    selectedNode = null
    try {
      investigation = await api.investigate(id)
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  function renderGraph() {
    if (!cytoscapeEl || !investigation?.graph) return

    import('cytoscape').then(({ default: cytoscape }) => {
      if (cy) cy.destroy()

      const typeColors: Record<string, string> = {
        process: '#ef4444',
        host: '#3b82f6',
        user: '#10b981',
        ip: '#f59e0b',
        domain: '#8b5cf6',
        file: '#6b7280',
        detection: '#ec4899',
        attack_technique: '#dc2626',
      }

      cy = cytoscape({
        container: cytoscapeEl,
        elements: investigation.graph.elements,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': (el: any) => typeColors[el.data('entity_type')] ?? '#6b7280',
              'label': 'data(label)',
              'color': '#e2e8f0',
              'font-size': '10px',
              'text-valign': 'bottom',
              'text-halign': 'center',
              'text-margin-y': '4px',
              'width': 36,
              'height': 36,
              'border-width': (el: any) => el.data('severity') === 'critical' ? 3 : 1,
              'border-color': (el: any) => el.data('severity') === 'critical' ? '#ef4444' : '#374151',
            }
          },
          {
            selector: 'edge',
            style: {
              'line-color': '#374151',
              'target-arrow-color': '#374151',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              'label': 'data(label)',
              'color': '#9ca3af',
              'font-size': '9px',
              'text-rotation': 'autorotate',
              'width': 1.5,
            }
          },
          {
            selector: 'node:selected',
            style: {
              'border-color': '#60a5fa',
              'border-width': 3,
            }
          },
          // Risk score color tiers — Phase 9
          {
            selector: 'node[risk_score > 80]',
            style: { 'border-color': '#ef4444', 'border-width': 4 }  // red — critical
          },
          {
            selector: 'node[risk_score > 60][risk_score <= 80]',
            style: { 'border-color': '#f97316', 'border-width': 3 }  // orange — high
          },
          {
            selector: 'node[risk_score > 30][risk_score <= 60]',
            style: { 'border-color': '#eab308', 'border-width': 2 }  // yellow — moderate
          },
          {
            selector: 'node[risk_score <= 30]',
            style: { 'border-color': '#22c55e', 'border-width': 1 }  // green — low
          },
        ],
        layout: { name: 'cose', animate: false, padding: 20, nodeRepulsion: 4000 } as any,
      })

      cy.on('tap', 'node', (evt: any) => {
        selectedNode = evt.target.data()
      })

      cy.on('tap', (evt: any) => {
        if (evt.target === cy) selectedNode = null
      })
    })
  }

  onDestroy(() => {
    if (cy) cy.destroy()
  })
</script>

<div class="investigation-panel">
  {#if !detectionId}
    <div class="empty-state">
      <p>Select a detection from the Detections tab to start investigating.</p>
    </div>
  {:else if loading}
    <div class="loading">Loading investigation...</div>
  {:else if error}
    <div class="error">{error}</div>
  {:else if investigation}
    <!-- Summary bar -->
    <div class="summary-bar">
      <span class="summary-text">{investigation.summary ?? 'Investigation complete'}</span>
      <span class="technique-badges">
        {#each investigation.techniques ?? [] as t}
          <span class="technique-badge" title={t.tactic ?? ''}>{t.technique_id ?? t}</span>
        {/each}
      </span>
    </div>

    <div class="investigation-layout">
      <!-- Left: Graph (60%) -->
      <div class="graph-section">
        <h3 class="section-title">Entity Graph</h3>
        <div class="graph-container" bind:this={cytoscapeEl}></div>
        {#if selectedNode}
          <div class="node-detail">
            <span class="node-type">{selectedNode.entity_type ?? selectedNode.type ?? 'node'}</span>
            <span class="node-label">{selectedNode.label}</span>
            {#if selectedNode.command_line}
              <code class="node-cmd">{selectedNode.command_line}</code>
            {/if}
            {#if selectedNode.severity}
              <span class="badge badge-{selectedNode.severity}">{selectedNode.severity}</span>
            {/if}
            {#if selectedNode.attack_technique}
              <span class="technique-badge">{selectedNode.attack_technique}</span>
            {/if}
          </div>
        {/if}
      </div>

      <!-- Right: Timeline + Evidence (40%) -->
      <div class="right-section">
        <!-- Attack Chain / Timeline -->
        <div class="timeline-section">
          <h3 class="section-title">Attack Timeline ({investigation.timeline?.length ?? 0} events)</h3>
          <div class="timeline-list">
            {#each investigation.timeline ?? [] as entry}
              <div class="timeline-entry severity-{entry.severity}">
                <div class="tl-time">{entry.timestamp?.slice(11, 19) ?? ''}</div>
                <div class="tl-body">
                  <div class="tl-desc">{entry.description ?? entry.event_type ?? ''}</div>
                  <div class="tl-meta">
                    {#if entry.hostname}
                      <span class="tl-host">{entry.hostname}</span>
                    {/if}
                    {#if entry.attack_technique}
                      <span class="technique-badge small">{entry.attack_technique}</span>
                    {/if}
                    {#if entry.severity}
                      <span class="badge badge-{entry.severity}">{entry.severity}</span>
                    {/if}
                  </div>
                </div>
              </div>
            {/each}
            {#if (investigation.timeline ?? []).length === 0}
              <div class="tl-empty">No timeline events available.</div>
            {/if}
          </div>
        </div>

        <!-- Selected node detail -->
        {#if selectedNode}
          <div class="evidence-section">
            <h3 class="section-title">Node Detail</h3>
            <table class="detail-table">
              <tbody>
                {#each Object.entries(selectedNode).filter(([k, v]) => v !== null && v !== undefined && v !== '' && k !== 'id') as [k, v]}
                  <tr><td class="k">{k}</td><td class="v">{v}</td></tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>

    <!-- Top Suspicious Entities — Phase 9 -->
    {#if topEntities.length > 0}
      <div class="mt-4 rounded border border-gray-700 p-3">
        <h3 class="mb-2 text-sm font-semibold text-orange-400">Top Suspicious Entities</h3>
        <ul class="space-y-1">
          {#each topEntities as entity}
            <li class="flex items-center justify-between text-xs">
              <span class="truncate text-gray-200">{entity.rule_name}</span>
              <span class="ml-2 rounded px-1.5 py-0.5 font-mono text-white"
                style="background: {entity.risk_score > 80 ? '#ef4444' : entity.risk_score > 60 ? '#f97316' : entity.risk_score > 30 ? '#eab308' : '#22c55e'}">
                {entity.risk_score}
              </span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    <!-- AI Explanation Panel — Phase 9 -->
    <div class="mt-4 rounded border border-gray-700 p-3">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold text-blue-400">AI Explanation</h3>
        <div class="flex gap-2">
          <button
            class="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:bg-blue-500 disabled:opacity-50"
            disabled={explainLoading}
            onclick={() => { showExplanation = true; loadExplanation(detectionId) }}
          >
            {explainLoading ? 'Generating…' : 'Generate'}
          </button>
          {#if explanation}
            <button
              class="rounded bg-gray-600 px-2 py-1 text-xs text-white hover:bg-gray-500"
              onclick={() => { showExplanation = !showExplanation }}
            >
              {showExplanation ? 'Hide' : 'Show'}
            </button>
          {/if}
        </div>
      </div>

      {#if showExplanation && explanation}
        <div class="mt-2 space-y-2 text-xs text-gray-300">
          <div>
            <p class="font-semibold text-white">What Happened</p>
            <p class="mt-0.5 whitespace-pre-wrap">{explanation.what_happened}</p>
          </div>
          <div>
            <p class="font-semibold text-white">Why It Matters</p>
            <p class="mt-0.5 whitespace-pre-wrap">{explanation.why_it_matters}</p>
          </div>
          <div>
            <p class="font-semibold text-white">Recommended Next Steps</p>
            <p class="mt-0.5 whitespace-pre-wrap">{explanation.recommended_next_steps}</p>
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .investigation-panel { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
  .empty-state { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-muted, #6b7280); }
  .loading, .error { padding: 20px; text-align: center; color: var(--text-muted, #6b7280); }
  .error { color: #ef4444; }

  .summary-bar {
    display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
    padding: 8px 16px; background: var(--bg-secondary, #1e293b); border-bottom: 1px solid var(--border, #334155);
    flex-shrink: 0;
  }
  .summary-text { font-size: 12px; color: var(--text-secondary, #94a3b8); flex: 1; }
  .technique-badges { display: flex; gap: 4px; flex-wrap: wrap; }
  .technique-badge { background: #312e81; color: #a5b4fc; font-size: 10px; padding: 2px 6px; border-radius: 3px; font-family: monospace; }
  .technique-badge.small { font-size: 9px; padding: 1px 4px; }

  .investigation-layout { flex: 1; display: flex; gap: 0; overflow: hidden; }

  .graph-section { flex: 3; display: flex; flex-direction: column; border-right: 1px solid var(--border, #334155); overflow: hidden; }
  .graph-container { flex: 1; background: var(--bg-primary, #0f172a); min-height: 300px; }

  .node-detail {
    padding: 8px 12px; background: var(--bg-secondary, #1e293b); border-top: 1px solid var(--border, #334155);
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 11px;
  }
  .node-type { background: #374151; padding: 2px 6px; border-radius: 3px; color: #9ca3af; text-transform: uppercase; font-size: 9px; }
  .node-label { color: var(--text-primary, #e2e8f0); font-weight: 600; }
  .node-cmd { background: #1e293b; padding: 2px 6px; border-radius: 3px; color: #a3e635; font-size: 10px; max-width: 100%; overflow: hidden; text-overflow: ellipsis; }

  .right-section { flex: 2; display: flex; flex-direction: column; overflow: hidden; }

  .timeline-section { flex: 1; overflow-y: auto; }
  .timeline-list { padding: 4px; }
  .tl-empty { padding: 16px; text-align: center; color: var(--text-muted, #6b7280); font-size: 12px; }
  .timeline-entry {
    display: flex; gap: 8px; padding: 4px 8px; border-left: 2px solid transparent;
    border-bottom: 1px solid var(--border, #334155);
  }
  .timeline-entry.severity-critical { border-left-color: #ef4444; }
  .timeline-entry.severity-high { border-left-color: #f97316; }
  .timeline-entry.severity-medium { border-left-color: #eab308; }
  .timeline-entry.severity-low { border-left-color: #6b7280; }

  .tl-time { font-size: 10px; color: #6b7280; flex-shrink: 0; font-family: monospace; }
  .tl-body { flex: 1; min-width: 0; }
  .tl-desc { font-size: 11px; color: var(--text-primary, #e2e8f0); }
  .tl-meta { display: flex; gap: 4px; align-items: center; margin-top: 2px; flex-wrap: wrap; }
  .tl-host { font-size: 9px; color: #6b7280; }

  .evidence-section { border-top: 1px solid var(--border, #334155); overflow-y: auto; max-height: 200px; }
  .detail-table { width: 100%; font-size: 10px; }
  .detail-table td { padding: 2px 8px; }
  .k { color: #6b7280; width: 120px; }
  .v { color: #e2e8f0; word-break: break-all; }

  .section-title { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: #6b7280; padding: 6px 12px; margin: 0; border-bottom: 1px solid var(--border, #334155); }

  .badge { font-size: 9px; padding: 1px 5px; border-radius: 3px; text-transform: uppercase; }
  .badge-critical { background: #7f1d1d; color: #fca5a5; }
  .badge-high { background: #431407; color: #fdba74; }
  .badge-medium { background: #422006; color: #fde68a; }
  .badge-low { background: #1e293b; color: #94a3b8; }
</style>
