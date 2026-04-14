<script lang="ts">
  import { api, type TacticCoverage, type ActorMatch } from '../lib/api.ts'

  let coverage = $state<TacticCoverage[] | null>(null)
  let actorMatches = $state<ActorMatch[] | null>(null)
  let expandedTactic = $state<string | null>(null)
  let loading = $state(true)
  let error = $state<string | null>(null)

  function heatColour(n: number): string {
    if (n === 0) return '#333'
    if (n <= 2) return '#7a4400'
    if (n <= 9) return '#c96a00'
    return '#e84a00'
  }

  function toggleTactic(tactic: string) {
    expandedTactic = expandedTactic === tactic ? null : tactic
  }

  function confidenceClass(confidence: string): string {
    if (confidence === 'High') return 'conf-high'
    if (confidence === 'Medium') return 'conf-medium'
    return 'conf-low'
  }

  $effect(() => {
    loading = true
    error = null
    Promise.all([
      api.attack.coverage(),
      api.attack.actorMatches(),
    ]).then(([cov, actors]) => {
      coverage = cov
      actorMatches = actors
    }).catch(e => {
      error = String(e)
    }).finally(() => {
      loading = false
    })
  })
</script>

<div class="view">
  <div class="view-header">
    <div class="header-left">
      <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style="color:#e84a00">
        <rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.4"/>
        <rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.4"/>
        <rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.4"/>
        <rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" stroke-width="1.4"/>
      </svg>
      <div>
        <h1>ATT&CK Coverage</h1>
        <p class="subtitle">MITRE ATT&CK technique coverage by tactic</p>
      </div>
    </div>
  </div>

  <div class="content">
    {#if loading}
      <div class="loading-state">Loading coverage data…</div>
    {:else if error}
      <div class="error-state">{error}</div>
    {:else}

      <!-- Actor Matches -->
      {#if actorMatches && actorMatches.length > 0}
        <div class="section-title">Threat Actor Overlap</div>
        <div class="actor-grid">
          {#each actorMatches.slice(0, 3) as actor}
            <div class="actor-card">
              <div class="actor-header">
                <span class="actor-name">{actor.name}</span>
                <span class="conf-badge {confidenceClass(actor.confidence)}">{actor.confidence}</span>
              </div>
              <div class="actor-group">{actor.group_id}</div>
              {#if actor.aliases.length > 0}
                <div class="actor-aliases">{actor.aliases.slice(0, 2).join(', ')}</div>
              {/if}
              <div class="actor-stats">
                <span class="overlap-pct">{actor.overlap_pct.toFixed(0)}% overlap</span>
                <span class="match-count">{actor.matched_count} / {actor.total_count} techniques</span>
              </div>
            </div>
          {/each}
        </div>
      {/if}

      <!-- ATT&CK Heatmap -->
      <div class="section-title" style="margin-top: 16px">Tactic Coverage Heatmap</div>

      {#if !coverage || coverage.length === 0}
        <div class="empty-state">No ATT&CK coverage data. Run detection rules to build coverage.</div>
      {:else}
        <div class="heatmap-grid">
          {#each coverage as tactic}
            <div
              class="tactic-col {expandedTactic === tactic.tactic ? 'expanded' : ''}"
              role="button"
              tabindex="0"
              onclick={() => toggleTactic(tactic.tactic)}
              onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') toggleTactic(tactic.tactic) }}
            >
              <div class="tactic-header" style="background: {heatColour(tactic.covered_count)}">
                <span class="tactic-short">{tactic.tactic_short}</span>
              </div>
              <div class="tactic-badge">
                <span class="covered">{tactic.covered_count}</span>
                <span class="sep">/</span>
                <span class="total">{tactic.total_techniques}</span>
              </div>
            </div>
          {/each}
        </div>

        <!-- Expanded tactic drill-down -->
        {#if expandedTactic}
          {@const expandedData = coverage.find(t => t.tactic === expandedTactic)}
          {#if expandedData}
            <div class="tactic-detail">
              <div class="tactic-detail-header">
                <h3>{expandedData.tactic}</h3>
                <span class="tactic-detail-stats">{expandedData.covered_count} covered / {expandedData.total_techniques} total</span>
                <button class="close-btn" onclick={() => { expandedTactic = null }}>Close</button>
              </div>
              <div class="technique-list">
                {#each [...expandedData.techniques].sort((a, b) => (b.covered ? 1 : 0) - (a.covered ? 1 : 0)) as tech}
                  {@const mitreUrl = `https://attack.mitre.org/techniques/${tech.tech_id.replace('.', '/')}/`}
                  <div class="technique-row {tech.covered ? 'covered' : 'uncovered'}">
                    <span class="tech-status">
                      {#if tech.covered}
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                          <path d="M2 6l3 3 5-5" stroke="#22c55e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                      {:else}
                        <span class="dash">—</span>
                      {/if}
                    </span>
                    <a class="tech-id mono" href={mitreUrl} target="_blank" rel="noopener noreferrer">{tech.tech_id}</a>
                    <a class="tech-name tech-link" href={mitreUrl} target="_blank" rel="noopener noreferrer">{tech.name}</a>
                    {#if tech.covered && tech.rule_titles.length > 0}
                      <span class="tech-rules">{tech.rule_titles[0]}{tech.rule_titles.length > 1 ? ` +${tech.rule_titles.length - 1}` : ''}</span>
                    {/if}
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        {/if}
      {/if}

    {/if}
  </div>
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

  .view-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 20px; border-bottom: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0;
  }
  .header-left { display: flex; align-items: center; gap: 10px; }
  h1 { font-size: 15px; font-weight: 600; margin: 0; }
  .subtitle { font-size: 11px; color: var(--text-muted); margin: 2px 0 0; }

  .content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }

  .loading-state,
  .error-state,
  .empty-state {
    padding: 40px 24px;
    font-size: 13px;
    color: var(--text-secondary);
    text-align: center;
  }
  .error-state { color: #ef4444; }

  .section-title {
    font-size: 10px; font-weight: 700; letter-spacing: 0.8px;
    text-transform: uppercase; color: var(--text-muted);
  }

  /* Actor cards */
  .actor-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px;
  }

  .actor-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-md); padding: 12px 14px;
    display: flex; flex-direction: column; gap: 6px;
  }

  .actor-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .actor-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }

  .conf-badge {
    font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 8px;
    text-transform: uppercase; letter-spacing: 0.3px;
  }
  .conf-high   { background: rgba(239,68,68,0.15);  color: #ef4444; }
  .conf-medium { background: rgba(234,179,8,0.15);  color: #eab308; }
  .conf-low    { background: rgba(100,116,139,0.15); color: #94a3b8; }

  .actor-group   { font-size: 11px; color: var(--text-muted); font-family: monospace; }
  .actor-aliases { font-size: 11px; color: var(--text-secondary); font-style: italic; }
  .actor-stats   { display: flex; align-items: center; justify-content: space-between; margin-top: 2px; }
  .overlap-pct   { font-size: 12px; font-weight: 700; color: #e84a00; }
  .match-count   { font-size: 11px; color: var(--text-muted); }

  /* Heatmap */
  .heatmap-grid {
    display: grid;
    grid-template-columns: repeat(14, 1fr);
    gap: 4px;
    min-width: 0;
  }

  .tactic-col {
    display: flex; flex-direction: column; align-items: center;
    cursor: pointer; border-radius: 6px; overflow: hidden;
    border: 1px solid rgba(255,255,255,0.06);
    transition: border-color 0.15s, transform 0.1s;
    min-width: 0;
  }
  .tactic-col:hover { border-color: rgba(255,255,255,0.2); transform: translateY(-1px); }
  .tactic-col.expanded { border-color: rgba(232,74,0,0.5); }

  .tactic-header {
    width: 100%; padding: 8px 4px 6px;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.2s;
  }

  .tactic-short {
    font-size: 9px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.3px; color: rgba(255,255,255,0.85);
    text-align: center; word-break: break-word;
  }

  .tactic-badge {
    padding: 6px 4px; display: flex; align-items: center; justify-content: center;
    gap: 2px; font-size: 10px; font-variant-numeric: tabular-nums;
    width: 100%; background: #1a1a1a; text-align: center;
  }
  .tactic-badge .covered { font-weight: 700; color: #e84a00; }
  .tactic-badge .sep     { color: var(--text-muted); }
  .tactic-badge .total   { color: var(--text-muted); }

  /* Tactic drill-down panel */
  .tactic-detail {
    background: #1a1a1a;
    border: 1px solid rgba(255,255,255,0.08);
    border-left: 3px solid #e84a00;
    border-radius: 6px;
    padding: 16px;
    margin-top: 4px;
  }

  .tactic-detail-header {
    display: flex; align-items: center; gap: 12px; margin-bottom: 12px;
  }
  .tactic-detail-header h3 { font-size: 14px; font-weight: 600; margin: 0; flex: 1; }
  .tactic-detail-stats { font-size: 11px; color: var(--text-muted); }

  .close-btn {
    padding: 3px 10px; font-size: 11px; background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1); border-radius: 4px;
    color: var(--text-secondary); cursor: pointer;
  }
  .close-btn:hover { background: rgba(255,255,255,0.1); }

  .technique-list { display: flex; flex-direction: column; gap: 2px; }

  .technique-row {
    display: flex; align-items: center; gap: 10px;
    padding: 5px 8px; border-radius: 4px; font-size: 12px;
  }
  .technique-row.covered   { background: rgba(34,197,94,0.05); }
  .technique-row.uncovered { opacity: 0.55; }

  .tech-status {
    width: 16px; height: 16px; display: flex;
    align-items: center; justify-content: center; flex-shrink: 0;
  }
  .dash { font-size: 14px; color: var(--text-muted); }

  .tech-id   { color: var(--text-muted); min-width: 70px; flex-shrink: 0; text-decoration: none; }
  .tech-id:hover { color: var(--accent, #60a5fa); text-decoration: underline; }
  .tech-name { flex: 1; color: var(--text-secondary); text-decoration: none; }
  .tech-link:hover { color: var(--accent, #60a5fa); text-decoration: underline; }
  .tech-rules {
    font-size: 10.5px; color: #22c55e; background: rgba(34,197,94,0.1);
    padding: 1px 7px; border-radius: 8px; white-space: nowrap;
    max-width: 200px; overflow: hidden; text-overflow: ellipsis;
  }

  .mono { font-family: 'JetBrains Mono', 'Fira Code', monospace; }
</style>
