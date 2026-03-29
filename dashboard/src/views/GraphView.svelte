<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import cytoscape from 'cytoscape'
  import fcose from 'cytoscape-fcose'
  import dagre from 'cytoscape-dagre'
  import { api, type GraphEntity } from '../lib/api.ts'

  cytoscape.use(fcose)
  cytoscape.use(dagre)

  let {
    focusEntityId = $bindable(''),
    onNavigateInvestigation = undefined,
  }: {
    focusEntityId?: string
    onNavigateInvestigation?: (investigationId: string) => void
  } = $props()

  let container: HTMLDivElement
  let cy: cytoscape.Core | null = null
  let entities = $state<GraphEntity[]>([])
  let selectedEntity = $state<GraphEntity | null>(null)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let typeFilter = $state('')
  let depth = $state(1)

  // Attack path state
  let pathSource = $state<string | null>(null)
  let pathTarget = $state<string | null>(null)
  let attackPathActive = $state(false)
  let showPathOnly = $state(false)

  // Focus effect: load subgraph when focusEntityId prop changes and cy is ready
  $effect(() => {
    if (focusEntityId && cy) {
      loadSubgraph(focusEntityId)
    }
  })

  const entityTypes = ['host', 'user', 'process', 'file', 'ip', 'domain', 'network_connection', 'detection']

  const typeColors: Record<string, string> = {
    host: '#58a6ff',
    user: '#3fb950',
    process: '#d29922',
    file: '#8b949e',
    ip: '#ffa657',
    domain: '#bc8cff',
    network_connection: '#f85149',
    detection: '#f85149',
    artifact: '#6e7681',
    incident: '#e3b341',
    attack_technique: '#ff6b6b',
  }

  function buildCytoStyle() {
    return [
      {
        selector: 'node',
        style: {
          'background-color': (ele: any) => typeColors[ele.data('type')] ?? '#8b949e',
          'label': 'data(label)',
          'color': '#e6edf3',
          'font-size': '10px',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': '4px',
          'border-width': 1,
          'border-color': '#30363d',
          'width': (ele: any) => {
            const score = Number(ele.data('risk_score') ?? 0)
            return Math.max(20, Math.min(50, 20 + score * 0.3))
          },
          'height': (ele: any) => {
            const score = Number(ele.data('risk_score') ?? 0)
            return Math.max(20, Math.min(50, 20 + score * 0.3))
          },
        }
      },
      {
        selector: 'node:selected',
        style: {
          'border-width': 3,
          'border-color': '#58a6ff',
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 1.5,
          'line-color': '#30363d',
          'target-arrow-color': '#30363d',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(edge_type)',
          'font-size': '9px',
          'color': '#6e7681',
          'text-rotation': 'autorotate',
        }
      },
      {
        selector: 'edge:selected',
        style: {
          'line-color': '#58a6ff',
          'target-arrow-color': '#58a6ff',
        }
      },
      {
        selector: 'node.attack-path-node',
        style: {
          'border-width': 3,
          'border-color': '#f85149',
          'background-color': 'rgba(248, 81, 73, 0.25)',
        }
      },
      {
        selector: 'edge.attack-path-edge',
        style: {
          'width': 4,
          'line-color': '#f85149',
          'target-arrow-color': '#f85149',
        }
      },
      {
        selector: 'node.attack-technique',
        style: {
          'border-width': 2,
          'border-color': '#ff6b6b',
        }
      },
    ]
  }

  // Normalize entity fields: backend may return entity_id/entity_name/entity_type
  function normalizeEntity(e: GraphEntity): GraphEntity {
    return {
      id: e.id ?? e.entity_id ?? '',
      entity_id: e.entity_id ?? e.id ?? '',
      type: e.type ?? e.entity_type ?? '',
      entity_type: e.entity_type ?? e.type ?? '',
      label: e.label ?? e.entity_name ?? e.id ?? e.entity_id ?? '',
      entity_name: e.entity_name ?? e.label ?? '',
      properties: e.properties ?? e.attributes ?? {},
      attributes: e.attributes ?? e.properties ?? {},
      first_seen: e.first_seen ?? '',
      last_seen: e.last_seen ?? '',
    }
  }

  function highlightAttackPath(sourceId: string, targetId: string) {
    cy!.elements().removeClass('attack-path-node attack-path-edge')
    const dijkstraResult = cy!.elements().dijkstra({
      root: cy!.$(`#${sourceId}`),
      directed: false,
    })
    const pathCollection = dijkstraResult.pathTo(cy!.$(`#${targetId}`))
    if (pathCollection.length > 0) {
      pathCollection.nodes().addClass('attack-path-node')
      pathCollection.edges().addClass('attack-path-edge')
      attackPathActive = true
      if (showPathOnly) {
        cy!.elements().not(pathCollection).hide()
      }
      pathCollection.nodes().animate(
        { style: { 'border-width': 4, 'border-color': '#f85149' } },
        { duration: 600 }
      )
    }
  }

  function clearAttackPath() {
    cy!.elements().removeClass('attack-path-node attack-path-edge')
    cy!.elements().show()
    pathSource = null
    pathTarget = null
    attackPathActive = false
    showPathOnly = false
  }

  async function loadEntities() {
    loading = true
    error = null
    try {
      const res = await api.graph.entities({ type: typeFilter || undefined, limit: 100 })
      entities = (res.entities ?? []).map(normalizeEntity)
      if (entities.length > 0) {
        await loadSubgraph(entities[0].id ?? entities[0].entity_id ?? '')
      } else {
        renderEmpty()
        loading = false
      }
    } catch (e) {
      error = String(e)
      loading = false
    }
  }

  async function loadSubgraph(entityId: string) {
    loading = true
    error = null
    try {
      const graph = await api.graph.entity(entityId, depth)
      // Normalize entities in the subgraph response
      if (graph.entities) {
        graph.entities = graph.entities.map(normalizeEntity)
      }
      renderGraph(graph)
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  function renderEmpty() {
    if (!cy) initCy()
    cy?.elements().remove()
  }

  function initCy() {
    cy = cytoscape({
      container,
      style: buildCytoStyle() as any,
      layout: { name: 'fcose', quality: 'default', animate: false, randomize: true,
        nodeRepulsion: 4500, idealEdgeLength: 80, edgeElasticity: 0.45,
        padding: 40, nodeSeparation: 75 } as any,
    })
    cy.on('tap', 'node', (evt) => {
      const data = evt.target.data()
      // Update selectedEntity (existing behaviour)
      selectedEntity = entities.find(e => (e.id ?? e.entity_id) === data.id) ?? {
        id: data.id, entity_id: data.id, type: data.type, entity_type: data.type,
        label: data.label, entity_name: data.label,
        properties: {}, attributes: {}, first_seen: '', last_seen: ''
      }
      // Two-click attack path: first click sets source, second sets target and triggers highlight
      if (!pathSource) {
        pathSource = data.id
      } else if (pathSource !== data.id) {
        pathTarget = data.id
        highlightAttackPath(pathSource, data.id)
      }
    })
    cy.on('tap', (evt) => {
      if (evt.target === cy) selectedEntity = null
    })
  }

  function renderGraph(graph: { entities: GraphEntity[]; edges: any[] }) {
    if (!cy) initCy()
    cy!.elements().remove()

    const nodes = graph.entities.map(e => ({
      data: {
        id: e.id ?? e.entity_id,
        label: (e.label ?? e.entity_name ?? '').slice(0, 24),
        type: e.type ?? e.entity_type,
        risk_score: (e.attributes ?? e.properties ?? {} as any)?.risk_score ?? 0,
        ...(e.properties ?? e.attributes ?? {})
      },
      classes: (e.type ?? e.entity_type) === 'attack_technique' ? 'attack-technique' : undefined
    }))

    const edges = graph.edges.map(e => ({
      data: {
        id: e.id,
        source: e.source_id,
        target: e.target_id,
        edge_type: e.edge_type,
      }
    }))

    cy!.add([...nodes, ...edges])
    cy!.layout({ name: 'fcose', quality: 'default', animate: false, randomize: true,
      nodeRepulsion: 4500, idealEdgeLength: 80, edgeElasticity: 0.45,
      padding: 40, nodeSeparation: 75 } as any).run()
  }

  onMount(() => {
    initCy()
    loadEntities()
  })

  onDestroy(() => { cy?.destroy() })
</script>

<div class="view">
  <div class="view-header">
    <h1>Graph</h1>
    <div class="controls">
      <select bind:value={typeFilter} onchange={loadEntities}>
        <option value="">All entity types</option>
        {#each entityTypes as t}
          <option value={t}>{t}</option>
        {/each}
      </select>
      <label>
        Depth
        <select bind:value={depth} onchange={() => selectedEntity && loadSubgraph(selectedEntity.id)}>
          <option value={1}>1-hop</option>
          <option value={2}>2-hop</option>
          <option value={3}>3-hop</option>
        </select>
      </label>
      <button class="btn" onclick={loadEntities}>&#8635; Reload</button>
      {#if attackPathActive}
        <button class="btn btn-danger" onclick={clearAttackPath}>Clear Path</button>
        <label class="toggle">
          <input type="checkbox" bind:checked={showPathOnly}
            onchange={() => showPathOnly ? cy?.elements().not('.attack-path-node, .attack-path-edge').hide() : cy?.elements().show()} />
          Path only
        </label>
      {/if}
      {#if pathSource && !attackPathActive}
        <span class="path-hint">Click target node to highlight path from {pathSource.slice(0,12)}…</span>
      {/if}
    </div>
  </div>

  {#if error}
    <div class="error-banner">&#9888; {error}</div>
  {/if}

  <div class="graph-body">
    <div class="cy-container" bind:this={container}>
      {#if loading}<div class="overlay">Loading graph…</div>{/if}
      {#if !loading && entities.length === 0}
        <div class="overlay">No entities yet. Ingest events to populate the graph.</div>
      {/if}
    </div>

    {#if selectedEntity}
      <div class="entity-panel">
        <div class="panel-header">
          <span class="entity-type" style="color: {typeColors[selectedEntity.type ?? selectedEntity.entity_type ?? ''] ?? '#8b949e'}">{selectedEntity.type ?? selectedEntity.entity_type}</span>
          <button class="btn-close" onclick={() => selectedEntity = null}>&#10005;</button>
        </div>
        <div class="panel-label">{selectedEntity.label ?? selectedEntity.entity_name}</div>
        {#if (selectedEntity.type ?? selectedEntity.entity_type) === 'attack_technique' && (selectedEntity.properties ?? selectedEntity.attributes ?? {} as any)?.tactic}
          <div class="tactic-badge">
            MITRE: {(selectedEntity.properties ?? selectedEntity.attributes ?? {} as any)?.tactic}
          </div>
        {/if}
        <div class="panel-section">
          <div class="panel-row"><span>First seen</span><span>{selectedEntity.first_seen ? new Date(selectedEntity.first_seen).toLocaleString() : '—'}</span></div>
          <div class="panel-row"><span>Last seen</span><span>{selectedEntity.last_seen ? new Date(selectedEntity.last_seen).toLocaleString() : '—'}</span></div>
        </div>
        {#if Object.keys(selectedEntity.properties ?? selectedEntity.attributes ?? {}).length > 0}
          <div class="panel-section">
            <div class="panel-sub">Properties</div>
            {#each Object.entries(selectedEntity.properties ?? selectedEntity.attributes ?? {}) as [k, v]}
              <div class="panel-row">
                <span class="prop-key">{k}</span>
                <span class="prop-val mono">{String(v).slice(0, 60)}</span>
              </div>
            {/each}
          </div>
        {/if}
        <button class="btn btn-primary full" onclick={() => selectedEntity && loadSubgraph(selectedEntity.id ?? selectedEntity.entity_id ?? '')}>
          Expand {depth}-hop subgraph
        </button>
        {#if onNavigateInvestigation && (selectedEntity?.attributes?.case_id ?? selectedEntity?.properties?.case_id)}
          <button class="btn btn-primary full" onclick={() => {
            const caseId = selectedEntity?.attributes?.case_id ?? selectedEntity?.properties?.case_id
            if (caseId && onNavigateInvestigation) onNavigateInvestigation(String(caseId))
          }}>
            Investigate case
          </button>
        {/if}
      </div>
    {/if}
  </div>

  <!-- Legend -->
  <div class="legend">
    {#each Object.entries(typeColors).slice(0, 8) as [type, color]}
      <span class="legend-item">
        <span class="legend-dot" style="background: {color}"></span>
        {type}
      </span>
    {/each}
  </div>
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
  .view-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 20px; border-bottom: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0;
  }
  h1 { font-size: 16px; font-weight: 600; }
  .controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .controls label { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-secondary); }

  .graph-body { flex: 1; display: flex; overflow: hidden; position: relative; }

  .cy-container {
    flex: 1;
    background: var(--bg-primary);
    position: relative;
  }

  .overlay {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    color: var(--text-secondary); font-size: 14px;
    background: var(--bg-primary);
  }

  .entity-panel {
    width: 260px;
    flex-shrink: 0;
    background: var(--bg-secondary);
    border-left: 1px solid var(--border);
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .panel-header { display: flex; justify-content: space-between; align-items: center; }
  .entity-type { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
  .btn-close { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 14px; }
  .panel-label { font-size: 14px; font-weight: 600; word-break: break-all; }

  .tactic-badge {
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    background: rgba(255, 107, 107, 0.15); color: #ff6b6b;
    border: 1px solid rgba(255, 107, 107, 0.35); border-radius: 4px;
    padding: 3px 8px; letter-spacing: 0.4px;
  }

  .panel-section { border-top: 1px solid var(--border); padding-top: 10px; }
  .panel-sub { font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; letter-spacing: 0.5px; }
  .panel-row { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 6px; font-size: 12px; }
  .panel-row span:first-child { color: var(--text-secondary); flex-shrink: 0; }
  .prop-key { color: var(--text-secondary); }
  .prop-val { color: var(--text-primary); word-break: break-all; text-align: right; }

  .full { width: 100%; justify-content: center; }

  .legend {
    display: flex; gap: 12px; padding: 8px 20px; flex-wrap: wrap;
    border-top: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0;
  }
  .legend-item { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--text-secondary); }
  .legend-dot { width: 8px; height: 8px; border-radius: 50%; }

  .error-banner { padding: 12px 20px; background: rgba(248,81,73,0.1); color: var(--severity-critical); border-bottom: 1px solid rgba(248,81,73,0.3); font-size: 13px; }

  .btn-danger { background: rgba(248,81,73,0.15); color: #f85149; border: 1px solid rgba(248,81,73,0.3); }
  .path-hint { font-size: 12px; color: var(--text-secondary); font-style: italic; }
  .toggle { display: flex; align-items: center; gap: 4px; cursor: pointer; font-size: 12px; }
</style>
