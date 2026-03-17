<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import cytoscape from 'cytoscape'
  import dagre from 'cytoscape-dagre'
  import { getAttackGraph, type CausalityGraphResponse } from '../../lib/api'

  // Register dagre plugin ONCE at module level (safe to call multiple times)
  cytoscape.use(dagre)

  let { alertId, onNodeSelect } = $props<{
    alertId: string
    onNodeSelect?: (node: Record<string, unknown>) => void
  }>()

  let container: HTMLDivElement
  let cy: ReturnType<typeof cytoscape> | null = null
  let loading = $state(false)
  let error = $state<string | null>(null)

  const NODE_COLORS: Record<string, string> = {
    host: '#3b82f6',    // blue
    ip: '#10b981',      // green
    alert: '#ef4444',   // red
    user: '#8b5cf6',    // purple
    domain: '#f59e0b',  // amber
    process: '#06b6d4', // cyan
    file: '#6b7280',    // grey
  }

  function highlightAttackPaths(data: CausalityGraphResponse) {
    if (!cy) return
    // Reset all highlighting first
    cy.elements().removeData('attackPath')
    // Mark attack path elements
    for (const path of data.attack_paths) {
      for (const nodeId of path.node_ids) {
        cy.getElementById(nodeId).data('attackPath', true)
      }
      for (const edgeId of path.edge_ids) {
        cy.getElementById(edgeId).data('attackPath', true)
      }
    }
  }

  async function loadGraph(id: string, from?: string, to?: string) {
    if (!id || !cy) return
    loading = true
    error = null
    try {
      const data = await getAttackGraph(id, { from, to })
      if (!cy) return
      cy.elements().remove()
      cy.add([
        ...data.nodes.map(n => ({
          data: { id: n.id, label: n.label, type: n.type },
          group: 'nodes' as const,
        })),
        ...data.edges.map(e => ({
          // IMPORTANT: map e.src -> source, e.dst -> target (GraphEdge schema uses src/dst)
          data: { id: e.id, source: e.src, target: e.dst, label: e.type },
          group: 'edges' as const,
        })),
      ])
      cy.layout({ name: 'dagre', rankDir: 'TB', nodeSep: 50, rankSep: 80 } as any).run()
      highlightAttackPaths(data)
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load attack graph'
    } finally {
      loading = false
    }
  }

  $effect(() => {
    if (alertId) {
      loadGraph(alertId)
    }
  })

  onMount(() => {
    cy = cytoscape({
      container,
      style: [
        {
          selector: 'node',
          style: {
            // @ts-ignore — function style is valid in Cytoscape but not in TS types
            'background-color': (ele: any) => NODE_COLORS[ele.data('type')] ?? '#6b7280',
            'label': 'data(label)',
            'color': '#e5e7eb',
            'font-size': '10px',
            'text-valign': 'bottom',
            'text-margin-y': 4,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': '#374151',
            'target-arrow-color': '#374151',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '9px',
            'color': '#6b7280',
          },
        },
        {
          // Attack path edges — orange highlight
          selector: 'edge[attackPath]',
          style: {
            'line-color': '#f97316',
            'target-arrow-color': '#f97316',
            'width': 3,
            'line-style': 'solid',
            'z-index': 10,
          },
        },
        {
          // Attack path nodes — orange border
          selector: 'node[attackPath]',
          style: {
            'border-width': 3,
            'border-color': '#f97316',
            'border-style': 'solid',
          },
        },
        {
          selector: ':selected',
          style: { 'border-width': 3, 'border-color': '#f59e0b' },
        },
      ],
      layout: { name: 'grid' },
    })

    cy.on('tap', 'node', (evt: any) => {
      onNodeSelect?.(evt.target.data())
    })

    if (alertId) loadGraph(alertId)
  })

  onDestroy(() => cy?.destroy())
</script>

{#if loading}
  <div class="overlay">Loading attack graph...</div>
{/if}
{#if error}
  <div class="overlay error">{error}</div>
{/if}
<div bind:this={container} class="graph-container"></div>

<style>
  .graph-container { width: 100%; height: 100%; background: #0d1117; position: relative; }
  .overlay {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: #9ca3af;
    font-size: 14px;
    z-index: 20;
    pointer-events: none;
  }
  .overlay.error { color: #ef4444; }
</style>
