<script lang="ts">
  import { api } from '../lib/api.ts'

  interface Message {
    role: 'user' | 'assistant'
    content: string
    ts: Date
    loading?: boolean
  }

  let messages = $state<Message[]>([])
  let input = $state('')
  let isLoading = $state(false)
  let textarea: HTMLTextAreaElement

  async function submit() {
    const q = input.trim()
    if (!q || isLoading) return
    input = ''

    messages.push({ role: 'user', content: q, ts: new Date() })
    const assistantMsg: Message = { role: 'assistant', content: '', ts: new Date(), loading: true }
    messages.push(assistantMsg)
    isLoading = true

    try {
      const answer = await api.query.ask(q)
      assistantMsg.content = answer
      assistantMsg.loading = false
    } catch (e) {
      assistantMsg.content = `Error: ${String(e)}`
      assistantMsg.loading = false
    } finally {
      isLoading = false
      // Trigger reactivity
      messages = [...messages]
    }
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const examples = [
    'What processes ran on the compromised host?',
    'Summarize all lateral movement indicators',
    'Which user accounts showed anomalous login times?',
    'What network connections were made after the initial detection?',
  ]
</script>

<div class="view">
  <div class="view-header">
    <h1>AI Query</h1>
    <span class="model-badge">qwen3:14b</span>
  </div>

  <div class="messages-area">
    {#if messages.length === 0}
      <div class="welcome">
        <div class="welcome-icon">🤖</div>
        <h2>Ask the SOC Brain</h2>
        <p>Query your ingested events using natural language. The AI analyzes only evidence from your local data.</p>
        <div class="examples">
          {#each examples as ex}
            <button class="example-btn" onclick={() => { input = ex; textarea?.focus() }}>{ex}</button>
          {/each}
        </div>
      </div>
    {:else}
      {#each messages as msg}
        <div class="message message-{msg.role}">
          <div class="message-role">{msg.role === 'user' ? 'You' : '🤖 SOC Brain'}</div>
          <div class="message-content">
            {#if msg.loading}
              <span class="typing-indicator">
                <span></span><span></span><span></span>
              </span>
            {:else}
              {msg.content}
            {/if}
          </div>
          <div class="message-time">{msg.ts.toLocaleTimeString()}</div>
        </div>
      {/each}
    {/if}
  </div>

  <div class="input-area">
    <textarea
      bind:this={textarea}
      bind:value={input}
      onkeydown={onKeydown}
      placeholder="Ask about your security events… (Enter to send, Shift+Enter for newline)"
      rows={3}
      disabled={isLoading}
    ></textarea>
    <button class="btn btn-primary send-btn" onclick={submit} disabled={isLoading || !input.trim()}>
      {isLoading ? '…' : '→ Ask'}
    </button>
  </div>
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }

  .view-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 20px; border-bottom: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0;
  }
  h1 { font-size: 16px; font-weight: 600; }
  .model-badge {
    font-size: 11px; font-family: var(--font-mono);
    background: var(--bg-tertiary); border: 1px solid var(--border);
    padding: 2px 8px; border-radius: 10px; color: var(--text-secondary);
  }

  .messages-area {
    flex: 1; overflow-y: auto; padding: 20px;
    display: flex; flex-direction: column; gap: 16px;
  }

  .welcome {
    display: flex; flex-direction: column; align-items: center;
    text-align: center; padding: 60px 40px; gap: 12px; color: var(--text-secondary);
  }
  .welcome-icon { font-size: 48px; margin-bottom: 8px; }
  .welcome h2 { color: var(--text-primary); font-size: 20px; font-weight: 600; }
  .welcome p { max-width: 460px; line-height: 1.6; }

  .examples { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 12px; }
  .example-btn {
    background: var(--bg-card); border: 1px solid var(--border);
    color: var(--text-secondary); padding: 6px 12px; border-radius: 16px;
    font-size: 12px; cursor: pointer; transition: all 0.1s;
  }
  .example-btn:hover { border-color: var(--accent-blue); color: var(--accent-blue); }

  .message { display: flex; flex-direction: column; gap: 4px; max-width: 800px; }
  .message-user { align-self: flex-end; }
  .message-assistant { align-self: flex-start; }

  .message-role {
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.5px; color: var(--text-muted);
  }
  .message-user .message-role { text-align: right; }

  .message-content {
    padding: 12px 16px; border-radius: var(--radius-md);
    font-size: 14px; line-height: 1.6; white-space: pre-wrap;
  }
  .message-user .message-content {
    background: rgba(88,166,255,0.1); border: 1px solid rgba(88,166,255,0.2);
    color: var(--text-primary);
  }
  .message-assistant .message-content {
    background: var(--bg-card); border: 1px solid var(--border);
    color: var(--text-primary);
  }

  .message-time { font-size: 10px; color: var(--text-muted); }
  .message-user .message-time { text-align: right; }

  .typing-indicator { display: inline-flex; gap: 4px; align-items: center; }
  .typing-indicator span {
    width: 6px; height: 6px; background: var(--accent-blue);
    border-radius: 50%; animation: pulse 1.2s ease-in-out infinite;
  }
  .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
  .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes pulse { 0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); } 40% { opacity: 1; transform: scale(1); } }

  .input-area {
    padding: 16px 20px; border-top: 1px solid var(--border);
    background: var(--bg-secondary); display: flex; gap: 12px;
    align-items: flex-end; flex-shrink: 0;
  }
  .input-area textarea { flex: 1; resize: none; }
  .send-btn { padding: 8px 20px; align-self: flex-end; }
</style>
