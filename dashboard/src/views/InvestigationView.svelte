<script lang="ts">
  import { api } from '../lib/api.ts'
  import type { TimelineItem, ChatHistoryMessage, CARAnalytic } from '../lib/api.ts'

  let {
    investigationId = '',
    onOpenInGraph = undefined,
    onRunPlaybook = undefined,
  }: {
    investigationId?: string
    onOpenInGraph?: (entityId: string) => void
    onRunPlaybook?: (investigationId: string) => void
  } = $props()

  // Investigation result — holds car_analytics from POST /api/investigate
  let investigationResult = $state<{ car_analytics?: CARAnalytic[]; detection?: { attack_technique?: string } } | null>(null)

  // Timeline state
  let timelineItems = $state<TimelineItem[]>([])
  let timelineLoading = $state(false)
  let timelineError = $state('')

  // Chat state
  let chatMessages = $state<ChatHistoryMessage[]>([])
  let inputText = $state('')
  let isStreaming = $state(false)
  let streamingContent = $state('')  // current assistant response being streamed
  let abortController = $state<AbortController | null>(null)

  // Load timeline + chat history + investigation result when investigationId changes
  $effect(() => {
    if (!investigationId) return
    loadTimeline()
    loadChatHistory()
    loadInvestigation()
  })

  async function loadInvestigation() {
    try {
      const res = await api.investigate(investigationId)
      investigationResult = res
    } catch { /* investigation fetch failure is non-critical — CAR section simply won't appear */ }
  }

  async function loadTimeline() {
    timelineLoading = true
    timelineError = ''
    try {
      const res = await api.investigations.timeline(investigationId)
      timelineItems = res.items
    } catch (e: any) {
      timelineError = e.message
    } finally {
      timelineLoading = false
    }
  }

  async function loadChatHistory() {
    try {
      const res = await api.investigations.chatHistory(investigationId)
      chatMessages = res.messages
    } catch { /* ignore — history is best-effort */ }
  }

  async function sendMessage() {
    if (!inputText.trim() || isStreaming) return
    const question = inputText.trim()
    inputText = ''
    isStreaming = true
    streamingContent = ''
    abortController = new AbortController()

    try {
      await api.investigations.chatStream(
        investigationId,
        question,
        (token) => { streamingContent += token },
        () => {
          chatMessages = [...chatMessages, { id: crypto.randomUUID(), investigation_id: investigationId, role: 'assistant', content: streamingContent, created_at: new Date().toISOString() }]
          streamingContent = ''
          isStreaming = false
        },
        abortController.signal,
      )
    } catch (e: any) {
      if (e.name !== 'AbortError') console.error('Chat error:', e)
      isStreaming = false
      streamingContent = ''
    }
  }

  function stopStream() {
    abortController?.abort()
    isStreaming = false
    streamingContent = ''
  }

  function fmtTime(ts: string): string {
    try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
    catch { return ts.slice(0, 19) }
  }

  function confidenceLevel(score: number | undefined): string {
    if (score === undefined) return 'unknown'
    if (score >= 0.8) return 'high'
    if (score >= 0.5) return 'medium'
    return 'low'
  }
</script>

