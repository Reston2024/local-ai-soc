<script lang="ts">
  // Threat Intel — feed integration stub
  const feeds = [
    { name: 'MISP Community', status: 'pending', iocs: 0,    updated: null },
    { name: 'AlienVault OTX', status: 'pending', iocs: 0,    updated: null },
    { name: 'Abuse.ch URLhaus', status: 'pending', iocs: 0,  updated: null },
    { name: 'Emerging Threats', status: 'pending', iocs: 0,  updated: null },
  ]
</script>

<div class="view">
  <div class="view-header">
    <div class="header-left">
      <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style="color:#f97316">
        <path d="M8 2a6 6 0 1 1 0 12A6 6 0 0 1 8 2Z" stroke="currentColor" stroke-width="1.4"/>
        <path d="M8 5v3.5l2 1.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <h1>Threat Intelligence</h1>
    </div>
    <span class="coming-soon-badge">BETA — Coming Soon</span>
  </div>

  <div class="content">
    <div class="section-intro">
      <p>Integrate external threat intelligence feeds to enrich detections with IOC context, active campaign data, and adversary TTPs. Planned sources:</p>
    </div>

    <div class="feed-grid">
      {#each feeds as feed}
        <div class="feed-card">
          <div class="feed-header">
            <span class="feed-name">{feed.name}</span>
            <span class="feed-status pending">Not configured</span>
          </div>
          <div class="feed-stats">
            <div class="feed-stat">
              <span class="stat-val">—</span>
              <span class="stat-key">IOCs</span>
            </div>
            <div class="feed-stat">
              <span class="stat-val">—</span>
              <span class="stat-key">Last sync</span>
            </div>
          </div>
        </div>
      {/each}
    </div>

    <div class="roadmap-note">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" style="flex-shrink:0; color:var(--accent-cyan)">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.5"/>
        <line x1="8" y1="7" x2="8" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="8" cy="5" r="0.8" fill="currentColor"/>
      </svg>
      <span>Threat intel integration is on the Phase 13 roadmap. IOC matching will enrich detections automatically on ingestion.</span>
    </div>
  </div>
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

  .header-left { display: flex; align-items: center; gap: 10px; }
  h1 { font-size: 15px; font-weight: 600; }

  .coming-soon-badge {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.6px;
    color: var(--accent-purple);
    background: rgba(167,139,250,0.1);
    border: 1px solid rgba(167,139,250,0.25);
    padding: 3px 10px;
    border-radius: 20px;
  }

  .content { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 20px; }

  .section-intro p { font-size: 13px; color: var(--text-secondary); max-width: 600px; line-height: 1.6; }

  .feed-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 12px;
  }

  .feed-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .feed-header { display: flex; align-items: center; justify-content: space-between; }
  .feed-name { font-size: 13px; font-weight: 600; }
  .feed-status.pending {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    padding: 2px 8px;
    border-radius: 10px;
  }

  .feed-stats { display: flex; gap: 20px; }
  .feed-stat { display: flex; flex-direction: column; gap: 2px; }
  .stat-val { font-size: 16px; font-weight: 700; color: var(--text-muted); }
  .stat-key { font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); }

  .roadmap-note {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    background: rgba(0,212,255,0.05);
    border: 1px solid rgba(0,212,255,0.15);
    border-radius: var(--radius-md);
    padding: 12px 14px;
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.6;
    max-width: 560px;
  }
</style>
