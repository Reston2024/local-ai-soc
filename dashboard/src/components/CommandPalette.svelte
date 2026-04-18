<script lang="ts">
  import { api, type Detection, type NormalizedEvent, type GraphEntity } from '../lib/api.ts'
  import { ALL_NAV, sev, type ViewId } from '../lib/tokens.ts'

  // ---------------------------------------------------------------------------
  // Props
  // ---------------------------------------------------------------------------
  interface Props {
    open: boolean
    onClose: () => void
    onNavigate: (view: ViewId) => void
    onInvestigate: (detectionId: string) => void
    onOpenInGraph: (entityId: string) => void
  }

  let { open, onClose, onNavigate, onInvestigate, onOpenInGraph }: Props = $props()

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  let query        = $state('')
  let selectedIdx  = $state(0)
  let searching    = $state(false)

  let detResults   = $state<Detection[]>([])
  let eventResults = $state<NormalizedEvent[]>([])
  let entResults   = $state<GraphEntity[]>([])

  let inputEl: HTMLInputElement | null = $state(null)
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  // ---------------------------------------------------------------------------
  // Palette item shape
  // ---------------------------------------------------------------------------
  interface PaletteItem {
    id: string
    type: 'nav' | 'detection' | 'event' | 'entity' | 'action'
    label: string
    sublabel?: string
    badge?: string
    badgeColor?: string
    run: () => void
  }

  interface PaletteGroup {
    label: string
    items: PaletteItem[]
  }

  // ---------------------------------------------------------------------------
  // Build groups from current state
  // ---------------------------------------------------------------------------
  const groups = $derived.by<PaletteGroup[]>(() => {
    const q = query.trim().toLowerCase()

    // ── Navigation ──────────────────────────────────────────────────────────
    const navItems = ALL_NAV
      .filter(n => !q || n.label.toLowerCase().includes(q) || n.group.toLowerCase().includes(q))
      .slice(0, q ? 8 : 20)
      .map<PaletteItem>(n => ({
        id:    `nav:${n.id}`,
        type:  'nav',
        label: `Go to ${n.label}`,
        sublabel: n.group,
        run: () => { onNavigate(n.id); onClose() },
      }))

    // ── Detections ──────────────────────────────────────────────────────────
    const detItems = detResults
      .filter(d => !q || d.rule_name.toLowerCase().includes(q) || (d.severity ?? '').toLowerCase().includes(q))
      .slice(0, 6)
      .map<PaletteItem>(d => {
        const tok = sev(d.severity)
        return {
          id:         `det:${d.id}`,
          type:       'detection',
          label:      d.rule_name,
          sublabel:   d.attack_technique ? `${d.attack_technique} · ${d.attack_tactic ?? ''}` : (d.fired_at ?? d.created_at ?? '').slice(0, 16),
          badge:      d.severity ?? 'info',
          badgeColor: tok.fg,
          run: () => { onInvestigate(d.id); onClose() },
        }
      })

    // ── Events ──────────────────────────────────────────────────────────────
    const evtItems = eventResults
      .slice(0, 5)
      .map<PaletteItem>(e => ({
        id:       `evt:${e.event_id}`,
        type:     'event',
        label:    e.event_type ?? e.process_name ?? e.event_id,
        sublabel: `${e.hostname ?? '—'} · ${(e.timestamp ?? '').slice(0, 16)}`,
        badge:    e.severity,
        badgeColor: sev(e.severity).fg,
        run: () => { onNavigate('events'); onClose() },
      }))

    // ── Graph entities ───────────────────────────────────────────────────────
    const entItems = entResults
      .slice(0, 5)
      .map<PaletteItem>(e => {
        const eid = e.entity_id ?? e.id ?? ''
        const lbl = e.label ?? e.entity_name ?? eid
        return {
          id:       `ent:${eid}`,
          type:     'entity',
          label:    lbl,
          sublabel: e.type ?? e.entity_type ?? 'entity',
          run: () => { onOpenInGraph(eid); onClose() },
        }
      })

    // ── Actions (always shown) ───────────────────────────────────────────────
    const actionItems: PaletteItem[] = [
      { id: 'action:triage',     type: 'action', label: 'Run AI Triage',          sublabel: 'Analyse all open detections', run: () => { onNavigate('overview');    onClose() } },
      { id: 'action:detections', type: 'action', label: 'Run Detection Engine',   sublabel: 'Re-scan events against rules', run: () => { onNavigate('detections');  onClose() } },
      { id: 'action:hunt',       type: 'action', label: 'Start a Threat Hunt',    sublabel: 'Open the hunting workbench',  run: () => { onNavigate('hunting');     onClose() } },
      { id: 'action:graph',      type: 'action', label: 'Open Attack Graph',      sublabel: 'Explore entity relationships',run: () => { onNavigate('graph');       onClose() } },
      { id: 'action:ingest',     type: 'action', label: 'Ingest Log Files',       sublabel: 'Upload EVTX / JSON / CSV',    run: () => { onNavigate('ingest');      onClose() } },
    ].filter(a => !q || a.label.toLowerCase().includes(q) || (a.sublabel ?? '').toLowerCase().includes(q))

    // ── Assemble groups (omit empty) ─────────────────────────────────────────
    const result: PaletteGroup[] = []
    if (navItems.length)    result.push({ label: 'Navigate',   items: navItems })
    if (detItems.length)    result.push({ label: 'Detections', items: detItems })
    if (evtItems.length)    result.push({ label: 'Events',     items: evtItems })
    if (entItems.length)    result.push({ label: 'Hosts / Entities', items: entItems })
    if (actionItems.length && !q) result.push({ label: 'Actions', items: actionItems })
    return result
  })

  /** Flat ordered list used for keyboard index math. */
  const flatItems = $derived(groups.flatMap(g => g.items))

  // ---------------------------------------------------------------------------
  // Keyboard navigation
  // ---------------------------------------------------------------------------
  function handleKeyDown(e: KeyboardEvent) {
    if (!open) return
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        selectedIdx = (selectedIdx + 1) % Math.max(flatItems.length, 1)
        scrollSelectedIntoView()
        break
      case 'ArrowUp':
        e.preventDefault()
        selectedIdx = (selectedIdx - 1 + Math.max(flatItems.length, 1)) % Math.max(flatItems.length, 1)
        scrollSelectedIntoView()
        break
      case 'Enter':
        e.preventDefault()
        flatItems[selectedIdx]?.run()
        break
      case 'Escape':
        e.preventDefault()
        onClose()
        break
    }
  }

  function scrollSelectedIntoView() {
    requestAnimationFrame(() => {
      document.querySelector('.palette-item.selected')?.scrollIntoView({ block: 'nearest' })
    })
  }

  // ---------------------------------------------------------------------------
  // Live search — debounced, fires when query >= 2 chars
  // ---------------------------------------------------------------------------
  $effect(() => {
    const q = query.trim()
    if (debounceTimer) clearTimeout(debounceTimer)

    if (q.length < 2) {
      detResults   = []
      eventResults = []
      entResults   = []
      searching    = false
      return
    }

    searching = true
    debounceTimer = setTimeout(async () => {
      try {
        const [dets, evts, ents] = await Promise.allSettled([
          api.detections.list({ limit: 10 }),
          api.events.search(q, 8),
          api.graph.entities({ limit: 20 }),
        ])

        if (dets.status === 'fulfilled') {
          detResults = (dets.value.detections ?? []).filter(d =>
            d.rule_name.toLowerCase().includes(q) ||
            (d.severity ?? '').toLowerCase().includes(q)
          )
        }
        if (evts.status === 'fulfilled') {
          eventResults = evts.value.events ?? []
        }
        if (ents.status === 'fulfilled') {
          entResults = (ents.value.entities ?? []).filter(e => {
            const lbl = (e.label ?? e.entity_name ?? '').toLowerCase()
            return lbl.includes(q)
          })
        }
      } catch { /* silent — palette degrades to nav-only */ }
      searching = false
    }, 180)
  })

  // ---------------------------------------------------------------------------
  // Reset index when results change
  // ---------------------------------------------------------------------------
  $effect(() => {
    // Depend on groups length — reset scroll position when results refresh
    void groups
    selectedIdx = 0
  })

  // ---------------------------------------------------------------------------
  // Focus input on open / restore body scroll on close
  // ---------------------------------------------------------------------------
  $effect(() => {
    if (open) {
      // Lock body scroll
      document.body.style.overflow = 'hidden'
      requestAnimationFrame(() => inputEl?.focus())
    } else {
      document.body.style.overflow = ''
      query = ''
      detResults   = []
      eventResults = []
      entResults   = []
    }
  })

  // ---------------------------------------------------------------------------
  // Global keyboard listener (mounted once, reads `open` reactively)
  // ---------------------------------------------------------------------------
  $effect(() => {
    const handler = (e: KeyboardEvent) => handleKeyDown(e)
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  })

  // ---------------------------------------------------------------------------
  // Type labels
  // ---------------------------------------------------------------------------
  const typeLabel: Record<string, string> = {
    nav: 'View', detection: 'Alert', event: 'Event', entity: 'Host', action: 'Action',
  }