<div class="investigation-view">

  <!-- Timeline panel -->
  <div class="panel timeline-panel">
    <div class="panel-header">
      <h2>Evidence Timeline</h2>
      <div class="header-actions">
        {#if onOpenInGraph && investigationId}
          <button class="btn-secondary" onclick={() => onOpenInGraph?.(investigationId)}>Open in Graph</button>
        {/if}
        <button
          class="btn-secondary btn-run-playbook"
          disabled={!investigationId}
          title={investigationId ? 'Run a playbook against this investigation' : 'No investigation selected'}
          onclick={() => { if (onRunPlaybook && investigationId) onRunPlaybook(investigationId) }}
        >&#10003; Run Playbook</button>
        <button class="btn-secondary" onclick={loadTimeline}>Refresh</button>
      </div>
    </div>
    {#if timelineLoading}
      <p class="muted">Loading timeline...</p>
    {:else if timelineError}
      <p class="error">{timelineError}</p>
    {:else if timelineItems.length === 0}
      <p class="muted">No events found for investigation {investigationId || '(none selected)'}.</p>
    {:else}
      <div class="timeline">
        {#each timelineItems as item (item.item_id)}
          <div class="timeline-entry severity-{item.severity ?? 'info'}">
            <div class="timeline-dot"></div>
            <div class="timeline-line"></div>
            <div class="timeline-content">
              <span class="time">{fmtTime(item.timestamp)}</span>
              <span class="badge type-{item.item_type}">{item.item_type}</span>
              {#if item.attack_technique}
                <span class="badge mitre">{item.attack_technique}</span>
              {/if}
              {#if item.attack_tactic}
                <span class="badge tactic">{item.attack_tactic}</span>
              {/if}
              <p class="item-title">{item.title}</p>
              {#each item.entity_labels as label}
                <span class="entity-badge">{label}</span>
              {/each}
            </div>
          </div>
        {/each}
      </div>
    {/if}

    {#if investigationResult?.car_analytics && investigationResult.car_analytics.length > 0}
      <section class="inv-section car-analytics-section">
        <h3 class="inv-section-title">CAR Analytics</h3>
        <p class="inv-section-subtitle">MITRE Cyber Analytics Repository — validated detection guidance for {investigationResult.detection?.attack_technique ?? 'this technique'}</p>
        <div class="car-panel">
          {#each investigationResult.car_analytics as analytic (analytic.analytic_id + analytic.technique_id)}
            <div class="car-card">
              <div class="car-card-header">
                <code class="car-id-badge">{analytic.analytic_id}</code>
                <span class="car-title">{analytic.title}</span>
                <span class="car-coverage coverage-{analytic.coverage_level.toLowerCase()}">{analytic.coverage_level}</span>
                <a href="https://car.mitre.org/analytics/{analytic.analytic_id}/" target="_blank" rel="noopener noreferrer" class="car-link">CAR ↗</a>
                <a href="https://attack.mitre.org/techniques/{analytic.technique_id}/" target="_blank" rel="noopener noreferrer" class="car-link">ATT&CK ↗</a>
              </div>
              {#if analytic.description}
                <p class="car-description">{analytic.description}</p>
              {/if}
              {#if analytic.log_sources}
                <div class="car-meta"><span class="car-label">Log Sources:</span> {analytic.log_sources}</div>
              {/if}
              {#if analytic.pseudocode}
                <pre class="car-pseudocode">{analytic.pseudocode}</pre>
              {/if}
            </div>
          {/each}
        </div>
      </section>
    {/if}
  </div>

  <!-- AI Copilot panel -->
  <div class="panel copilot-panel">
    <div class="panel-header">
      <h2>AI Copilot</h2>
      <span class="model-label">foundation-sec:8b</span>
    </div>
    <div class="chat-history">
      {#each chatMessages as msg (msg.id)}
        <div class="message {msg.role}">
          {#if msg.role === 'assistant'}
            <div class="ai-advisory-banner" aria-label="AI Advisory — not a verified fact">
              <span class="advisory-label">AI Advisory</span>
              <span
                class="confidence-badge confidence-{confidenceLevel(msg.confidence)}"
                title="AI confidence: {msg.confidence !== undefined ? (msg.confidence * 100).toFixed(0) + '%' : 'unknown'}"
              >
                {#if msg.confidence !== undefined}
                  {confidenceLevel(msg.confidence) === 'high' ? 'High' :
                   confidenceLevel(msg.confidence) === 'medium' ? 'Medium' : 'Low'} confidence
                {:else}
                  Confidence unknown
                {/if}
              </span>
            </div>
            <p class="ai-content">{msg.content}</p>
            {#if msg.is_grounded === false || (msg.grounding_event_ids !== undefined && msg.grounding_event_ids.length === 0)}
              <div class="ungrounded-warning" aria-label="Ungrounded response warning">
                <span class="warning-icon">&#9888;</span>
                <span>Response not grounded in retrieved evidence</span>
              </div>
            {/if}
            {#if msg.grounding_event_ids && msg.grounding_event_ids.length > 0}
              <div class="citation-list" aria-label="Grounding sources">
                <span class="citation-label">Sources:</span>
                {#each msg.grounding_event_ids as evtId}
                  <span class="citation-tag">{evtId}</span>
                {/each}
              </div>
            {/if}
          {:else}
            <span class="role-label">You</span>
            <p>{msg.content}</p>
          {/if}
        </div>
      {/each}
      {#if isStreaming && streamingContent}
        <div class="message assistant streaming">
          <div class="ai-advisory-banner" aria-label="AI Advisory — not a verified fact">
            <span class="advisory-label">AI Advisory</span>
            <span class="confidence-badge confidence-unknown">Generating...</span>
          </div>
          <p class="ai-content">{streamingContent}<span class="cursor">&#x258C;</span></p>
        </div>
      {/if}
    </div>
    <div class="chat-input-area">
      <textarea
        bind:value={inputText}
        placeholder="Ask the AI Copilot about this investigation..."
        rows="2"
        onkeydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
        disabled={isStreaming}
      ></textarea>
      <div class="chat-actions">
        {#if isStreaming}
          <button class="btn-danger" onclick={stopStream}>Stop</button>
        {:else}
          <button class="btn-primary" onclick={sendMessage} disabled={!inputText.trim()}>Send</button>
        {/if}
      </div>
    </div>
  </div>

</div>

<style>
.investigation-view {
  display: grid;
  grid-template-columns: 55% 45%;
  gap: 1rem;
  height: calc(100vh - 60px);
  padding: 1rem;
  box-sizing: border-box;
}
.panel {
  background: var(--surface, #1a2236);
  border: 1px solid var(--border, #2d3a52);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border, #2d3a52);
}
.panel-header h2 { margin: 0; font-size: 1rem; font-weight: 600; }
.header-actions { display: flex; gap: 0.5rem; align-items: center; }
.model-label { font-size: 0.75rem; color: var(--muted, #8899aa); }

/* Timeline */
.timeline { overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0; }
.timeline-entry { display: grid; grid-template-columns: 12px 1px 1fr; gap: 0 0.75rem; padding-bottom: 1rem; }
.timeline-dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 4px; flex-shrink: 0; }
.timeline-line { background: var(--border, #2d3a52); }
.timeline-content { padding-bottom: 0.25rem; }
.severity-critical .timeline-dot { background: #ef4444; }
.severity-high .timeline-dot     { background: #f97316; }
.severity-medium .timeline-dot   { background: #eab308; }
.severity-low .timeline-dot      { background: #22c55e; }
.severity-info .timeline-dot     { background: #3b82f6; }
.time { font-size: 0.72rem; color: var(--muted, #8899aa); margin-right: 0.4rem; }
.badge { font-size: 0.68rem; padding: 1px 6px; border-radius: 4px; margin-right: 0.3rem;
         background: var(--surface2, #253048); color: var(--muted, #8899aa); }
.badge.mitre  { background: #1e3a5f; color: #60a5fa; }
.badge.tactic { background: #1e2d1e; color: #4ade80; }
.badge.type-detection { background: #3d1a1a; color: #f87171; }
.item-title { margin: 0.3rem 0 0.2rem; font-size: 0.85rem; }
.entity-badge { font-size: 0.7rem; padding: 1px 5px; border-radius: 3px;
                background: var(--surface2, #253048); color: var(--fg, #c9d1e0);
                margin-right: 0.2rem; }

/* AI Advisory banner (P22-T05) — non-dismissable */
.ai-advisory-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fef3c7;
  border-left: 3px solid #f59e0b;
  padding: 4px 8px;
  border-radius: 2px 4px 4px 2px;
  margin-bottom: 6px;
  font-size: 0.75rem;
}
.advisory-label {
  font-weight: 700;
  color: #92400e;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
/* Confidence badge */
.confidence-badge {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}
.confidence-high    { background: #16a34a; color: #fff; }
.confidence-medium  { background: #d97706; color: #fff; }
.confidence-low     { background: #dc2626; color: #fff; }
.confidence-unknown { background: #6b7280; color: #fff; }
/* AI response text styling — distinct from human messages */
.ai-content {
  font-style: italic;
  color: var(--text-muted, #6b7280);
  margin: 0;
  line-height: 1.6;
}

.ungrounded-warning {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: #b45309;
  background: #fef3c7;
  border: 1px solid #f59e0b;
  border-radius: 4px;
  padding: 0.25rem 0.5rem;
  margin-top: 0.25rem;
}
.warning-icon {
  font-size: 0.9rem;
}
.citation-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.3rem;
  margin-top: 0.3rem;
  font-size: 0.72rem;
}
.citation-label {
  color: #6b7280;
  font-weight: 500;
}
.citation-tag {
  background: #e0f2fe;
  color: #0369a1;
  border: 1px solid #bae6fd;
  border-radius: 3px;
  padding: 0.1rem 0.35rem;
  font-family: monospace;
  font-size: 0.7rem;
}

/* Copilot */
.copilot-panel { display: flex; flex-direction: column; }
.chat-history { flex: 1; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0.75rem; }
.message { max-width: 85%; padding: 0.5rem 0.75rem; border-radius: 8px; }
.message.user { align-self: flex-end; background: #1e3a5f; }
.message.assistant { align-self: flex-start; background: var(--surface2, #253048); }
.message.streaming { opacity: 0.9; }
.role-label { font-size: 0.68rem; color: var(--muted, #8899aa); display: block; margin-bottom: 0.2rem; }
.message p { margin: 0; font-size: 0.85rem; white-space: pre-wrap; }
.cursor { animation: blink 1s step-start infinite; }
@keyframes blink { 50% { opacity: 0; } }
.chat-input-area { padding: 0.75rem; border-top: 1px solid var(--border, #2d3a52); display: flex; flex-direction: column; gap: 0.5rem; }
textarea { width: 100%; background: var(--surface2, #253048); border: 1px solid var(--border, #2d3a52);
           border-radius: 6px; color: var(--fg, #c9d1e0); padding: 0.5rem; font-size: 0.85rem; resize: none; box-sizing: border-box; }
.chat-actions { display: flex; justify-content: flex-end; }
.btn-primary { background: #1e3a5f; color: #60a5fa; border: 1px solid #2563eb; padding: 0.4rem 1rem; border-radius: 5px; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; cursor: default; }
.btn-secondary { background: transparent; color: var(--muted, #8899aa); border: 1px solid var(--border, #2d3a52); padding: 0.3rem 0.75rem; border-radius: 5px; cursor: pointer; font-size: 0.8rem; }
.btn-danger { background: #3d1a1a; color: #f87171; border: 1px solid #dc2626; padding: 0.4rem 1rem; border-radius: 5px; cursor: pointer; }
.btn-run-playbook { color: #4ade80; border-color: rgba(74,222,128,0.35); }
.btn-run-playbook:disabled { opacity: 0.4; cursor: not-allowed; }
.muted { color: var(--muted, #8899aa); font-size: 0.85rem; padding: 1rem; }
.error { color: #f87171; font-size: 0.85rem; padding: 1rem; }

/* Phase 39: CAR Analytics section */
.inv-section { margin: 16px; margin-top: 0; }
.car-analytics-section { padding-top: 8px; border-top: 1px solid var(--border, #2d3a52); }
.inv-section-title { font-size: 0.9rem; font-weight: 600; color: rgba(255,255,255,0.87); margin: 0 0 4px; }
.inv-section-subtitle { font-size: 0.75rem; color: rgba(255,255,255,0.4); margin: 0 0 12px; }
.car-panel { display: flex; flex-direction: column; gap: 12px; }
.car-card { border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 12px; background: rgba(255,255,255,0.02); }
.car-card-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.car-id-badge { font-family: monospace; font-size: 0.75rem; background: rgba(99,102,241,0.15); color: #a5b4fc; padding: 2px 6px; border-radius: 4px; }
.car-title { font-weight: 500; font-size: 0.875rem; color: rgba(255,255,255,0.87); flex: 1; }
.car-coverage { font-size: 0.7rem; padding: 2px 6px; border-radius: 10px; text-transform: uppercase; letter-spacing: 0.05em; }
.coverage-low { background: rgba(245,158,11,0.15); color: #fbbf24; }
.coverage-moderate { background: rgba(59,130,246,0.15); color: #60a5fa; }
.coverage-high { background: rgba(34,197,94,0.15); color: #4ade80; }
.car-link { font-size: 0.75rem; color: rgba(99,130,246,0.8); text-decoration: none; }
.car-link:hover { text-decoration: underline; }
.car-description { font-size: 0.8rem; color: rgba(255,255,255,0.65); margin: 0 0 8px; line-height: 1.5; }
.car-meta { font-size: 0.78rem; color: rgba(255,255,255,0.55); margin-bottom: 4px; }
.car-label { color: rgba(255,255,255,0.45); font-weight: 500; }
.car-pseudocode { font-family: monospace; font-size: 0.75rem; background: rgba(0,0,0,0.4); color: #a5b4fc; padding: 10px; border-radius: 4px; overflow-x: auto; white-space: pre; margin: 8px 0 0; max-height: 200px; overflow-y: auto; }
</style>
