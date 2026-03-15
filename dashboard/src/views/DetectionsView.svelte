<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type Detection } from '../lib/api.ts'

  let detections = $state<Detection[]>([])
  let total = $state(0)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let severityFilter = $state('')

  async function load() {
    loading = true
    error = null
    try {
      const res = await api.detections.list({ limit: 100, severity: severityFilter || undefined })
      detections = res.detections
      total = res.total
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  onMount(load)

  function severityClass(s: string) {
    return `badge badge-${s.toLowerCase()}`
  }

  function fmtTime(ts: string) {
    return new Date(ts).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }
</script>

<div class="view">
  <div class="view-header">
    <div class="view-title">
      <h1>Detections <span class="count">{total}</span></h1>
    </div>
    <div class="view-actions">
      <select bind:value={severityFilter} onchange={load}>
        <option value="">All severities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>
      <button class="btn" onclick={load}>↻ Refresh</button>
    </div>
  </div>

  {#if error}
    <div class="error-banner">⚠ {error}</div>
  {/if}

  {#if loading}
    <div class="loading">Loading detections...</div>
  {:else if detections.length === 0}
    <div class="empty">No detections found. Ingest events and run detection rules.</div>
  {:else}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Rule</th>
            <th>Severity</th>
            <th>Event ID</th>
          </tr>
        </thead>
        <tbody>
          {#each detections as d}
            <tr>
              <td class="mono ts">{fmtTime(d.fired_at)}</td>
              <td class="rule-name">{d.rule_name}</td>
              <td><span class={severityClass(d.severity)}>{d.severity}</span></td>
              <td class="mono eid" title={d.event_id}>{d.event_id.slice(0, 8)}…</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

  .view-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
    flex-shrink: 0;
  }

  .view-title h1 { font-size: 16px; font-weight: 600; }
  .count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 18px;
    padding: 0 6px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
    margin-left: 8px;
    color: var(--text-secondary);
  }

  .view-actions { display: flex; gap: 8px; align-items: center; }

  .table-wrap { flex: 1; overflow-y: auto; }

  .ts { color: var(--text-secondary); font-size: 12px; white-space: nowrap; }
  .rule-name { font-weight: 500; }
  .eid { color: var(--text-muted); }

  .loading, .empty { padding: 40px; text-align: center; color: var(--text-secondary); }
  .error-banner { padding: 12px 20px; background: rgba(248,81,73,0.1); color: var(--severity-critical); border-bottom: 1px solid rgba(248,81,73,0.3); font-size: 13px; }
</style>
