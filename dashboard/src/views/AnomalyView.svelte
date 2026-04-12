<script lang="ts">
  import { api, type AnomalyEvent, type EntityProfile, type ScoreTrendResponse } from '../lib/api.ts'

  let anomalies = $state<AnomalyEvent[]>([])
  let loading = $state(true)
  let error = $state<string | null>(null)
  let minScore = $state(0.5)
  let selectedEvent = $state<AnomalyEvent | null>(null)
  let entityProfile = $state<EntityProfile | null>(null)
  let trendData = $state<ScoreTrendResponse | null>(null)
  let profileLoading = $state(false)
  let showTrend = $state(false)

  async function loadAnomalies() {
    loading = true
    error = null
    try {
      const res = await api.anomaly.list(minScore, 200)
      anomalies = res.anomalies
    } catch (e) {
      error = 'Failed to load anomalies'
    } finally {
      loading = false
    }
  }

  $effect(() => {
    loadAnomalies()
  })

  async function selectEvent(ev: AnomalyEvent) {
    selectedEvent = ev
    profileLoading = true
    trendData = null
    showTrend = false
    try {
      // Extract subnet from src_ip (first 3 octets)
      const subnet = ev.src_ip ? ev.src_ip.split('.').slice(0, 3).join('.') : 'unknown_subnet'
      const proc = ev.process_name || 'unknown'
      entityProfile = await api.anomaly.entityProfile(subnet, proc)
    } catch (e) {
      entityProfile = null
    } finally {
      profileLoading = false
    }
  }

  async function loadTrend() {
    if (!entityProfile) return
    showTrend = true
    try {
      trendData = await api.anomaly.trend(entityProfile.entity_key, 24)
    } catch (e) {
      trendData = null
    }
  }

  function scoreColor(score: number): string {
    if (score >= 0.85) return 'var(--danger, #ef4444)'
    if (score >= 0.7) return 'var(--warning, #f59e0b)'
    return 'var(--info, #3b82f6)'
  }

  function scoreLabel(score: number): string {
    if (score >= 0.85) return 'critical'
    if (score >= 0.7) return 'high'
    if (score >= 0.5) return 'medium'
    return 'low'
  }
</script>

