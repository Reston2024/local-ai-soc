<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import cytoscape from 'cytoscape'
  import { getGraph } from '../../lib/api'

  let { onNodeSelect } = $props<{ onNodeSelect?: (n: any) => void }>()

  let container: HTMLDivElement
  let cy: any

  const NODE_COLORS: Record<string, string> = {
    host: '#3b82f6',
    ip: '#10b981',
    alert: '#ef4444',
  }

  async function refresh() {
    const data = await getGraph()
    if (!cy) return
    cy.elements().remove()
    cy.add([
      ...data.nodes.map(n => ({
        data: { id: n.id, label: n.label, type: n.type },
        group: 'nodes' as const,
      })),
      ...data.edges.map(e => ({
        data: { id: e.id, source: e.source, target: e.target, label: e.type },
        group: 'edges' as const,
      })),
    ])
    cy.layout({ name: 'cose', animate: false }).run()
  }

  onMount(() => {
    cy = cytoscape({
      container,
      style: [
        {
          selector: 'node',
          style: {
            // @ts-ignore
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
          selector: ':selected',
          style: { 'border-width': 3, 'border-color': '#f59e0b' },
        },
      ],
      layout: { name: 'grid' },
    })

    cy.on('tap', 'node', (evt: any) => {
      onNodeSelect?.(evt.target.data())
    })

    refresh()
    const interval = setInterval(refresh, 10000)
    return () => clearInterval(interval)
  })

  onDestroy(() => cy?.destroy())
</script>

<div bind:this={container} class="graph-container"></div>

<style>
  .graph-container { width: 100%; height: 100%; background: #0d1117; }
</style>