</script>

<!-- Backdrop -->
{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="palette-backdrop" onclick={onClose}>
    <!-- Dialog — stop propagation so clicking inside doesn't close -->
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div class="palette-dialog" onclick={(e) => e.stopPropagation()} role="dialog" aria-label="Command palette" aria-modal="true" tabindex="-1">

      <!-- Search input -->
      <div class="palette-input-row">
        <svg class="palette-search-icon" width="15" height="15" viewBox="0 0 16 16" fill="none">
          <circle cx="7" cy="7" r="4.5" stroke="currentColor" stroke-width="1.6"/>
          <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
        </svg>
        <input
          bind:this={inputEl}
          bind:value={query}
          class="palette-input"
          type="text"
          placeholder="Search views, detections, events, hosts…"
          autocomplete="off"
          spellcheck="false"
        />
        {#if searching}
          <span class="palette-spinner"></span>
        {:else}
          <kbd class="palette-esc-hint">Esc</kbd>
        {/if}
      </div>

      <!-- Results -->
      <div class="palette-results" role="listbox">
        {#if flatItems.length === 0}
          <div class="palette-empty">
            {query.length >= 2 && !searching ? 'No matches' : 'Type to search…'}
          </div>
        {:else}
          {#each groups as group}
            <div class="palette-group-header">{group.label}</div>
            {#each group.items as item}
              {@const idx = flatItems.indexOf(item)}
              <!-- svelte-ignore a11y_click_events_have_key_events -->
              <div
                class="palette-item"
                class:selected={idx === selectedIdx}
                role="option"
                aria-selected={idx === selectedIdx}
                tabindex="0"
                onclick={() => item.run()}
                onmouseenter={() => { selectedIdx = idx }}
              >
                <span class="palette-item-type">{typeLabel[item.type] ?? item.type}</span>
                <span class="palette-item-label">{item.label}</span>
                {#if item.sublabel}
                  <span class="palette-item-sub">{item.sublabel}</span>
                {/if}
                {#if item.badge}
                  <span class="palette-item-badge" style="color:{item.badgeColor ?? '#3b82f6'}">
                    {item.badge}
                  </span>
                {/if}
                {#if idx === selectedIdx}
                  <span class="palette-enter-hint">↵</span>
                {/if}
              </div>
            {/each}
          {/each}
        {/if}
      </div>

      <!-- Footer -->
      <div class="palette-footer">
        <span><kbd>↑↓</kbd> Navigate</span>
        <span><kbd>↵</kbd> Select</span>
        <span><kbd>Esc</kbd> Close</span>
        <span class="palette-footer-spacer"></span>
        <span class="palette-footer-brand">SOC Brain ⌘K</span>
      </div>
    </div>
  </div>
{/if}

<style>
  /* ── Backdrop ── */
  .palette-backdrop {
    position: fixed;
    inset: 0;
    z-index: 9000;
    background: rgba(4, 8, 20, 0.72);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 12vh;
    animation: backdropIn 0.1s ease;
  }

  @keyframes backdropIn {
    from { opacity: 0 }
    to   { opacity: 1 }
  }

  /* ── Dialog ── */
  .palette-dialog {
    width: 600px;
    max-width: calc(100vw - 32px);
    background: #0d1630;
    border: 1px solid #1e3260;
    border-radius: 14px;
    box-shadow: 0 24px 64px rgba(0,0,0,0.85), 0 0 0 1px rgba(255,255,255,0.04);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: dialogIn 0.14s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes dialogIn {
    from { opacity: 0; transform: scale(0.97) translateY(-6px) }
    to   { opacity: 1; transform: scale(1)    translateY(0) }
  }

  /* ── Input row ── */
  .palette-input-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px;
    border-bottom: 1px solid #1a2847;
    flex-shrink: 0;
  }

  .palette-search-icon {
    color: rgba(255,255,255,0.28);
    flex-shrink: 0;
  }

  .palette-input {
    flex: 1;
    background: none;
    border: none;
    outline: none;
    color: #e2eaff;
    font-size: 15px;
    font-family: var(--font-sans);
    caret-color: #00d4ff;
    padding: 0;
  }

  .palette-input::placeholder {
    color: rgba(255,255,255,0.22);
  }

  .palette-esc-hint {
    font-size: 10px;
    color: rgba(255,255,255,0.22);
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 4px;
    padding: 2px 5px;
    flex-shrink: 0;
    font-family: var(--font-sans);
    cursor: default;
  }

  /* ── Spinner ── */
  .palette-spinner {
    width: 14px;
    height: 14px;
    border: 1.5px solid rgba(255,255,255,0.12);
    border-top-color: #00d4ff;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    flex-shrink: 0;
  }
  @keyframes spin { to { transform: rotate(360deg) } }

  /* ── Results ── */
  .palette-results {
    overflow-y: auto;
    max-height: 400px;
    padding: 6px 0;
  }

  .palette-results::-webkit-scrollbar { width: 3px; }
  .palette-results::-webkit-scrollbar-thumb { background: #1a2847; border-radius: 2px; }

  .palette-empty {
    padding: 32px 20px;
    text-align: center;
    color: rgba(255,255,255,0.22);
    font-size: 13px;
  }

  /* ── Group header ── */
  .palette-group-header {
    padding: 8px 16px 3px;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: rgba(255,255,255,0.22);
    user-select: none;
  }

  /* ── Item ── */
  .palette-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    cursor: pointer;
    transition: background 0.08s;
    border-radius: 0;
  }

  .palette-item:hover,
  .palette-item.selected {
    background: rgba(59,130,246,0.1);
  }

  .palette-item.selected {
    background: rgba(59,130,246,0.14);
  }

  .palette-item-type {
    font-size: 10px;
    font-weight: 600;
    color: rgba(255,255,255,0.22);
    min-width: 54px;
    flex-shrink: 0;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }

  .palette-item-label {
    flex: 1;
    font-size: 13.5px;
    color: #e2eaff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .palette-item-sub {
    font-size: 11.5px;
    color: rgba(255,255,255,0.32);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 180px;
    flex-shrink: 0;
  }

  .palette-item-badge {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    flex-shrink: 0;
    font-family: var(--font-mono);
  }

  .palette-enter-hint {
    font-size: 12px;
    color: rgba(255,255,255,0.3);
    flex-shrink: 0;
    margin-left: auto;
  }

  /* ── Footer ── */
  .palette-footer {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 8px 16px;
    border-top: 1px solid #1a2847;
    flex-shrink: 0;
  }

  .palette-footer span {
    font-size: 11px;
    color: rgba(255,255,255,0.22);
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .palette-footer kbd {
    font-size: 10px;
    font-family: var(--font-sans);
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 3px;
    padding: 1px 4px;
    color: rgba(255,255,255,0.38);
  }

  .palette-footer-spacer {
    flex: 1;
  }

  .palette-footer-brand {
    color: rgba(255,255,255,0.14) !important;
    font-family: var(--font-mono) !important;
    font-size: 10px !important;
  }
</style>
