<script lang="ts">
  import { onMount } from 'svelte'
  import { api, type Detection } from '../lib/api.ts'

  let { onInvestigate }: { onInvestigate?: (id: string) => void } = $props()

  let detections = $state<Detection[]>([])
  let total = $state(0)
  let loading = $state(true)
  let runningDetection = $state(false)
  let error = $state<string | null>(null)
  let severityFilter = $state('')

  async function load() {
    loading = true
    error = null
    try {
      const res = await api.detections.list({ limit: 100, severity: severityFilter || undefined })
      detections = res.detections ?? []
      total = res.total
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
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

  onMount(load)

  function severityClass(s: string) {
    return `badge badge-${s.toLowerCase()}`
  }

  function fmtTime(ts: string | undefined) {
    if (!ts) return '—'
    return new Date(ts).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  function getDetectionId(d: Detection): string {
    return d.detection_id ?? d.id ?? ''
  }

  function getEventCount(d: Detection): number {
    if (d.matched_event_ids) return d.matched_event_ids.length
    if (d.event_id) return 1
    return 0
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
      <button class="btn" onclick={load} disabled={loading}>↻ Refresh</button>
      <button class="btn btn-primary" onclick={runDetection} disabled={runningDetection}>
        {runningDetection ? 'Running…' : '⚡ Run Detection'}
      </button>
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
            <th>Technique</th>
            <th>Events</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each detections as d}
            <tr>
              <td class="mono ts">{fmtTime(d.fired_at)}</td>
              <td class="rule-name">
                {d.rule_name}
                {#if d.explanation}
                  <span class="explanation" title={d.explanation}>ℹ</span>
                {/if}
              </td>
              <td><span class={severityClass(d.severity)}>{d.severity}</span></td>
              <td class="mono technique">
                {#if d.attack_technique}
                  <span class="technique-badge" title={d.attack_tactic ?? ''}>{d.attack_technique}</span>
                {:else}
                  <span class="text-muted">—</span>
                {/if}
              </td>
              <td class="event-count">{getEventCount(d)}</td>
              <td>
                {#if onInvestigate}
                  <button
                    class="btn btn-investigate"
                    onclick={() => onInvestigate!(getDetectionId(d))}
                    disabled={!getDetectionId(d)}
                  >
                    Investigate
                  </button>
                {/if}
              </td>
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
  .technique { font-size: 11px; }
  .event-count { text-align: center; color: var(--text-secondary); font-size: 13px; }
  .text-muted { color: var(--text-muted); }

  .explanation {
    cursor: help;
    color: var(--text-muted);
    font-size: 11px;
    margin-left: 4px;
  }

  .technique-badge {
    background: #312e81;
    color: #a5b4fc;
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: var(--font-mono, monospace);
  }

  .btn-investigate {
    font-size: 11px;
    padding: 3px 10px;
    background: rgba(88, 166, 255, 0.1);
    color: var(--accent-blue, #58a6ff);
    border: 1px solid rgba(88, 166, 255, 0.3);
    border-radius: 4px;
    cursor: pointer;
  }
  .btn-investigate:hover {
    background: rgba(88, 166, 255, 0.2);
  }
  .btn-investigate:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .loading, .empty { padding: 40px; text-align: center; color: var(--text-secondary); }
  .error-banner { padding: 12px 20px; background: rgba(248,81,73,0.1); color: var(--severity-critical); border-bottom: 1px solid rgba(248,81,73,0.3); font-size: 13px; }
</style>
