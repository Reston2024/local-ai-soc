<script lang="ts">
  /**
   * ArcGauge — RPM-style tachometer gauge rendered in pure SVG.
   *
   * The gauge sweeps 270° (from 7 o'clock → clockwise → 5 o'clock).
   * Tick marks ring the arc; each tick is lit green → amber → red based
   * on its position relative to the current value.  The numeric value
   * is shown as a large digital readout in the centre.
   */

  let {
    value = 0,        // 0–100
    label = '',       // e.g. "CPU", "RAM", "DISK"
    detail = '',      // e.g. "9.8 / 16.0 GB"
    size = 180,       // SVG canvas size in px
    nullLabel = 'N/A' // shown when value is null / undefined
  }: {
    value: number | null
    label: string
    detail?: string | null
    size?: number
    nullLabel?: string
  } = $props()

  // ── Geometry ─────────────────────────────────────────────────────────────
  const CX = size / 2
  const CY = size / 2
  const R  = size * 0.38          // arc radius
  const TICK_COUNT  = 40          // number of segments around the arc
  const TICK_OUTER  = R + size * 0.065
  const TICK_INNER  = R - size * 0.01
  const TICK_W      = size * 0.022

  // Arc starts at 135° (bottom-left) and sweeps 270° clockwise to 45° (bottom-right)
  const START_DEG = 135
  const SWEEP_DEG = 270

  function degToRad(deg: number) { return (deg * Math.PI) / 180 }

  // ── Tick geometry ─────────────────────────────────────────────────────────
  type Tick = { x1: number; y1: number; x2: number; y2: number; lit: boolean; color: string }

  const ticks = $derived.by((): Tick[] => {
    const v = value ?? 0
    return Array.from({ length: TICK_COUNT }, (_, i) => {
      const frac  = i / (TICK_COUNT - 1)                // 0 → 1
      const angle = degToRad(START_DEG + frac * SWEEP_DEG)
      const cos   = Math.cos(angle)
      const sin   = Math.sin(angle)

      const lit = frac * 100 <= v

      // Colour zones: 0–60 cyan, 60–80 amber, 80–100 red
      let color: string
      if (frac * 100 <= 60)       color = lit ? '#00d4ff' : 'rgba(0,212,255,0.12)'
      else if (frac * 100 <= 80)  color = lit ? '#f59e0b' : 'rgba(245,158,11,0.12)'
      else                        color = lit ? '#ef4444' : 'rgba(239,68,68,0.12)'

      return {
        x1: CX + TICK_INNER * cos,
        y1: CY + TICK_INNER * sin,
        x2: CX + TICK_OUTER * cos,
        y2: CY + TICK_OUTER * sin,
        lit,
        color,
      }
    })
  })

  // ── Value colour for the centre readout ───────────────────────────────────
  const valueColor = $derived.by(() => {
    if (value === null || value === undefined) return 'rgba(255,255,255,0.3)'
    if (value >= 80) return '#ef4444'
    if (value >= 60) return '#f59e0b'
    return '#00d4ff'
  })

  const displayValue = $derived(
    value === null || value === undefined ? nullLabel : `${Math.round(value)}%`
  )
</script>

<div class="gauge-wrap" style="width:{size}px">
  <svg
    width={size}
    height={size}
    viewBox="0 0 {size} {size}"
    xmlns="http://www.w3.org/2000/svg"
    aria-label="{label} {displayValue}"
  >
    <!-- Outer bezel ring -->
    <circle
      cx={CX} cy={CY} r={size * 0.48}
      fill="rgba(255,255,255,0.03)"
      stroke="rgba(255,255,255,0.08)"
      stroke-width="1"
    />

    <!-- Tick marks -->
    {#each ticks as t}
      <line
        x1={t.x1} y1={t.y1}
        x2={t.x2} y2={t.y2}
        stroke={t.color}
        stroke-width={TICK_W}
        stroke-linecap="round"
      />
    {/each}

    <!-- Inner dial face -->
    <circle
      cx={CX} cy={CY} r={R * 0.78}
      fill="rgba(0,0,0,0.55)"
      stroke="rgba(255,255,255,0.06)"
      stroke-width="1"
    />

    <!-- Numeric value -->
    <text
      x={CX} y={CY + size * 0.04}
      text-anchor="middle"
      dominant-baseline="middle"
      font-family="'Courier New', monospace"
      font-size={size * 0.18}
      font-weight="700"
      fill={valueColor}
      letter-spacing="1"
    >{displayValue}</text>

    <!-- Label below value -->
    <text
      x={CX} y={CY + size * 0.21}
      text-anchor="middle"
      dominant-baseline="middle"
      font-family="inherit"
      font-size={size * 0.085}
      font-weight="600"
      fill="rgba(255,255,255,0.45)"
      letter-spacing="2"
    >{label.toUpperCase()}</text>
  </svg>

  {#if detail}
    <p class="gauge-detail">{detail}</p>
  {/if}
</div>

<style>
  .gauge-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }

  .gauge-detail {
    font-size: 11px;
    color: rgba(255,255,255,0.35);
    margin: 0;
    text-align: center;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.3px;
  }
</style>
