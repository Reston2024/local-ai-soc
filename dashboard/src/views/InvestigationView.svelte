<script lang="ts">
  import { api } from '../lib/api.ts'
  import type { TimelineItem, ChatHistoryMessage } from '../lib/api.ts'

  let {
    investigationId = '',
    onOpenInGraph = undefined,
    onRunPlaybook = undefined,
  }: {
    investigationId?: string
    onOpenInGraph?: (entityId: string) => void
    onRunPlaybook?: (investigationId: string) => void
  } = $props()

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

  // Load timeline + chat history when investigationId changes
  $effect(() => {
    if (!investigationId) return
    loadTimeline()
    loadChatHistory()
  })

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
          <span class="role-label">{msg.role === 'user' ? 'You' : 'Copilot'}</span>
          {#if msg.role === 'assistant'}
            <div class="ai-advisory-inline" aria-label="AI Advisory">
              <span class="confidence-badge confidence-{confidenceLevel(msg.confidence)}"
                    title="AI confidence: {msg.confidence !== undefined ? (msg.confidence * 100).toFixed(0) + '%' : 'unknown'}">
                {confidenceLevel(msg.confidence) === 'high' ? 'High confidence' :
                 confidenceLevel(msg.confidence) === 'medium' ? 'Medium confidence' : 'Low confidence'}
              </span>
            </div>
          {/if}
          <p>{msg.content}</p>
        </div>
      {/each}
      {#if isStreaming && streamingContent}
        <div class="message assistant streaming">
          <span class="role-label">Copilot</span>
          <p>{streamingContent}<span class="cursor">&#x258C;</span></p>
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

/* Confidence badge */
.confidence-badge {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  margin-bottom: 4px;
}
.confidence-high    { background: #16a34a; color: #fff; }
.confidence-medium  { background: #d97706; color: #fff; }
.confidence-low     { background: #dc2626; color: #fff; }
.confidence-unknown { background: #6b7280; color: #fff; }
.ai-advisory-inline { margin-bottom: 4px; }

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
</style>
