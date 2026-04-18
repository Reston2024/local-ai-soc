<script lang="ts">
  /**
   * CoPilot — persistent right rail (320px) for AI-assisted analysis.
   * Provides /triage, /graph, /playbook, /report slash commands
   * and a streaming chat interface backed by the query API.
   */
  import { api } from '../lib/api.ts'

  interface Props {
    open:              boolean
    onClose:           () => void
    investigationId?:  string
    onNavigate?:       (view: string) => void
  }

  let {
    open,
    onClose,
    investigationId = '',
    onNavigate,
  }: Props = $props()

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  let inputValue  = $state('')
  let messages    = $state<Array<{ role: 'user' | 'assistant'; text: string; ts: string }>>([])
  let streaming   = $state(false)
  let inputEl: HTMLTextAreaElement | null = $state(null)

  const SLASH_CMDS = [
    { cmd: '/triage',   desc: 'AI triage of all open detections',   icon: '⚡' },
    { cmd: '/graph',    desc: 'Open the attack graph view',          icon: '⬡' },
    { cmd: '/playbook', desc: 'Open playbooks for current case',     icon: '📋' },
    { cmd: '/report',   desc: 'Generate an incident report',         icon: '📄' },
    { cmd: '/help',     desc: 'List available commands',             icon: '❓' },
  ]

  const showSlashMenu = $derived(inputValue.startsWith('/') && !inputValue.includes(' '))
  const slashFiltered = $derived(
    SLASH_CMDS.filter(c => c.cmd.startsWith(inputValue.toLowerCase()))
  )

  // ---------------------------------------------------------------------------
  // Send message
  // ---------------------------------------------------------------------------
  async function send() {
    const text = inputValue.trim()
    if (!text || streaming) return
    inputValue = ''

    // Slash command dispatch
    if (text.startsWith('/')) {
      const cmd = text.split(' ')[0].toLowerCase()
      switch (cmd) {
        case '/triage':
          onNavigate?.('overview')
          addMsg('assistant', 'Navigated to Overview. Click **Run AI Triage** to start analysis.')
          return
        case '/graph':
          onNavigate?.('graph')
          addMsg('assistant', 'Attack Graph opened.')
          return
        case '/playbook':
          onNavigate?.('playbooks')
          addMsg('assistant', 'Playbooks view opened.')
          return
        case '/report':
          onNavigate?.('reports')
          addMsg('assistant', 'Reports view opened.')
          return
        case '/help':
          addMsg('assistant', SLASH_CMDS.map(c => `**${c.cmd}** — ${c.desc}`).join('\n'))
          return
        default:
          addMsg('assistant', `Unknown command: \`${cmd}\`. Type **/help** for a list.`)
          return
      }
    }

    // Free-text → streaming query
    addMsg('user', text)
    streaming = true
    let reply = ''
    const msgIdx = messages.length
    messages = [...messages, { role: 'assistant', text: '…', ts: ts() }]

    try {
      await api.query.ask(
        investigationId ? `[Investigation context: ${investigationId}]\n${text}` : text,
      ).then(fullText => {
        reply = fullText
      })
    } catch (err: any) {
      reply = `Error: ${err?.message ?? 'query failed'}`
    }

    messages = messages.map((m, i) => i === msgIdx ? { ...m, text: reply } : m)
    streaming = false
    scrollToBottom()
  }

  function addMsg(role: 'user' | 'assistant', text: string) {
    messages = [...messages, { role, text, ts: ts() }]
    scrollToBottom()
  }

  function ts() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
  }

  function scrollToBottom() {
    requestAnimationFrame(() => {
      const el = document.querySelector('.copilot-messages')
      if (el) el.scrollTop = el.scrollHeight
    })
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
    if (e.key === 'Escape') {
      onClose()
    }
  }

  function fillSlash(cmd: string) {
    inputValue = cmd + ' '
    inputEl?.focus()
  }

  // Focus input when opened
  $effect(() => {
    if (open) requestAnimationFrame(() => inputEl?.focus())
  })
</script>

