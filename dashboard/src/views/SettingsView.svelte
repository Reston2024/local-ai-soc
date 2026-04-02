<script lang="ts">
  import { api } from '../lib/api.ts'
  import type { Operator, OperatorCreateResponse, OperatorRotateResponse, ModelStatus } from '../lib/api.ts'

  // ---------------------------------------------------------------------------
  // Tab state
  // ---------------------------------------------------------------------------
  let activeTab = $state<'operators' | 'system'>('operators')

  // ---------------------------------------------------------------------------
  // Operators tab state
  // ---------------------------------------------------------------------------
  let operators = $state<Operator[]>([])
  let operatorsLoading = $state(false)
  let operatorsError = $state('')

  // Create form
  let createUsername = $state('')
  let createRole = $state<'admin' | 'analyst'>('analyst')
  let creating = $state(false)
  let createError = $state('')

  // One-time key display modal
  let newApiKey = $state<string | null>(null)
  let newApiKeyUsername = $state('')

  // TOTP modal
  let totpQrCode = $state<string | null>(null)
  let totpProvisioningUri = $state('')
  let totpUsername = $state('')

  // ---------------------------------------------------------------------------
  // Auto-load operators when tab activates
  // ---------------------------------------------------------------------------
  $effect(() => {
    if (activeTab === 'operators' && operators.length === 0 && !operatorsLoading)
      loadOperators()
  })

  // ---------------------------------------------------------------------------
  // Operators CRUD
  // ---------------------------------------------------------------------------
  async function loadOperators() {
    operatorsLoading = true
    operatorsError = ''
    try {
      const r = await api.settings.operators.list()
      operators = r.operators
    } catch (e: any) {
      operatorsError = e.message
    } finally {
      operatorsLoading = false
    }
  }

  async function createOperator() {
    if (!createUsername.trim()) {
      createError = 'Username is required'
      return
    }
    creating = true
    createError = ''
    try {
      const r: OperatorCreateResponse = await api.settings.operators.create({
        username: createUsername.trim(),
        role: createRole,
      })
      newApiKey = r.api_key
      newApiKeyUsername = r.username
      createUsername = ''
      createRole = 'analyst'
      await loadOperators()
    } catch (e: any) {
      createError = e.message
    } finally {
      creating = false
    }
  }

  async function rotateKey(op: Operator) {
    if (!window.confirm(`Rotate API key for ${op.username}? The old key will immediately stop working.`))
      return
    try {
      const r: OperatorRotateResponse = await api.settings.operators.rotateKey(op.operator_id)
      newApiKey = r.api_key
      newApiKeyUsername = op.username
    } catch (e: any) {
      operatorsError = e.message
    }
  }

  async function deactivateOperator(op: Operator) {
    if (!window.confirm(`Disable operator ${op.username}? They will no longer be able to authenticate.`))
      return
    try {
      await api.settings.operators.deactivate(op.operator_id)
      await loadOperators()
    } catch (e: any) {
      operatorsError = e.message
    }
  }

  async function enableTotp(op: Operator) {
    try {
      const r = await api.settings.operators.enableTotp(op.operator_id)
      totpQrCode = r.qr_code
      totpProvisioningUri = r.provisioning_uri
      totpUsername = op.username
    } catch (e: any) {
      operatorsError = e.message
    }
  }

  function dismissKeyModal() {
    newApiKey = null
    newApiKeyUsername = ''
  }

  function copyKey() {
    if (newApiKey) navigator.clipboard.writeText(newApiKey)
  }

  function dismissTotpModal() {
    totpQrCode = null
    totpProvisioningUri = ''
    totpUsername = ''
  }

  // ---------------------------------------------------------------------------
  // System tab state — model status
  // ---------------------------------------------------------------------------
  let modelStatus = $state<ModelStatus | null>(null)
  let modelStatusLoading = $state(false)
  let modelStatusError = $state('')

  $effect(() => {
    if (activeTab === 'system' && modelStatus === null && !modelStatusLoading)
      loadModelStatus()
  })

  async function loadModelStatus() {
    modelStatusLoading = true
    modelStatusError = ''
    try {
      modelStatus = await api.settings.modelStatus()
    } catch (e: any) {
      modelStatusError = e.message
    } finally {
      modelStatusLoading = false
    }
  }
</script>

