<script lang="ts">
  const reportTemplates = [
    { name: 'Executive Summary',       desc: 'High-level security posture, top incidents, risk trend. For leadership and board.',    icon: '📊', period: 'Monthly' },
    { name: 'SOC Operations Report',   desc: 'MTTD/MTTR trends, analyst workload, alert volume, false positive rate.',               icon: '⚙️',  period: 'Weekly' },
    { name: 'MITRE ATT&CK Coverage',   desc: 'Detection coverage heatmap across all ATT&CK tactics and techniques.',                 icon: '🎯', period: 'On demand' },
    { name: 'Incident Report',         desc: 'Detailed timeline, affected assets, indicators, and remediation steps for a case.',    icon: '🔍', period: 'Per incident' },
    { name: 'Compliance Posture',       desc: 'Controls status against NIST CSF, CIS v8, or ISO 27001 frameworks.',                  icon: '✅', period: 'Quarterly' },
    { name: 'Threat Intelligence Digest', desc: 'Active campaigns, new IOCs, adversary TTPs relevant to your industry.',            icon: '🌐', period: 'Weekly' },
  ]
</script>

<div class="view">
  <div class="view-header">
    <div class="header-left">
      <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style="color:#fbbf24">
        <rect x="2" y="10" width="3" height="4" rx="1" fill="currentColor" opacity="0.5"/>
        <rect x="6.5" y="6" width="3" height="8" rx="1" fill="currentColor" opacity="0.75"/>
        <rect x="11" y="2" width="3" height="12" rx="1" fill="currentColor"/>
      </svg>
      <h1>Reports</h1>
    </div>
    <button class="btn" disabled>
      <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
        <line x1="8" y1="2" x2="8" y2="10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
        <path d="M5 7.5L8 11L11 7.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="3" y1="13" x2="13" y2="13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
      </svg>
      Export All
    </button>
  </div>

  <div class="content">
    <div class="section-intro">
      Generate security reports for analysts, managers, and compliance teams. Templates are AI-assisted — populated from live data.
    </div>

    <div class="report-grid">
      {#each reportTemplates as tpl}
        <div class="report-card">
          <div class="report-icon">{tpl.icon}</div>
          <div class="report-info">
            <span class="report-name">{tpl.name}</span>
            <span class="report-desc">{tpl.desc}</span>
          </div>
          <div class="report-footer">
            <span class="report-period">{tpl.period}</span>
            <button class="report-btn" disabled>Generate</button>
          </div>
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

  .view-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 20px; border-bottom: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0;
  }
  .header-left { display: flex; align-items: center; gap: 10px; }
  h1 { font-size: 15px; font-weight: 600; }

  .content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
  .section-intro { font-size: 13px; color: var(--text-secondary); max-width: 640px; line-height: 1.6; }

  .report-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px;
  }

  .report-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-md); padding: 16px;
    display: flex; flex-direction: column; gap: 10px;
    transition: border-color 0.15s;
  }
  .report-card:hover { border-color: var(--border-hover); }

  .report-icon { font-size: 20px; line-height: 1; }
  .report-info { display: flex; flex-direction: column; gap: 5px; flex: 1; }
  .report-name { font-size: 13px; font-weight: 600; }
  .report-desc { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }

  .report-footer { display: flex; align-items: center; justify-content: space-between; }
  .report-period {
    font-size: 11px; color: var(--text-muted);
    background: var(--bg-tertiary); border: 1px solid var(--border);
    padding: 2px 8px; border-radius: 10px;
  }

  .report-btn {
    font-size: 11px; padding: 4px 12px;
    background: rgba(251,191,36,0.08); color: #fbbf24;
    border: 1px solid rgba(251,191,36,0.25); border-radius: var(--radius-md);
    cursor: not-allowed; opacity: 0.5; font-family: var(--font-sans);
  }
</style>
