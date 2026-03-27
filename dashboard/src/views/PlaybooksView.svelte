<script lang="ts">
  const playbooks = [
    {
      name: 'Endpoint Isolation',
      trigger: 'Critical detection',
      steps: ['Identify affected host', 'Isolate via EDR API', 'Collect volatile memory', 'Notify analyst'],
      status: 'draft',
    },
    {
      name: 'Account Lockout',
      trigger: 'Brute-force / credential stuffing',
      steps: ['Identify targeted account', 'Lock via AD/Entra API', 'Capture auth logs', 'Create incident ticket'],
      status: 'draft',
    },
    {
      name: 'Malware Triage',
      trigger: 'High severity file or process detection',
      steps: ['Hash lookup (VirusTotal)', 'Sandbox detonation', 'Check lateral spread', 'Escalate or close'],
      status: 'draft',
    },
    {
      name: 'Phishing Response',
      trigger: 'Suspicious email indicators',
      steps: ['Extract IOCs from email', 'Block sender/domain', 'Check click-through logs', 'User notification'],
      status: 'draft',
    },
  ]
</script>

<div class="view">
  <div class="view-header">
    <div class="header-left">
      <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style="color:#34d399">
        <rect x="3" y="2" width="10" height="12" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
        <line x1="6" y1="6" x2="10" y2="6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="6" y1="9" x2="9" y2="9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
      </svg>
      <h1>Playbooks / SOAR</h1>
    </div>
    <span class="coming-soon-badge">BETA — Coming Soon</span>
  </div>

  <div class="content">
    <div class="section-intro">
      Automated response playbooks — triggered by detection rules, executed against integrated platforms (EDR, AD, email gateways).
    </div>

    <div class="playbook-list">
      {#each playbooks as pb}
        <div class="pb-card">
          <div class="pb-top">
            <div class="pb-left">
              <span class="pb-name">{pb.name}</span>
              <span class="pb-trigger">Trigger: {pb.trigger}</span>
            </div>
            <span class="pb-status">{pb.status}</span>
          </div>
          <div class="pb-steps">
            {#each pb.steps as step, i}
              <div class="step">
                <span class="step-num">{i + 1}</span>
                <span class="step-text">{step}</span>
              </div>
            {/each}
          </div>
          <div class="pb-actions">
            <button class="pb-btn" disabled>Edit</button>
            <button class="pb-btn" disabled>Test Run</button>
            <button class="pb-btn pb-enable" disabled>Enable</button>
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

  .coming-soon-badge {
    font-size: 10px; font-weight: 700; letter-spacing: 0.6px;
    color: var(--accent-purple); background: rgba(167,139,250,0.1);
    border: 1px solid rgba(167,139,250,0.25); padding: 3px 10px; border-radius: 20px;
  }

  .content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 14px; }

  .section-intro { font-size: 13px; color: var(--text-secondary); max-width: 600px; line-height: 1.6; }

  .playbook-list { display: flex; flex-direction: column; gap: 10px; }

  .pb-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-md); padding: 16px;
    display: flex; flex-direction: column; gap: 12px;
  }

  .pb-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
  .pb-left { display: flex; flex-direction: column; gap: 3px; }
  .pb-name { font-size: 14px; font-weight: 600; }
  .pb-trigger { font-size: 11px; color: var(--text-secondary); }

  .pb-status {
    font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--text-muted); background: var(--bg-tertiary);
    border: 1px solid var(--border); padding: 2px 8px; border-radius: 10px;
    white-space: nowrap;
  }

  .pb-steps { display: flex; flex-direction: column; gap: 5px; }
  .step { display: flex; align-items: center; gap: 8px; }
  .step-num {
    width: 18px; height: 18px; border-radius: 50%;
    background: var(--bg-tertiary); border: 1px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 700; color: var(--text-muted);
    flex-shrink: 0;
  }
  .step-text { font-size: 12px; color: var(--text-secondary); }

  .pb-actions { display: flex; gap: 8px; }
  .pb-btn {
    font-size: 11px; padding: 4px 12px;
    background: var(--bg-tertiary); color: var(--text-secondary);
    border: 1px solid var(--border); border-radius: var(--radius-md);
    cursor: not-allowed; opacity: 0.5; font-family: var(--font-sans);
  }
  .pb-enable { color: var(--accent-green); border-color: rgba(34,197,94,0.3); }
</style>