<div class="view">
  <!-- Header -->
  <div class="view-header">
    <div class="header-left">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2">
        <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
      <h1>Settings</h1>
    </div>
  </div>

  <!-- Tab bar -->
  <div class="tab-bar">
    {#each [['operators', 'Operators'], ['system', 'System']] as [id, label]}
      <button
        class="tab-btn"
        class:active={activeTab === id}
        onclick={() => activeTab = id as 'operators' | 'system'}
      >{label}</button>
    {/each}
  </div>

  <!-- Content -->
  <div class="content">

    <!-- ------------------------------------------------------------------ -->
    <!-- Operators tab                                                       -->
    <!-- ------------------------------------------------------------------ -->
    {#if activeTab === 'operators'}

      <!-- Create operator form -->
      <div class="card">
        <h2>Create Operator</h2>
        <div class="form-row">
          <label>
            Username
            <input
              type="text"
              bind:value={createUsername}
              placeholder="e.g. alice"
              minlength="3"
              maxlength="64"
            />
          </label>
          <label>
            Role
            <select bind:value={createRole}>
              <option value="analyst">Analyst</option>
              <option value="admin">Admin</option>
            </select>
          </label>
          <button class="btn btn-primary" onclick={createOperator} disabled={creating}>
            {creating ? 'Creating…' : 'Create Operator'}
          </button>
        </div>
        {#if createError}<p class="error">{createError}</p>{/if}
      </div>

      <!-- Operators list -->
      <div class="card">
        <div class="card-header">
          <h2>Operators</h2>
          <button class="btn btn-sm" onclick={loadOperators} disabled={operatorsLoading}>Refresh</button>
        </div>

        {#if operatorsError}<p class="error">{operatorsError}</p>{/if}

        {#if operatorsLoading}
          <p class="muted">Loading…</p>
        {:else if operators.length === 0}
          <p class="muted">No operators found.</p>
        {:else}
          <table class="data-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th>Last Seen</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {#each operators as op}
                <tr class:inactive={!op.is_active}>
                  <td class="username">{op.username}</td>
                  <td>
                    <span class="role-badge role-{op.role}">{op.role}</span>
                  </td>
                  <td>
                    <span class="status-badge" class:active-badge={op.is_active} class:inactive-badge={!op.is_active}>
                      {op.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td class="muted">{new Date(op.created_at).toLocaleDateString()}</td>
                  <td class="muted">{op.last_seen_at ? new Date(op.last_seen_at).toLocaleString() : '—'}</td>
                  <td class="actions">
                    {#if op.is_active}
                      <button class="btn btn-sm" onclick={() => rotateKey(op)}>Rotate Key</button>
                      <button class="btn btn-sm btn-warning" onclick={() => deactivateOperator(op)}>Disable</button>
                      <button class="btn btn-sm btn-totp" onclick={() => enableTotp(op)}>Enable TOTP</button>
                    {:else}
                      <span class="muted">Inactive</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    {/if}

    <!-- ------------------------------------------------------------------ -->
    <!-- System tab — AI model status                                        -->
    <!-- ------------------------------------------------------------------ -->
    {#if activeTab === 'system'}
      <div class="card">
        <h2>AI Model Status</h2>
        {#if modelStatusLoading}
          <p class="muted">Loading model status...</p>
        {:else if modelStatusError}
          <p class="error">{modelStatusError}</p>
        {:else if modelStatus}
          <div class="model-status-grid">
            <div class="status-row">
              <span class="status-label">Active model</span>
              <span class="status-value">{modelStatus.active_model ?? 'Unknown (Ollama unreachable)'}</span>
            </div>
            <div class="status-row">
              <span class="status-label">Last known model</span>
              <span class="status-value">{modelStatus.last_known_model ?? 'Not yet recorded'}</span>
            </div>
            {#if modelStatus.drift_detected}
              <div class="drift-alert" role="alert" aria-live="polite">
                <strong>Model drift detected</strong> — active model differs from last-known model.
                Review the change and confirm it is expected.
              </div>
            {/if}
            {#if modelStatus.last_change}
              <div class="status-row">
                <span class="status-label">Last change detected</span>
                <span class="status-value">{modelStatus.last_change.detected_at}</span>
              </div>
              <div class="status-row">
                <span class="status-label">Previous model</span>
                <span class="status-value">{modelStatus.last_change.previous_model ?? '—'}</span>
              </div>
            {/if}
          </div>
        {:else}
          <p class="muted">No model status available.</p>
        {/if}
      </div>
    {/if}

  </div><!-- .content -->
</div><!-- .view -->

<!-- ========================================================================
     One-time API key modal
     ======================================================================== -->
{#if newApiKey !== null}
  <div class="modal-overlay" role="dialog" aria-modal="true" aria-label="New API Key">
    <div class="modal">
      <h2>API Key for {newApiKeyUsername}</h2>
      <p class="modal-warning">
        This key will only be shown once. Copy it now and store it securely.
      </p>
      <div class="key-display">
        <code class="key-code">{newApiKey}</code>
        <button class="btn btn-sm" onclick={copyKey}>Copy</button>
      </div>
      <div class="modal-footer">
        <button class="btn btn-primary" onclick={dismissKeyModal}>I have saved this key</button>
      </div>
    </div>
  </div>
{/if}

<!-- ========================================================================
     TOTP QR code modal
     ======================================================================== -->
{#if totpQrCode !== null}
  <div class="modal-overlay" role="dialog" aria-modal="true" aria-label="Enable TOTP">
    <div class="modal">
      <h2>Enable TOTP for {totpUsername}</h2>
      <p class="muted">Scan this QR code with Google Authenticator, Authy, or a compatible app.</p>
      <div class="qr-container">
        <img src={totpQrCode} alt="TOTP QR Code" class="qr-image" />
      </div>
      <p class="provisioning-uri muted">{totpProvisioningUri}</p>
      <div class="modal-footer">
        <button class="btn btn-primary" onclick={dismissTotpModal}>Done</button>
      </div>
    </div>
  </div>
{/if}

<style>
  /* Layout */
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
  .view-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
  .header-left { display: flex; align-items: center; gap: 10px; }
  .header-left h1 { font-size: 18px; font-weight: 600; margin: 0; }

  /* Tab bar */
  .tab-bar { display: flex; border-bottom: 1px solid var(--border); background: var(--bg-secondary); flex-shrink: 0; }
  .tab-btn { font-size: 13px; padding: 10px 16px; border: none; background: transparent; cursor: pointer; color: var(--text-secondary); border-bottom: 2px solid transparent; }
  .tab-btn.active { color: #a78bfa; border-bottom-color: #a78bfa; }
  .tab-btn:hover:not(.active) { color: #e5e7eb; }

  /* Content area */
  .content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }

  /* Cards */
  .card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md, 6px); padding: 16px; }
  .card h2 { font-size: 14px; font-weight: 600; margin: 0 0 12px; }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .card-header h2 { margin: 0; }

  /* Form */
  .form-row { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }
  .form-row label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-secondary); }
  input[type=text], select { font-size: 12px; padding: 5px 8px; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-md, 4px); color: inherit; min-width: 160px; }

  /* Buttons */
  .btn { font-size: 13px; padding: 6px 14px; border-radius: var(--radius-md, 4px); border: 1px solid var(--border); cursor: pointer; background: var(--bg-secondary); color: inherit; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-primary { background: #a78bfa; color: #111; border-color: #a78bfa; font-weight: 600; }
  .btn-primary:hover:not(:disabled) { background: #8b5cf6; }
  .btn-sm { font-size: 12px; padding: 4px 10px; }
  .btn-warning { color: #f87171; border-color: #f87171; }
  .btn-warning:hover:not(:disabled) { background: rgba(248,113,113,0.1); }
  .btn-totp { color: #60a5fa; border-color: #60a5fa; }
  .btn-totp:hover:not(:disabled) { background: rgba(96,165,250,0.1); }

  /* Table */
  .data-table { width: 100%; border-collapse: collapse; }
  .data-table td, .data-table th { padding: 8px 10px; font-size: 13px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: middle; }
  .data-table th { font-weight: 600; font-size: 12px; color: var(--text-secondary); }
  .data-table tbody tr:hover { background: var(--bg-secondary); }
  .data-table tr.inactive td { opacity: 0.5; }
  .username { font-weight: 500; }
  .actions { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }

  /* Role badges */
  .role-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
  .role-admin { background: rgba(248,113,113,0.15); color: #f87171; }
  .role-analyst { background: rgba(96,165,250,0.15); color: #60a5fa; }

  /* Status badges */
  .status-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
  .active-badge { background: rgba(34,197,94,0.15); color: #22c55e; }
  .inactive-badge { background: rgba(107,114,128,0.2); color: #6b7280; }

  /* Text */
  .muted { color: var(--text-secondary); font-size: 13px; margin: 0; }
  .error { color: #f87171; font-size: 13px; margin: 0; }

  /* Modals */
  .modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.7);
    display: flex; align-items: center; justify-content: center;
    z-index: 1000;
  }
  .modal {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-md, 8px); padding: 24px;
    max-width: 480px; width: 90%; display: flex; flex-direction: column; gap: 16px;
  }
  .modal h2 { font-size: 16px; font-weight: 600; margin: 0; }
  .modal-warning { color: #fbbf24; font-size: 13px; margin: 0; }
  .modal-footer { display: flex; justify-content: flex-end; }

  /* API key display */
  .key-display { display: flex; gap: 8px; align-items: center; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 4px; padding: 10px 12px; }
  .key-code { font-family: monospace; font-size: 12px; word-break: break-all; flex: 1; }

  /* TOTP QR */
  .qr-container { display: flex; justify-content: center; padding: 8px; }
  .qr-image { max-width: 240px; border-radius: 4px; }
  .provisioning-uri { font-family: monospace; font-size: 10px; word-break: break-all; }

  /* Model status card */
  .model-status-grid { display: grid; gap: 8px; }
  .status-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border, #e5e7eb); }
  .status-label { font-weight: 500; color: var(--text-muted, #6b7280); }
  .status-value { font-family: monospace; }
  .drift-alert { background: #fef3c7; border: 1px solid #f59e0b; border-radius: 6px; padding: 10px 14px; color: #92400e; margin: 8px 0; }
</style>
