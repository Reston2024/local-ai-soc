<script lang="ts">
  import { api } from '../lib/api.ts'
  import type { TimelineItem, ChatHistoryMessage, CARAnalytic, SimilarCase, AgentStep, AgentVerdict } from '../lib/api.ts'


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
  let investigationResult = $state<{ car_analytics?: CARAnalytic[]; detection?: { attack_technique?: string; rule_id?: string; rule_name?: string } } | null>(null)

  // Phase 44: similar confirmed cases
  let similarCases = $state<SimilarCase[]>([])

  // Phase 45: Agent tab state
  let activeTab = $state<'summary' | 'agent'>('summary')
  let agentSteps = $state<AgentStep[]>([])
  let agentReasoningChunks = $state<string[]>([])
  let agentVerdict = $state<AgentVerdict | null>(null)
  let agentRunning = $state(false)
  let agentCallCount = $state(0)
  let agentLimitReason = $state<string | null>(null)
  let agentError = $state<string | null>(null)
  let agentExpandedSteps = $state<Set<number>>(new Set())
  let agentAbortController: AbortController | null = null

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

  // Phase 44: load similar confirmed cases when investigationId changes
  $effect(() => {
    if (!investigationId) return
    const det = investigationResult?.detection
    api.feedback.similar(
      investigationId,
      det?.rule_id,
      det?.rule_name
    ).then(r => {
      similarCases = r.cases ?? []
    }).catch(() => { similarCases = [] })
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

  // Phase 45: Agent helpers
  function toolIcon(name: string): string {
    const icons: Record<string, string> = {
      query_events: '🔍',
      get_entity_profile: '👤',
      enrich_ip: '🌐',
      search_sigma_matches: '⚡',
      get_graph_neighbors: '🕸️',
      search_similar_incidents: '📋',
    }
    return icons[name] ?? '🔧'
  }

  function toggleStep(callNumber: number) {
    const next = new Set(agentExpandedSteps)
    if (next.has(callNumber)) next.delete(callNumber)
    else next.add(callNumber)
    agentExpandedSteps = next
  }

  async function startAgent() {
    if (!investigationId) return

    // Check cache
    const cached = agentCache.get(investigationId)
    if (cached) {
      agentSteps = cached.steps
      agentReasoningChunks = cached.reasoningChunks
      agentVerdict = cached.verdict
      agentLimitReason = cached.limitReason
      agentError = cached.error
      agentCallCount = cached.steps.length
      return
    }

    // Fresh run
    agentRunning = true
    agentSteps = []
    agentReasoningChunks = []
    agentVerdict = null
    agentLimitReason = null
    agentError = null
    agentCallCount = 0

    agentAbortController = new AbortController()

    try {
      await api.investigations.runAgentic(
        investigationId,
        (step) => {
          agentSteps = [...agentSteps, step]
          agentCallCount = step.call_number
        },
        (text) => {
          agentReasoningChunks = [...agentReasoningChunks, text]
        },
        (verdict) => {
          agentVerdict = verdict
        },
        (reason) => {
          agentLimitReason = reason
        },
        () => {
          agentRunning = false
          agentCache.set(investigationId, {
            steps: agentSteps,
            reasoningChunks: agentReasoningChunks,
            verdict: agentVerdict,
            limitReason: agentLimitReason,
            error: agentError,
          })
        },
        (message) => {
          agentError = message
          agentRunning = false
        },
        agentAbortController.signal,
      )
    } catch (err) {
      agentError = err instanceof Error ? err.message : 'Unknown error'
      agentRunning = false
    }
  }

  function retryAgent() {
    if (investigationId) agentCache.delete(investigationId)
    agentVerdict = null
    agentError = null
    agentLimitReason = null
    startAgent()
  }

  async function confirmVerdict(verdict: 'TP' | 'FP') {
    if (!investigationId) return
    try {
      await api.feedback.submit({ detection_id: investigationId, verdict })
    } catch { /* silent on error */ }
  }
</script>

<script module lang="ts">
  // Phase 45: module-level cache — keyed by detection_id, persists across mounts
  import type { AgentRunResult as _AgentRunResult } from '../lib/api.ts'
  const agentCache = new Map<string, _AgentRunResult>()
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

    {#if similarCases.length > 0}
      <section class="inv-section similar-cases-section">
        <h3 class="inv-section-title">Similar Confirmed Cases</h3>
        <div class="similar-cases-list">
          {#each similarCases as c (c.detection_id)}
            <div class="similar-case-card">
              <span class="verdict-badge verdict-{c.verdict.toLowerCase()}">{c.verdict}</span>
              <span class="similar-rule-name">{c.rule_name ?? 'Unknown rule'}</span>
              <span class="similar-score">{c.similarity_pct}% similar</span>
              {#if c.summary}
                <p class="similar-summary">{c.summary}</p>
              {/if}
            </div>
          {/each}
        </div>
      </section>
    {/if}
  </div>

  <!-- AI Copilot / Agent panel -->
  <div class="panel copilot-panel">
    <div class="panel-header">
      <h2>AI Copilot</h2>
      <span class="model-label">foundation-sec:8b</span>
    </div>

    <!-- Phase 45: Tab selector -->
    <div class="tab-header">
      <button
        class="tab-btn"
        class:active={activeTab === 'summary'}
        onclick={() => activeTab = 'summary'}
      >Summary</button>
      <button
        class="tab-btn"
        class:active={activeTab === 'agent'}
        onclick={() => { activeTab = 'agent'; if (!agentRunning && !agentVerdict && agentSteps.length === 0 && !agentError) startAgent() }}
      >Agent</button>
    </div>

    {#if activeTab === 'summary'}
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

    {:else}
    <!-- AGENT TAB -->
    <div class="agent-panel">

      <!-- Header with call counter during run -->
      <div class="agent-header">
        <span class="agent-title">Agentic Investigation</span>
        {#if agentRunning}
          <span class="call-counter">{agentCallCount}/10 calls used</span>
        {/if}
      </div>

      <!-- Empty state (before first run) -->
      {#if !agentRunning && agentSteps.length === 0 && !agentVerdict && !agentError && !agentLimitReason}
        <div class="agent-empty">
          <p class="agent-empty-desc">
            The AI agent will query events, enrich IPs, and reason step-by-step to a verdict.
          </p>
          <button class="btn-run-agent" onclick={startAgent}>
            Run agentic investigation ▶
          </button>
        </div>

      {:else}
        <!-- Trace cards + streaming reasoning -->
        <div class="agent-trace">

          <!-- Waiting spinner — shown until first tool call or reasoning text arrives -->
          {#if agentRunning && agentSteps.length === 0 && agentReasoningChunks.length === 0}
            <div class="agent-thinking">
              <div class="thinking-spinner"></div>
              <div class="thinking-text">
                <span class="thinking-label">Agent is working…</span>
                <span class="thinking-sub">Querying evidence and reasoning about the detection</span>
              </div>
            </div>
          {/if}

          {#each agentSteps as step, i (step.call_number)}
            <!-- Collapsible trace card -->
            <div class="trace-card">
              <button
                class="trace-card-header"
                onclick={() => toggleStep(step.call_number)}
              >
                <span class="tool-icon">{toolIcon(step.tool_name)}</span>
                <span class="tool-name">{step.tool_name}</span>
                <span class="tool-summary">{step.result.slice(0, 80)}{step.result.length > 80 ? '…' : ''}</span>
                <span class="chevron">{agentExpandedSteps.has(step.call_number) ? '▾' : '▸'}</span>
              </button>
              {#if agentExpandedSteps.has(step.call_number)}
                <div class="trace-card-body">
                  <div class="trace-args">
                    <strong>Arguments:</strong>
                    <pre>{JSON.stringify(step.arguments, null, 2)}</pre>
                  </div>
                  <div class="trace-result">
                    <strong>Result:</strong>
                    <p>{step.result}</p>
                  </div>
                </div>
              {/if}
            </div>
            <!-- Reasoning text after this card -->
            {#if agentReasoningChunks[i]}
              <div class="reasoning-text">{agentReasoningChunks[i]}</div>
            {/if}
          {/each}

          <!-- Live reasoning text (after last card, while running) -->
          {#if agentRunning && agentReasoningChunks.length > agentSteps.length}
            <div class="reasoning-text reasoning-live">
              {agentReasoningChunks[agentReasoningChunks.length - 1]}
            </div>
          {/if}
        </div>

        <!-- Limit/timeout warning banner -->
        {#if agentLimitReason && !agentRunning}
          <div class="agent-limit-banner">
            <span>Agent stopped — hit {agentLimitReason === 'timeout' ? 'time limit' : '10-call limit'}.
            Partial investigation shown.</span>
            <button class="btn-retry" onclick={retryAgent}>Re-run ↺</button>
          </div>
        {/if}

        <!-- Error banner with retry -->
        {#if agentError && !agentRunning}
          <div class="agent-error-card">
            <span>{agentError}</span>
            <button class="btn-retry" onclick={retryAgent}>Retry ↺</button>
          </div>
        {/if}

        <!-- Final Verdict section — visible once complete -->
        {#if agentVerdict && !agentRunning}
          <div class="verdict-section">
            <div class="verdict-header">
              <span class="verdict-badge-agent" class:tp={agentVerdict.verdict === 'TP'} class:fp={agentVerdict.verdict === 'FP'}>
                {agentVerdict.verdict}
              </span>
              <span class="verdict-confidence">{agentVerdict.confidence}% confident</span>
            </div>
            <p class="verdict-narrative">{agentVerdict.narrative}</p>
            <div class="verdict-actions">
              <button class="btn-confirm-tp" onclick={() => confirmVerdict('TP')}>✓ Confirm TP</button>
              <button class="btn-mark-fp" onclick={() => confirmVerdict('FP')}>✗ Mark FP</button>
            </div>
          </div>
        {/if}
      {/if}

    </div>
    {/if}

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

/* Phase 44: Similar Confirmed Cases */
.similar-cases-section { margin-top: 16px; }
.similar-cases-list { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.similar-case-card { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: rgba(255,255,255,0.04); border-radius: 6px; border: 1px solid rgba(255,255,255,0.08); flex-wrap: wrap; }
.similar-rule-name { font-size: 13px; color: rgba(255,255,255,0.8); flex: 1; }
.similar-score { font-size: 12px; color: rgba(255,255,255,0.45); white-space: nowrap; }
.similar-summary { font-size: 12px; color: rgba(255,255,255,0.5); margin: 4px 0 0; width: 100%; }
.verdict-badge { display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.verdict-tp { background: rgba(34,197,94,0.2); color: #22c55e; }
.verdict-fp { background: rgba(239,68,68,0.2); color: #ef4444; }

/* Phase 45: Tab header */
.tab-header { display: flex; gap: 0; border-bottom: 1px solid #2a2a3a; margin: 0; padding: 0 0.75rem; }
.tab-btn { background: none; border: none; color: rgba(255,255,255,0.48); padding: 0.5rem 1rem; cursor: pointer; font-size: 0.85rem; border-bottom: 2px solid transparent; margin-bottom: -1px; }
.tab-btn.active { color: #fff; border-bottom-color: #6366f1; }
.tab-btn:hover:not(.active) { color: rgba(255,255,255,0.72); }

/* Phase 45: Agent panel */
.agent-panel { display: flex; flex-direction: column; gap: 0.75rem; padding: 0.75rem; flex: 1; overflow-y: auto; }
.agent-header { display: flex; justify-content: space-between; align-items: center; }
.agent-title { font-size: 0.9rem; font-weight: 600; color: rgba(255,255,255,0.9); }
.call-counter { font-size: 0.75rem; color: rgba(255,255,255,0.48); font-variant-numeric: tabular-nums; }
.agent-empty { display: flex; flex-direction: column; align-items: center; gap: 1rem; padding: 2rem; text-align: center; }
.agent-empty-desc { color: rgba(255,255,255,0.48); font-size: 0.85rem; max-width: 320px; }
.btn-run-agent { background: #6366f1; color: #fff; border: none; padding: 0.5rem 1.25rem; border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
.btn-run-agent:hover { background: #4f46e5; }
.agent-trace { display: flex; flex-direction: column; gap: 0.5rem; }
.trace-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; overflow: hidden; }
.trace-card-header { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.75rem; width: 100%; background: none; border: none; color: rgba(255,255,255,0.8); cursor: pointer; text-align: left; font-size: 0.8rem; }
.tool-icon { font-size: 1rem; }
.tool-name { font-weight: 600; color: #a5b4fc; min-width: 140px; }
.tool-summary { flex: 1; color: rgba(255,255,255,0.48); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chevron { color: rgba(255,255,255,0.4); }
.trace-card-body { padding: 0.75rem; border-top: 1px solid rgba(255,255,255,0.06); font-size: 0.78rem; display: flex; flex-direction: column; gap: 0.5rem; }
.trace-args pre { background: rgba(0,0,0,0.3); padding: 0.4rem; border-radius: 4px; font-size: 0.72rem; color: rgba(255,255,255,0.7); overflow-x: auto; margin: 0.25rem 0 0; }
.trace-result p { color: rgba(255,255,255,0.8); margin: 0.25rem 0 0; white-space: pre-wrap; }
.reasoning-text { font-size: 0.8rem; color: rgba(255,255,255,0.55); font-style: italic; padding: 0.25rem 0.5rem; border-left: 2px solid #6366f1; margin: 0.25rem 0; }
.reasoning-live { animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { opacity: 0.6 } 50% { opacity: 1 } }
.agent-limit-banner { background: rgba(234,179,8,0.12); border: 1px solid rgba(234,179,8,0.3); border-radius: 6px; padding: 0.5rem 0.75rem; color: #fbbf24; font-size: 0.8rem; display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
.agent-error-card { background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2); border-radius: 6px; padding: 0.5rem 0.75rem; display: flex; justify-content: space-between; align-items: center; color: #f87171; font-size: 0.8rem; }
.btn-retry { background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3); color: #f87171; padding: 0.25rem 0.6rem; border-radius: 4px; cursor: pointer; font-size: 0.75rem; }
.verdict-section { margin-top: auto; background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.2); border-radius: 8px; padding: 1rem; display: flex; flex-direction: column; gap: 0.5rem; }
.verdict-header { display: flex; align-items: center; gap: 0.75rem; }
.verdict-badge-agent { font-size: 1rem; font-weight: 700; padding: 0.2rem 0.6rem; border-radius: 4px; }
.verdict-badge-agent.tp { background: rgba(34,197,94,0.15); color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }
.verdict-badge-agent.fp { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
.verdict-confidence { color: rgba(255,255,255,0.55); font-size: 0.8rem; }
.verdict-narrative { color: rgba(255,255,255,0.8); font-size: 0.82rem; margin: 0; line-height: 1.5; }
.verdict-actions { display: flex; gap: 0.5rem; }
.btn-confirm-tp { background: rgba(34,197,94,0.15); border: 1px solid rgba(34,197,94,0.3); color: #4ade80; padding: 0.35rem 0.75rem; border-radius: 5px; cursor: pointer; font-size: 0.8rem; }
.btn-confirm-tp:hover { background: rgba(34,197,94,0.25); }
.btn-mark-fp { background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.25); color: #f87171; padding: 0.35rem 0.75rem; border-radius: 5px; cursor: pointer; font-size: 0.8rem; }
.btn-mark-fp:hover { background: rgba(239,68,68,0.22); }

/* Phase 45: Waiting / thinking indicator */
.agent-thinking {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1.25rem;
  background: rgba(99,102,241,0.06);
  border: 1px solid rgba(99,102,241,0.15);
  border-radius: 8px;
  margin: 0.25rem 0;
}
.thinking-spinner {
  width: 22px;
  height: 22px;
  border: 3px solid rgba(99,102,241,0.25);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
.thinking-text {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.thinking-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: rgba(255,255,255,0.85);
}
.thinking-sub {
  font-size: 0.75rem;
  color: rgba(255,255,255,0.42);
}
</style>
