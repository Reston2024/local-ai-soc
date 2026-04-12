<script lang="ts">
  import { api, type AtomicTechnique, type AtomicTest } from '../lib/api.ts'

  let techniques = $state<AtomicTechnique[]>([])
  let totalTechniques = $state(0)
  let totalTests = $state(0)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let expandedTechniqueId = $state<string | null>(null)
  // Validation state keyed by "technique_id:test_number"
  let validationResults = $state<Record<string, 'pass' | 'fail' | 'checking' | null>>({})
  // Copy feedback keyed by button id (e.g. "T1059.001:1:prereq")
  let copyFeedback = $state<Record<string, boolean>>({})

  $effect(() => {
    api.atomics.list()
      .then(data => {
        techniques = data.techniques
        totalTechniques = data.total_techniques
        totalTests = data.total_tests
        loading = false
      })
      .catch(err => {
        error = String(err)
        loading = false
      })
  })

  function toggleTechnique(tid: string) {
    expandedTechniqueId = expandedTechniqueId === tid ? null : tid
  }

  function validationKey(technique_id: string, test_number: number): string {
    return `${technique_id}:${test_number}`
  }

  async function handleValidate(technique_id: string, test_number: number) {
    const key = validationKey(technique_id, test_number)
    validationResults = { ...validationResults, [key]: 'checking' }
    try {
      const result = await api.atomics.validate(technique_id, test_number)
      validationResults = { ...validationResults, [key]: result.verdict }
    } catch {
      validationResults = { ...validationResults, [key]: 'fail' }
    }
  }

  async function copyToClipboard(text: string, feedbackKey: string) {
    try {
      await navigator.clipboard.writeText(text)
      copyFeedback = { ...copyFeedback, [feedbackKey]: true }
      setTimeout(() => {
        copyFeedback = { ...copyFeedback, [feedbackKey]: false }
      }, 1500)
    } catch {
      // silent
    }
  }

  function coverageLabel(coverage: string): string {
    if (coverage === 'validated') return 'Validated'
    if (coverage === 'detected') return 'Sigma Exists'
    return 'No Coverage'
  }

  function coverageClass(coverage: string): string {
    if (coverage === 'validated') return 'badge-validated'
    if (coverage === 'detected') return 'badge-detected'
    return 'badge-none'
  }

  function platformClass(platform: string): string {
    const p = platform.toLowerCase()
    if (p === 'windows') return 'chip-windows'
    if (p === 'linux') return 'chip-linux'
    if (p === 'macos' || p === 'mac') return 'chip-macos'
    return 'chip-other'
  }

  // Initialise validationResults from persisted test.validation on load
  $effect(() => {
    if (!loading && techniques.length > 0) {
      const init: Record<string, 'pass' | 'fail' | 'checking' | null> = {}
      for (const tech of techniques) {
        for (const test of tech.tests) {
          if (test.validation) {
            init[validationKey(tech.technique_id, test.test_number)] = test.validation.verdict
          }
        }
      }
      if (Object.keys(init).length > 0) {
        validationResults = { ...init, ...validationResults }
      }
    }
  })
</script>

