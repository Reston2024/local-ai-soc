<script lang="ts">
  const presetHunts = [
    { name: 'PowerShell child processes',     mitre: 'T1059.001', desc: 'Identify unusual processes spawned by powershell.exe or pwsh.exe' },
    { name: 'Suspicious network beaconing',   mitre: 'T1071',     desc: 'Detect regular outbound connections with jitter < 5s to external IPs' },
    { name: 'Unusual auth hour patterns',     mitre: 'T1078',     desc: 'Logins outside business hours or from new geolocation' },
    { name: 'LOLBin abuse (certutil/mshta)',  mitre: 'T1218',     desc: 'Living-off-the-land binaries used for payload delivery or evasion' },
    { name: 'Lateral movement via WMI/PsExec', mitre: 'T1021',   desc: 'Remote execution patterns indicating lateral movement' },
    { name: 'Credential dumping indicators',  mitre: 'T1003',     desc: 'Access to LSASS memory or SAM database from unexpected processes' },
  ]

  let query = $state('')
</script>

<div class="view">
  <div class="view-header">
    <div class="header-left">
      <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style="color:#e879f9">
        <circle cx="7.5" cy="7.5" r="5" stroke="currentColor" stroke-width="1.4"/>
        <line x1="7.5" y1="2.5" x2="7.5" y2="4.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="7.5" y1="10.5" x2="7.5" y2="12.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="2.5" y1="7.5" x2="4.5" y2="7.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="10.5" y1="7.5" x2="12.5" y2="7.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <circle cx="7.5" cy="7.5" r="1.5" fill="currentColor"/>
      </svg>
      <h1>Threat Hunting</h1>
    </div>
    <span class="coming-soon-badge">BETA — Coming Soon</span>
  </div>

  <div class="content">
    <div class="hunt-bar">
      <input
        type="text"
        bind:value={query}
        placeholder="Describe what you're hunting for… (e.g. 'PowerShell download cradle')"
        class="hunt-input"
        disabled
      />
      <button class="btn btn-primary" disabled>
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
          <circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="1.6"/>
          <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
        </svg>
        Hunt
      </button>
    </div>

    <div class="preset-label">Preset Hunt Queries</div>
    <div class="hunt-grid">
      {#each presetHunts as hunt}
        <div class="hunt-card">
          <div class="hunt-top">
            <span class="hunt-name">{hunt.name}</span>
            <span class="mitre-tag">{hunt.mitre}</span>
          </div>
          <p class="hunt-desc">{hunt.desc}</p>
          <button class="hunt-run-btn" disabled>Run Hunt</button>
        </div>
      {/each}
    </div>

    <div class="roadmap-note">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" style="flex-shrink:0; color:var(--accent-cyan)">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.5"/>
        <line x1="8" y1="7" x2="8" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="8" cy="5" r="0.8" fill="currentColor"/>
      </svg>
      Hunting will use AI Query under the hood — natural language → DuckDB SQL → ranked results. Backends already support the <code>execute_hunt()</code> API.
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

  .content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 18px; }

  .hunt-bar { display: flex; gap: 10px; }
  .hunt-input {
    flex: 1; height: 38px; border-radius: var(--radius-md);
    font-size: 13px; padding: 0 14px;
  }
  .hunt-input:disabled { opacity: 0.5; cursor: not-allowed; }

  .preset-label {
    font-size: 11px; font-weight: 600; letter-spacing: 0.8px;
    text-transform: uppercase; color: var(--text-muted);
  }

  .hunt-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px;
  }

  .hunt-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-md); padding: 14px; display: flex;
    flex-direction: column; gap: 8px;
    transition: border-color 0.15s;
  }
  .hunt-card:hover { border-color: var(--border-hover); }

  .hunt-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
  .hunt-name { font-size: 13px; font-weight: 600; line-height: 1.3; flex: 1; }

  .mitre-tag {
    font-size: 10px; font-weight: 700; font-family: var(--font-mono);
    color: #a78bfa; background: rgba(167,139,250,0.1);
    border: 1px solid rgba(167,139,250,0.2); padding: 2px 7px; border-radius: 4px;
    white-space: nowrap;
  }

  .hunt-desc { font-size: 12px; color: var(--text-secondary); line-height: 1.5; flex: 1; }

  .hunt-run-btn {
    align-self: flex-start; font-size: 11px; padding: 4px 12px;
    background: var(--bg-tertiary); color: var(--text-secondary);
    border: 1px solid var(--border); border-radius: var(--radius-md);
    cursor: not-allowed; opacity: 0.5; font-family: var(--font-sans);
  }

  .roadmap-note {
    display: flex; align-items: flex-start; gap: 8px;
    background: rgba(0,212,255,0.05); border: 1px solid rgba(0,212,255,0.15);
    border-radius: var(--radius-md); padding: 12px 14px;
    font-size: 12px; color: var(--text-secondary); line-height: 1.6; max-width: 560px;
  }
  code { font-size: 11px; color: var(--accent-cyan); }
</style>
