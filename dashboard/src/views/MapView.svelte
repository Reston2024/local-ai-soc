<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import { api } from '../lib/api.ts'
  import type { OsintResult } from '../lib/api.ts'
  // Leaflet imported dynamically in onMount to avoid SSR issues

  let mapContainer: HTMLDivElement
  // Module-level typed variables — set in onMount after dynamic import
  let L: typeof import('leaflet') | null = null
  let map: import('leaflet').Map | null = null
  let markerLayer: import('leaflet').LayerGroup | null = null

  let selectedIp = $state<string | null>(null)
  let osintData = $state<OsintResult | null>(null)
  let osintLoading = $state(false)
  let markerCount = $state(0)
  let lastRefresh = $state<string>('')
  let refreshInterval: ReturnType<typeof setInterval> | null = null
</script>

<div class="map-view">
  <div class="map-header">
    <h1>Threat Map</h1>
    <span class="map-meta">{markerCount} IPs plotted · refreshes every 60s</span>
  </div>
  <div class="map-body">
    <div class="map-container" bind:this={mapContainer}></div>
    {#if selectedIp}
      <div class="osint-side-panel">
        <div class="panel-header">
          <span class="panel-ip">{selectedIp}</span>
          <button class="panel-close" onclick={() => { selectedIp = null; osintData = null }}>✕</button>
        </div>
        {#if osintLoading}
          <div class="panel-loading">Loading OSINT…</div>
        {:else if osintData}
          <!-- OSINT data rendered in Task 1 -->
        {:else}
          <div class="panel-empty">No enrichment data</div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .map-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
  .map-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; border-bottom: 1px solid var(--border); background: var(--bg-secondary); flex-shrink: 0; }
  .map-header h1 { font-size: 15px; font-weight: 600; }
  .map-meta { font-size: 11px; color: var(--text-muted); }
  .map-body { display: flex; flex: 1; overflow: hidden; }
  .map-container { flex: 1; }
  .osint-side-panel { width: 300px; border-left: 1px solid var(--border); background: var(--bg-secondary); overflow-y: auto; flex-shrink: 0; }
  .panel-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; border-bottom: 1px solid var(--border); }
  .panel-ip { font-family: monospace; font-size: 13px; font-weight: 600; }
  .panel-close { background: none; border: none; cursor: pointer; color: var(--text-muted); font-size: 14px; }
  .panel-loading, .panel-empty { padding: 20px 14px; font-size: 12px; color: var(--text-muted); }
</style>