<div class="atomics-view">
  <div class="view-header">
    <div class="header-left">
      <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style="color:#ef4444">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.4"/>
        <path d="M8 4v4l2.5 2.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="8" cy="8" r="1.5" fill="currentColor" opacity="0.6"/>
      </svg>
      <div>
        <h1>Atomic Red Team</h1>
        <p class="subtitle">Adversary simulation tests mapped to MITRE ATT&amp;CK</p>
      </div>
    </div>
    {#if !loading && !error}
      <div class="stats-chips">
        <span class="stat-chip">{totalTechniques} techniques</span>
        <span class="stat-chip">{totalTests} tests</span>
      </div>
    {/if}
  </div>

  <div class="content">
    {#if loading}
      <div class="state-msg">Loading atomics...</div>
    {:else if error}
      <div class="state-msg error">{error}</div>
    {:else if techniques.length === 0}
      <div class="state-msg">No atomics loaded. Run the seed task to populate atomics.</div>
    {:else}
      <div class="technique-list">
        {#each techniques as tech}
          <div class="technique-card">
            <button
              class="technique-header"
              onclick={() => toggleTechnique(tech.technique_id)}
            >
              <span class="chevron">{expandedTechniqueId === tech.technique_id ? '▾' : '▸'}</span>
              <span class="tech-id">{tech.technique_id}</span>
              <span class="tech-name">{tech.display_name}</span>
              <span class="test-count">{tech.tests.length} test{tech.tests.length !== 1 ? 's' : ''}</span>
              <span class="coverage-badge {coverageClass(tech.coverage)}">{coverageLabel(tech.coverage)}</span>
            </button>

            {#if expandedTechniqueId === tech.technique_id}
              <div class="tests-section">
                {#each tech.tests as test}
                  {@const vkey = validationKey(tech.technique_id, test.test_number)}
                  {@const vstate = validationResults[vkey]}
                  <div class="test-row">
                    <div class="test-top">
                      <span class="test-num">#{test.test_number}</span>
                      <span class="test-name">{test.test_name}</span>
                      <div class="platform-chips">
                        {#each test.supported_platforms as plat}
                          <span class="platform-chip {platformClass(plat)}">{plat}</span>
                        {/each}
                      </div>
                      {#if test.elevation_required}
                        <span class="elev-badge">admin</span>
                      {/if}
                    </div>
                    <div class="test-actions">
                      <button
                        class="copy-btn"
                        onclick={() => copyToClipboard(test.invoke_prereq, `${tech.technique_id}:${test.test_number}:prereq`)}
                        title={test.invoke_prereq}
                      >
                        {#if copyFeedback[`${tech.technique_id}:${test.test_number}:prereq`]}
                          Copied!
                        {:else}
                          Prereq
                        {/if}
                      </button>
                      <button
                        class="copy-btn copy-btn-primary"
                        onclick={() => copyToClipboard(test.invoke_command, `${tech.technique_id}:${test.test_number}:test`)}
                        title={test.invoke_command}
                      >
                        {#if copyFeedback[`${tech.technique_id}:${test.test_number}:test`]}
                          Copied!
                        {:else}
                          Test
                        {/if}
                      </button>
                      <button
                        class="copy-btn"
                        onclick={() => copyToClipboard(test.invoke_cleanup, `${tech.technique_id}:${test.test_number}:cleanup`)}
                        title={test.invoke_cleanup}
                      >
                        {#if copyFeedback[`${tech.technique_id}:${test.test_number}:cleanup`]}
                          Copied!
                        {:else}
                          Cleanup
                        {/if}
                      </button>
                      <button
                        class="validate-btn"
                        class:checking={vstate === 'checking'}
                        disabled={vstate === 'checking'}
                        onclick={() => handleValidate(tech.technique_id, test.test_number)}
                      >
                        {vstate === 'checking' ? 'Checking...' : 'Validate'}
                      </button>
                      {#if vstate === 'pass'}
                        <span class="verdict verdict-pass">PASS</span>
                      {:else if vstate === 'fail'}
                        <span class="verdict verdict-fail">FAIL</span>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .atomics-view {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    background: #111;
    color: rgba(255, 255, 255, 0.85);
  }

  .view-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 24px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  h1 {
    font-size: 18px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.92);
    margin: 0;
  }

  .subtitle {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.4);
    margin: 2px 0 0;
  }

  .stats-chips {
    display: flex;
    gap: 8px;
  }

  .stat-chip {
    font-size: 12px;
    padding: 3px 10px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.06);
    color: rgba(255, 255, 255, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .content {
    flex: 1;
    overflow-y: auto;
    padding: 16px 24px;
  }

  .content::-webkit-scrollbar { width: 4px; }
  .content::-webkit-scrollbar-track { background: transparent; }
  .content::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

  .state-msg {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.4);
    text-align: center;
    padding: 48px;
  }

  .state-msg.error {
    color: #ef4444;
  }

  .technique-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .technique-card {
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 6px;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.02);
  }

  .technique-header {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 10px 14px;
    background: none;
    border: none;
    color: inherit;
    font-family: inherit;
    font-size: 13px;
    cursor: pointer;
    text-align: left;
    transition: background 0.1s;
  }

  .technique-header:hover {
    background: rgba(255, 255, 255, 0.04);
  }

  .chevron {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.35);
    flex-shrink: 0;
    width: 14px;
  }

  .tech-id {
    font-family: monospace;
    font-size: 12px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.75);
    flex-shrink: 0;
    min-width: 90px;
  }

  .tech-name {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.55);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .test-count {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.3);
    flex-shrink: 0;
  }

  /* Coverage badges */
  .coverage-badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    flex-shrink: 0;
    font-weight: 500;
  }

  .badge-validated {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.3);
  }

  .badge-detected {
    background: rgba(234, 179, 8, 0.15);
    color: #eab308;
    border: 1px solid rgba(234, 179, 8, 0.3);
  }

  .badge-none {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
  }

  /* Expanded tests section */
  .tests-section {
    border-top: 1px solid rgba(255, 255, 255, 0.05);
  }

  .test-row {
    padding: 10px 14px 10px 38px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .test-row:last-child {
    border-bottom: none;
  }

  .test-top {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .test-num {
    font-size: 11px;
    font-family: monospace;
    color: rgba(255, 255, 255, 0.3);
    flex-shrink: 0;
  }

  .test-name {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.7);
    flex: 1;
    min-width: 200px;
  }

  .platform-chips {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .platform-chip {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 8px;
    font-weight: 500;
  }

  .chip-windows {
    background: rgba(59, 130, 246, 0.15);
    color: #60a5fa;
  }

  .chip-linux {
    background: rgba(168, 85, 247, 0.15);
    color: #c084fc;
  }

  .chip-macos {
    background: rgba(20, 184, 166, 0.15);
    color: #2dd4bf;
  }

  .chip-other {
    background: rgba(255, 255, 255, 0.07);
    color: rgba(255, 255, 255, 0.4);
  }

  .elev-badge {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 8px;
    background: rgba(251, 191, 36, 0.12);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.25);
  }

  /* Action buttons */
  .test-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .copy-btn {
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.06);
    color: rgba(255, 255, 255, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.1);
    cursor: pointer;
    font-family: inherit;
    transition: background 0.1s, color 0.1s;
    min-width: 60px;
    text-align: center;
  }

  .copy-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.8);
  }

  .copy-btn-primary {
    background: rgba(59, 130, 246, 0.15);
    color: #60a5fa;
    border-color: rgba(59, 130, 246, 0.3);
  }

  .copy-btn-primary:hover {
    background: rgba(59, 130, 246, 0.25);
  }

  .validate-btn {
    font-size: 11px;
    padding: 4px 12px;
    border-radius: 4px;
    background: rgba(239, 68, 68, 0.12);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
    cursor: pointer;
    font-family: inherit;
    transition: background 0.1s;
  }

  .validate-btn:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.22);
  }

  .validate-btn.checking,
  .validate-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .verdict {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: monospace;
  }

  .verdict-pass {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.3);
  }

  .verdict-fail {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
  }
</style>
