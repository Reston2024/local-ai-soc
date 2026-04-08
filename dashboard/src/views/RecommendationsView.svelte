<script lang="ts">
  import { onMount } from 'svelte'
  import { api, dispatchRecommendation, type RecommendationItem } from '../lib/api.ts'

  let recommendations = $state<RecommendationItem[]>([])
  let total = $state(0)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let statusFilter = $state('')

  // Per-card dispatch state keyed by recommendation_id
  let dispatching = $state<Record<string, boolean>>({})
  let dispatched = $state<Record<string, boolean>>({})
  let dispatchErrors = $state<Record<string, string | null>>({})

  async function load() {
    loading = true
    error = null
    try {
      const res = await api.recommendations.list({ status: statusFilter || undefined })
      recommendations = res.items ?? []
      total = res.total
    } catch (e) {
      error = String(e)
    } finally {
      loading = false
    }
  }

  async function handleDispatch(rec: RecommendationItem) {
    const id = rec.recommendation_id
    dispatching = { ...dispatching, [id]: true }
    dispatchErrors = { ...dispatchErrors, [id]: null }
    try {
      await dispatchRecommendation(id)
      dispatched = { ...dispatched, [id]: true }
    } catch (err) {
      dispatchErrors = {
        ...dispatchErrors,
        [id]: err instanceof Error ? err.message : 'Dispatch failed',
      }
    } finally {
      dispatching = { ...dispatching, [id]: false }
    }
  }

  onMount(load)

  const confidenceColor: Record<string, string> = {
    high:   '#22c55e',
    medium: '#eab308',
    low:    '#f97316',
    none:   '#ef4444',
  }

  const statusColor: Record<string, string> = {
    draft:    '#4a5d7a',
    approved: '#22c55e',
    rejected: '#ef4444',
    expired:  '#6b7280',
  }
</script>

<div class="view-root">
  <div class="view-header">
    <div class="header-left">
      <h1 class="view-title">Recommendations</h1>
      <span class="total-badge">{total}</span>
    </div>
    <div class="header-actions">
      <select
        class="filter-select"
        bind:value={statusFilter}
        onchange={load}
      >
        <option value="">All statuses</option>
        <option value="draft">Draft</option>
        <option value="approved">Approved</option>
        <option value="rejected">Rejected</option>
      </select>
      <button class="btn-refresh" onclick={load} disabled={loading}>
        {loading ? 'Loading...' : 'Refresh'}
      </button>
    </div>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if loading}
    <div class="loading-state">Loading recommendations...</div>
  {:else if recommendations.length === 0}
    <div class="empty-state">No recommendations found.</div>
  {:else}
    <div class="rec-list">
      {#each recommendations as rec (rec.recommendation_id)}
        <div class="rec-card">
          <div class="rec-card-header">
            <span class="rec-type">{rec.type.replace(/_/g, ' ')}</span>
            <span
              class="rec-status"
              style="color: {statusColor[rec.status] ?? '#4a5d7a'}"
            >{rec.status}</span>
          </div>

          <div class="rec-action">{rec.proposed_action}</div>

          <div class="rec-meta">
            <span class="meta-item">
              Target: <strong>{rec.target}</strong>
            </span>
            <span class="meta-item">
              Scope: <strong>{rec.scope}</strong>
            </span>
            <span class="meta-item" style="color: {confidenceColor[rec.inference_confidence] ?? '#4a5d7a'}">
              Confidence: <strong>{rec.inference_confidence}</strong>
            </span>
          </div>

          {#if rec.rationale?.length > 0}
            <ul class="rec-rationale">
              {#each rec.rationale as point}
                <li>{point}</li>
              {/each}
            </ul>
          {/if}

          <div class="rec-footer">
            <span class="rec-id" title={rec.recommendation_id}>
              {rec.recommendation_id.slice(0, 8)}...
            </span>
            <span class="rec-model">{rec.model_id}</span>

            {#if rec.status === 'approved' && !dispatched[rec.recommendation_id]}
              <button
                class="btn-dispatch"
                onclick={() => handleDispatch(rec)}
                disabled={dispatching[rec.recommendation_id]}
              >
                {dispatching[rec.recommendation_id] ? 'Dispatching...' : 'Dispatch'}
              </button>
            {/if}

            {#if dispatched[rec.recommendation_id]}
              <span class="dispatch-success">Dispatched</span>
            {/if}

            {#if dispatchErrors[rec.recommendation_id]}
              <span class="dispatch-error">{dispatchErrors[rec.recommendation_id]}</span>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .view-root {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    padding: 20px 24px;
    gap: 16px;
  }

  .view-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .view-title {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
  }

  .total-badge {
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    font-size: 12px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 12px;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .filter-select {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    color: var(--text-secondary);
    font-size: 13px;
    padding: 5px 10px;
    border-radius: var(--radius-md);
    cursor: pointer;
  }

  .btn-refresh {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    color: var(--text-secondary);
    font-size: 13px;
    padding: 5px 12px;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background 0.12s;
  }
  .btn-refresh:hover:not(:disabled) { background: var(--bg-tertiary); }
  .btn-refresh:disabled { opacity: 0.5; cursor: not-allowed; }

  .error-banner {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #ef4444;
    padding: 10px 14px;
    border-radius: var(--radius-md);
    font-size: 13px;
    flex-shrink: 0;
  }

  .loading-state,
  .empty-state {
    color: var(--text-muted);
    font-size: 14px;
    text-align: center;
    margin-top: 40px;
  }

  .rec-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow-y: auto;
    flex: 1;
  }

  .rec-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: border-color 0.12s;
  }
  .rec-card:hover { border-color: var(--border-hover, var(--border)); }

  .rec-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .rec-type {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .rec-status {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
  }

  .rec-action {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.4;
  }

  .rec-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }

  .meta-item {
    font-size: 12px;
    color: var(--text-muted);
  }

  .rec-rationale {
    margin: 0;
    padding-left: 16px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .rec-rationale li {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .rec-footer {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 4px;
    padding-top: 8px;
    border-top: 1px solid var(--border);
  }

  .rec-id {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
  }

  .rec-model {
    font-size: 11px;
    color: var(--text-muted);
    flex: 1;
  }

  .btn-dispatch {
    background: rgba(34, 197, 94, 0.1);
    border: 1px solid rgba(34, 197, 94, 0.3);
    color: #22c55e;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
  }
  .btn-dispatch:hover:not(:disabled) {
    background: rgba(34, 197, 94, 0.2);
    border-color: rgba(34, 197, 94, 0.5);
  }
  .btn-dispatch:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .dispatch-success {
    font-size: 12px;
    font-weight: 600;
    color: #22c55e;
  }

  .dispatch-error {
    font-size: 12px;
    color: #ef4444;
  }
</style>