{#if open}
  <aside class="copilot-rail">
    <!-- Header -->
    <div class="cp-header">
      <div class="cp-title">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
          <path d="M8 2a4 4 0 0 1 4 4c0 2-1 3.5-2.5 4.5L8 14l-1.5-3.5C5 9.5 4 8 4 6a4 4 0 0 1 4-4z"
            stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
          <circle cx="8" cy="6" r="1.3" fill="currentColor"/>
        </svg>
        AI Co-Pilot
        {#if investigationId}
          <span class="cp-context-badge">case</span>
        {/if}
      </div>
      <button class="cp-close-btn" onclick={onClose} title="Close (Esc)">✕</button>
    </div>

    <!-- Messages -->
    <div class="copilot-messages">
      {#if messages.length === 0}
        <div class="cp-empty">
          <p class="cp-empty-title">How can I help?</p>
          <p class="cp-empty-sub">Ask about detections, IOCs, attack techniques, or use a slash command.</p>
          <div class="cp-quick-cmds">
            {#each SLASH_CMDS.slice(0, 4) as sc}
              <button class="cp-quick-btn" onclick={() => fillSlash(sc.cmd)}>
                <span class="cp-quick-icon">{sc.icon}</span>
                <span>{sc.cmd}</span>
              </button>
            {/each}
          </div>
        </div>
      {:else}
        {#each messages as msg}
          <div class="cp-msg" class:user={msg.role === 'user'} class:assistant={msg.role === 'assistant'}>
            <div class="cp-msg-bubble">
              <!-- Simple markdown-ish rendering: bold (**text**), code (`text`) -->
              <!-- For now render as plain text — full markdown would add weight -->
              <span class="cp-msg-text">{msg.text}</span>
            </div>
            <span class="cp-msg-ts">{msg.ts}</span>
          </div>
        {/each}
      {/if}
    </div>

    <!-- Slash suggestion menu -->
    {#if showSlashMenu && slashFiltered.length > 0}
      <div class="cp-slash-menu">
        {#each slashFiltered as sc}
          <button class="cp-slash-item" onclick={() => fillSlash(sc.cmd)}>
            <span class="cp-slash-cmd">{sc.cmd}</span>
            <span class="cp-slash-desc">{sc.desc}</span>
          </button>
        {/each}
      </div>
    {/if}

    <!-- Input -->
    <div class="cp-input-row">
      <textarea
        bind:this={inputEl}
        bind:value={inputValue}
        class="cp-input"
        placeholder="Ask anything or type / for commands…"
        rows="2"
        disabled={streaming}
        onkeydown={handleKeyDown}
      ></textarea>
      <button
        class="cp-send-btn"
        onclick={send}
        disabled={!inputValue.trim() || streaming}
        title="Send (Enter)"
      >
        {#if streaming}
          <span class="cp-send-spinner"></span>
        {:else}
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M2 8L14 2L8 14L7 9L2 8Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          </svg>
        {/if}
      </button>
    </div>
  </aside>
{/if}

<style>
  /* ── Rail ── */
  .copilot-rail {
    width: 320px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
    border-left: 1px solid var(--border);
    overflow: hidden;
  }

  /* ── Header ── */
  .cp-header {
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 14px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .cp-title {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 13px;
    font-weight: 600;
    color: rgba(255,255,255,0.8);
  }

  .cp-context-badge {
    font-size: 9.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    background: rgba(0,212,255,0.12);
    color: #00d4ff;
    border: 1px solid rgba(0,212,255,0.25);
    border-radius: 3px;
    padding: 1px 5px;
  }

  .cp-close-btn {
    background: none;
    border: none;
    color: rgba(255,255,255,0.28);
    font-size: 12px;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: color 0.12s, background 0.12s;
  }

  .cp-close-btn:hover {
    color: rgba(255,255,255,0.7);
    background: rgba(255,255,255,0.06);
  }

  /* ── Messages ── */
  .copilot-messages {
    flex: 1;
    overflow-y: auto;
    padding: 12px 12px 8px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .copilot-messages::-webkit-scrollbar { width: 3px; }
  .copilot-messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  /* ── Empty state ── */
  .cp-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 8px;
    gap: 8px;
    text-align: center;
  }

  .cp-empty-title {
    font-size: 14px;
    font-weight: 600;
    color: rgba(255,255,255,0.65);
  }

  .cp-empty-sub {
    font-size: 12px;
    color: rgba(255,255,255,0.28);
    line-height: 1.5;
  }

  .cp-quick-cmds {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    width: 100%;
    margin-top: 8px;
  }

  .cp-quick-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 7px 10px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 7px;
    color: rgba(255,255,255,0.5);
    font-size: 12px;
    font-family: var(--font-mono);
    cursor: pointer;
    transition: background 0.1s, border-color 0.1s;
  }

  .cp-quick-btn:hover {
    background: rgba(255,255,255,0.08);
    border-color: rgba(255,255,255,0.14);
    color: rgba(255,255,255,0.8);
  }

  .cp-quick-icon {
    font-size: 11px;
  }

  /* ── Message bubble ── */
  .cp-msg {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .cp-msg.user {
    align-items: flex-end;
  }

  .cp-msg.assistant {
    align-items: flex-start;
  }

  .cp-msg-bubble {
    max-width: 90%;
    padding: 8px 11px;
    border-radius: 10px;
    font-size: 12.5px;
    line-height: 1.55;
  }

  .cp-msg.user .cp-msg-bubble {
    background: rgba(0,212,255,0.1);
    border: 1px solid rgba(0,212,255,0.2);
    color: rgba(255,255,255,0.85);
    border-bottom-right-radius: 3px;
  }

  .cp-msg.assistant .cp-msg-bubble {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    color: rgba(255,255,255,0.75);
    border-bottom-left-radius: 3px;
    white-space: pre-wrap;
  }

  .cp-msg-text {
    display: block;
  }

  .cp-msg-ts {
    font-size: 10px;
    color: rgba(255,255,255,0.18);
    font-family: var(--font-mono);
  }

  /* ── Slash menu ── */
  .cp-slash-menu {
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    background: var(--bg-tertiary);
    flex-shrink: 0;
  }

  .cp-slash-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 14px;
    background: none;
    border: none;
    cursor: pointer;
    text-align: left;
    transition: background 0.08s;
  }

  .cp-slash-item:hover {
    background: rgba(255,255,255,0.05);
  }

  .cp-slash-cmd {
    font-size: 12.5px;
    font-family: var(--font-mono);
    color: #00d4ff;
    flex-shrink: 0;
    min-width: 80px;
  }

  .cp-slash-desc {
    font-size: 11.5px;
    color: rgba(255,255,255,0.35);
  }

  /* ── Input row ── */
  .cp-input-row {
    display: flex;
    align-items: flex-end;
    gap: 8px;
    padding: 10px 12px;
    border-top: 1px solid var(--border);
    flex-shrink: 0;
  }

  .cp-input {
    flex: 1;
    resize: none;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 12.5px;
    font-family: var(--font-sans);
    padding: 7px 10px;
    outline: none;
    line-height: 1.5;
    transition: border-color 0.15s, box-shadow 0.15s;
    min-height: 44px;
  }

  .cp-input:focus {
    border-color: rgba(0,212,255,0.3);
    box-shadow: 0 0 0 3px rgba(0,212,255,0.07);
  }

  .cp-input:disabled { opacity: 0.5; }

  .cp-input::placeholder { color: rgba(255,255,255,0.2); }

  .cp-send-btn {
    width: 34px;
    height: 34px;
    flex-shrink: 0;
    background: var(--accent-cyan);
    border: none;
    border-radius: 8px;
    color: #070c1b;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: filter 0.12s;
  }

  .cp-send-btn:hover:not(:disabled) { filter: brightness(1.15); }
  .cp-send-btn:disabled { opacity: 0.35; cursor: not-allowed; }

  .cp-send-spinner {
    width: 12px;
    height: 12px;
    border: 1.5px solid rgba(7,12,27,0.3);
    border-top-color: #070c1b;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg) } }
</style>
