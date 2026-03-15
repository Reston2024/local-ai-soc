<script lang="ts">
  import { onMount } from 'svelte'
  import * as d3 from 'd3'
  import { getTimeline } from '../../lib/api'

  let svg: SVGSVGElement
  let events: any[] = []

  const SEVERITY_COLOR: Record<string, string> = {
    critical: '#ef4444',
    high: '#f59e0b',
    medium: '#3b82f6',
    low: '#10b981',
    info: '#6b7280',
  }

  async function render() {
    events = await getTimeline()
    if (!events.length || !svg) return

    const width = svg.clientWidth || 800
    const height = 120
    const margin = { top: 20, right: 20, bottom: 30, left: 40 }

    const sel = d3.select(svg)
    sel.selectAll('*').remove()

    const times = events.map(e => new Date(e.timestamp)).filter(d => !isNaN(d.getTime()))
    if (!times.length) return

    const x = d3.scaleTime()
      .domain(d3.extent(times) as [Date, Date])
      .range([margin.left, width - margin.right])

    const g = sel.append('g')

    g.append('g')
      .attr('transform', `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x).ticks(6).tickFormat(d3.timeFormat('%H:%M') as any))
      .attr('color', '#6b7280')

    g.selectAll('circle')
      .data(events.filter(e => !isNaN(new Date(e.timestamp).getTime())))
      .join('circle')
      .attr('cx', d => x(new Date(d.timestamp)))
      .attr('cy', height / 2 - 15)
      .attr('r', 5)
      .attr('fill', d => SEVERITY_COLOR[d.severity] ?? '#6b7280')
      .attr('stroke', '#1f2937')
      .attr('stroke-width', 1.5)

    g.append('line')
      .attr('x1', margin.left)
      .attr('x2', width - margin.right)
      .attr('y1', height / 2 - 15)
      .attr('y2', height / 2 - 15)
      .attr('stroke', '#1f2937')
      .attr('stroke-width', 1)
  }

  onMount(() => {
    render()
    const interval = setInterval(render, 10000)
    return () => clearInterval(interval)
  })
</script>

<div class="timeline-wrap">
  <span class="label">Event Timeline</span>
  <svg bind:this={svg} class="timeline-svg"></svg>
</div>

<style>
  .timeline-wrap { height: 100%; display: flex; flex-direction: column; padding: 8px 12px; background: #0d1117; }
  .label { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
  .timeline-svg { flex: 1; width: 100%; }
</style>