<div class="anomaly-view">
  <div class="anomaly-header">
    <h2>Anomaly Profiles</h2>
    <div class="filter-bar">
      <label>
        Min Score: <strong>{minScore.toFixed(2)}</strong>
        <input type="range" min="0.3" max="1.0" step="0.05"
               bind:value={minScore}
               onchange={loadAnomalies} />
      </label>
      <button class="btn-refresh" onclick={loadAnomalies}>Refresh</button>
    </div>
  </div>

  {#if loading}
    <div class="loading">Loading anomaly data…</div>
  {:else if error}
    <div class="error-msg">{error}</div>
  {:else}
    <div class="anomaly-body">
      <!-- Events table -->
      <div class="anomaly-table-wrap">
        <table class="anomaly-table">
          <thead>
            <tr>
              <th>Score</th>
              <th>Hostname</th>
              <th>Process</th>
              <th>Src IP</th>
              <th>Event Type</th>
              <th>Severity</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {#each anomalies as ev}
              <tr
                class="anomaly-row"
                class:selected={selectedEvent?.event_id === ev.event_id}
                onclick={() => selectEvent(ev)}
              >
                <td class="score-cell">
                  <div class="score-bar-wrap">
                    <div class="score-fill"
                         style="width: {(ev.anomaly_score * 100).toFixed(0)}%; background: {scoreColor(ev.anomaly_score)}">
                    </div>
                  </div>
                  <span class="score-val" style="color: {scoreColor(ev.anomaly_score)}">
                    {ev.anomaly_score.toFixed(3)}
                  </span>
                </td>
                <td>{ev.hostname ?? '—'}</td>
                <td class="process-cell">{ev.process_name ?? '—'}</td>
                <td class="ip-cell">{ev.src_ip ?? '—'}</td>
                <td>{ev.event_type ?? '—'}</td>
                <td><span class="badge badge-{ev.severity}">{ev.severity}</span></td>
                <td class="ts-cell">{new Date(ev.timestamp).toLocaleString()}</td>
              </tr>
            {:else}
              <tr><td colspan="7" class="empty-msg">No anomalies above {minScore.toFixed(2)} threshold</td></tr>
            {/each}
          </tbody>
        </table>
        <div class="table-footer">Showing {anomalies.length} events</div>
      </div>

      <!-- Entity profile panel -->
      {#if selectedEvent}
        <div class="profile-panel">
          <div class="profile-header">
            <h3>Entity Profile</h3>
            <button class="btn-close" onclick={() => { selectedEvent = null; entityProfile = null }}>x</button>
          </div>
          {#if profileLoading}
            <div class="loading">Loading profile…</div>
          {:else if entityProfile}
            <div class="profile-stats">
              <div class="stat-row"><span class="stat-label">Entity Key</span><span class="stat-val mono">{entityProfile.entity_key}</span></div>
              <div class="stat-row"><span class="stat-label">Events</span><span class="stat-val">{entityProfile.event_count}</span></div>
              <div class="stat-row"><span class="stat-label">Avg Score</span><span class="stat-val" style="color:{scoreColor(entityProfile.avg_score)}">{entityProfile.avg_score.toFixed(3)}</span></div>
              <div class="stat-row"><span class="stat-label">Max Score</span><span class="stat-val" style="color:{scoreColor(entityProfile.max_score)}">{entityProfile.max_score.toFixed(3)}</span></div>
            </div>

            <!-- Sparkline -->
            <div class="sparkline-wrap">
              <div class="sparkline-label">Recent Score Distribution</div>
              <div class="sparkline">
                {#each entityProfile.scores.slice(0, 50) as pt}
                  <div class="spark-bar"
                       style="height: {(pt.score * 100).toFixed(0)}%; background: {scoreColor(pt.score)}"
                       title="{pt.score.toFixed(3)} @ {new Date(pt.timestamp).toLocaleString()}">
                  </div>
                {/each}
              </div>
            </div>

            <!-- Trend toggle -->
            {#if !showTrend}
              <button class="btn-trend" onclick={loadTrend}>Show 24h Trend</button>
            {:else if trendData}
              <div class="trend-wrap">
                <div class="trend-label">24h Score Trend ({trendData.trend.length} points)</div>
                <div class="trend-chart">
                  {#each trendData.trend as pt, i}
                    <div class="trend-point"
                         style="left: {(i / Math.max(trendData.trend.length - 1, 1) * 100).toFixed(1)}%; bottom: {(pt.score * 100).toFixed(0)}%; background: {scoreColor(pt.score)}"
                         title="{pt.score.toFixed(3)} @ {new Date(pt.timestamp).toLocaleString()}">
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          {:else}
            <div class="empty-msg">No profile data for this entity</div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .anomaly-view { display: flex; flex-direction: column; height: 100%; padding: 1rem; gap: 0.75rem; overflow: hidden; }
  .anomaly-header { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
  .anomaly-header h2 { margin: 0; font-size: 1.1rem; font-weight: 600; }
  .filter-bar { display: flex; align-items: center; gap: 1rem; font-size: 0.85rem; }
  .filter-bar label { display: flex; align-items: center; gap: 0.5rem; }
  .btn-refresh, .btn-trend { padding: 0.3rem 0.75rem; border-radius: 4px; border: 1px solid rgba(255,255,255,0.15); background: rgba(255,255,255,0.06); color: inherit; cursor: pointer; font-size: 0.8rem; }
  .btn-refresh:hover, .btn-trend:hover { background: rgba(255,255,255,0.12); }
  .anomaly-body { display: flex; gap: 1rem; flex: 1; overflow: hidden; }
  .anomaly-table-wrap { flex: 1; overflow: auto; display: flex; flex-direction: column; }
  .anomaly-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
  .anomaly-table th { padding: 0.4rem 0.6rem; text-align: left; font-weight: 600; color: rgba(255,255,255,0.55); border-bottom: 1px solid rgba(255,255,255,0.08); white-space: nowrap; }
  .anomaly-table td { padding: 0.35rem 0.6rem; border-bottom: 1px solid rgba(255,255,255,0.05); }
  .anomaly-row { cursor: pointer; transition: background 0.1s; }
  .anomaly-row:hover { background: rgba(255,255,255,0.04); }
  .anomaly-row.selected { background: rgba(255,255,255,0.08); }
  .score-cell { display: flex; align-items: center; gap: 0.4rem; min-width: 100px; }
  .score-bar-wrap { flex: 1; height: 6px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden; }
  .score-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
  .score-val { font-size: 0.78rem; font-weight: 600; min-width: 44px; }
  .process-cell, .ip-cell { font-family: monospace; font-size: 0.8rem; }
  .ts-cell { font-size: 0.78rem; color: rgba(255,255,255,0.55); white-space: nowrap; }
  .table-footer { font-size: 0.78rem; color: rgba(255,255,255,0.4); padding: 0.4rem 0.6rem; flex-shrink: 0; }
  .empty-msg { text-align: center; padding: 2rem; color: rgba(255,255,255,0.4); font-size: 0.9rem; }
  .loading { padding: 2rem; text-align: center; color: rgba(255,255,255,0.5); }
  .error-msg { padding: 1rem; color: #ef4444; background: rgba(239,68,68,0.1); border-radius: 6px; }

  /* Profile panel */
  .profile-panel { width: 320px; flex-shrink: 0; display: flex; flex-direction: column; gap: 0.75rem; overflow-y: auto; border-left: 1px solid rgba(255,255,255,0.08); padding-left: 1rem; }
  .profile-header { display: flex; justify-content: space-between; align-items: center; }
  .profile-header h3 { margin: 0; font-size: 0.95rem; font-weight: 600; }
  .btn-close { background: none; border: none; color: rgba(255,255,255,0.5); cursor: pointer; font-size: 1rem; padding: 0.1rem 0.3rem; }
  .btn-close:hover { color: rgba(255,255,255,0.9); }
  .profile-stats { display: flex; flex-direction: column; gap: 0.35rem; }
  .stat-row { display: flex; justify-content: space-between; font-size: 0.82rem; }
  .stat-label { color: rgba(255,255,255,0.5); }
  .stat-val { font-weight: 500; }
  .stat-val.mono { font-family: monospace; font-size: 0.78rem; }

  /* Sparkline */
  .sparkline-wrap { display: flex; flex-direction: column; gap: 0.25rem; }
  .sparkline-label { font-size: 0.75rem; color: rgba(255,255,255,0.45); }
  .sparkline { display: flex; align-items: flex-end; gap: 1px; height: 48px; background: rgba(255,255,255,0.03); border-radius: 4px; padding: 2px; overflow: hidden; }
  .spark-bar { flex: 1; min-width: 3px; border-radius: 2px 2px 0 0; transition: height 0.2s; }

  /* Trend chart */
  .trend-wrap { display: flex; flex-direction: column; gap: 0.25rem; }
  .trend-label { font-size: 0.75rem; color: rgba(255,255,255,0.45); }
  .trend-chart { position: relative; height: 80px; background: rgba(255,255,255,0.03); border-radius: 4px; overflow: hidden; }
  .trend-point { position: absolute; width: 4px; height: 4px; border-radius: 50%; transform: translateX(-50%); }

  /* Badges */
  .badge { padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.72rem; font-weight: 600; text-transform: uppercase; }
  .badge-critical { background: rgba(239,68,68,0.2); color: #ef4444; }
  .badge-high { background: rgba(245,158,11,0.2); color: #f59e0b; }
  .badge-medium { background: rgba(59,130,246,0.2); color: #3b82f6; }
  .badge-low { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.6); }
</style>
