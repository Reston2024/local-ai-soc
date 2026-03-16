<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import cytoscape from 'cytoscape'
  import { getGraph } from '../../lib/api.ts'

  // Props
  let { onNodeSelect }: { onNodeSelect?: (data: any) => void } = $props()

  let container: HTMLDivElement
  let cy: cytoscape.Core | null = null
  let loading = $state(true)
  let error = $state<string | null>(null)
  let selectedNode: any = $state(null)

  const NODE_COLORS: Record<string, string> = {
    host: '#58a6ff',
    ip: '#ffa657',
    alert: '#ef4444',
    domain: '#8b5cf6',
    process: '#f59e0b',
    user: '#06b6d4',
    artifact: '#6e7681',
  }

  function buildStyles() {
    return [
      {
        selector: 'node',
        style: {
          'background-color': (ele: any) => NODE_COLORS[ele.data('type')] ?? '#8b949e',
          'label': 'data(label)',
          'color': '#e6edf3',
          'font-size': '10px',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': '4px',
          'border-width': 1,
          'border-color': '#30363d',
          'width': 28,
          'height': 28,
        }
      },
      {
        selector: 'node:selected',
        style: { 'border-width': 3, 'border-color': '#58a6ff' }
      },
      {
        selector: 'edge',
        style: {
          'width': 1.5,
          'line-color': '#30363d',
          'target-arrow-color': '#30363d',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '9px',
          'color': '#6e7681',
          'text-rotation': 'autorotate',
        }
      },
      {
        selector: 'edge:selected',
        style: { 'line-color': '#58a6ff', 'target-arrow-color': '#58a6ff' }
      },
      {
        selector: '.attack-path-highlight',
        style: { 'border-width': 2, 'border-color': '#f59e0b', 'border-opacity': 0.8 }
      },
    ]
  }

  async function loadAndRender() {
    loading = true
    error = null
    try {
      const data = await getGraph()
      if (!cy) {
        cy = cytoscape({
          container,
          style: buildStyles() as any,
          layout: { name: 'cose', padding: 40, animate: false } as any,
        })
        cy.on('tap', 'node', (evt: any) => {
          selectedNode = evt.target.data()
          onNodeSelect?.(evt.target.data())
        })
        cy.on('tap', (evt: any) => {
          if (evt.target === cy) selectedNode = null
        })
      }

      cy.elements().remove()

      const nodes = (data.nodes ?? []).map((n: any) => ({
        data: {
          id: n.id,
          label: n.label,
          type: n.type,
          evidence: n.evidence ?? [],
          first_seen: n.first_seen ?? '',
          attributes: n.attributes ?? {},
        }
      }))

      const edges = (data.edges ?? []).map((e: any) => ({
        data: {
          id: e.id,
          source: e.src,
          target: e.dst,
          label: e.type,
          evidence_event_ids: e.evidence_event_ids ?? [],
        }
      }))

      cy.add([...nodes, ...edges])
      cy.layout({ name: 'cose', padding: 40, animate: false } as any).run()

      // Attack path highlighting
      if (data.attack_paths && data.attack_paths.length > 0) {
        data.attack_paths.forEach((path: any, idx: number) => {
          path.node_ids.forEach((nid: string) => {
            cy!.getElementById(nid).addClass(`attack-path-highlight path-${idx}`)
          })
        })
      }
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  onMount(() => { loadAndRender() })
  onDestroy(() => { cy?.destroy() })
</script>

<div class="graph-container">
  <div class="cy-wrap" bind:this={container}>
    {#if loading}<div class="overlay">Loading graph…</div>{/if}
    {#if !loading && !error && cy && cy.elements().length === 0}
      <div class="overlay">No graph data yet. Ingest events to populate.</div>
    {/if}
    {#if error}
      <div class="overlay error">Error: {error}</div>
    {/if}
  </div>

  {#if selectedNode}
    <div class="node-detail">
      <h4>{selectedNode.label} <span class="badge">{selectedNode.type}</span></h4>
      {#if selectedNode.evidence?.length}
        <p class="label">Evidence events</p>
        <ul>{#each selectedNode.evidence as eid}<li>{eid}</li>{/each}</ul>
      {/if}
      {#if selectedNode.attributes && Object.keys(selectedNode.attributes).length}
        <p class="label">Attributes</p>
        <pre>{JSON.stringify(selectedNode.attributes, null, 2)}</pre>
      {/if}
      <button onclick={() => selectedNode = null}>Close</button>
    </div>
  {/if}
</div>

<style>
  .graph-container {
    position: relative;
    display: flex;
    width: 100%;
    height: 100%;
  }

  .cy-wrap {
    flex: 1;
    background: var(--bg-primary, #0d1117);
    position: relative;
    min-height: 400px;
  }

  .overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary, #8b949e);
    font-size: 14px;
    background: var(--bg-primary, #0d1117);
  }

  .overlay.error {
    color: #ef4444;
  }

  .node-detail {
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    width: 260px;
    background: var(--bg-secondary, #161b22);
    border-left: 1px solid var(--border, #30363d);
    overflow-y: auto;
    padding: 16px;
    font-size: 13px;
    z-index: 10;
  }

  .node-detail h4 {
    font-size: 14px;
    font-weight: 600;
    margin: 0 0 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .badge {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    background: var(--border, #30363d);
    color: var(--text-secondary, #8b949e);
    padding: 2px 6px;
    border-radius: 4px;
  }

  .label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--text-muted, #6e7681);
    margin: 10px 0 4px;
  }

  ul {
    margin: 0;
    padding: 0 0 0 16px;
    color: var(--text-secondary, #8b949e);
    font-size: 12px;
  }

  pre {
    font-size: 11px;
    background: var(--bg-primary, #0d1117);
    padding: 8px;
    border-radius: 4px;
    overflow-x: auto;
    color: var(--text-secondary, #8b949e);
  }

  button {
    margin-top: 12px;
    padding: 6px 12px;
    background: var(--border, #30363d);
    border: none;
    border-radius: 4px;
    color: var(--text-secondary, #8b949e);
    cursor: pointer;
    font-size: 12px;
  }

  button:hover {
    background: var(--bg-tertiary, #21262d);
    color: var(--text-primary, #e6edf3);
  }
</style>
