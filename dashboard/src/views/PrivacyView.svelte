<script lang="ts">
  /**
   * PrivacyView — outbound traffic privacy monitoring dashboard.
   *
   * Sections:
   * 1. Status bar — blocklist feed health + domain count
   * 2. Detections tab — cookie exfil, tracking pixel, DNS tracker detections
   * 3. HTTP Traffic tab — plain HTTP events with tracker flagging
   * 4. DNS Queries tab — DNS lookups with tracker domain flagging
   *
   * Note: TLS/SSL events don't carry SNI in Malcolm's Arkime session format,
   * so DNS-based detection is used for encrypted traffic monitoring.
   */
  import { api } from '../lib/api.ts'
  import type { PrivacyHit, PrivacyHttpEvent, PrivacyFeedStatus, PrivacyDnsEvent } from '../lib/api.ts'
  import { onMount } from 'svelte'

  // ── State ──────────────────────────────────────────────────────────────────
  let hits         = $state<PrivacyHit[]>([])
  let httpEvts     = $state<PrivacyHttpEvent[]>([])
  let dnsEvts      = $state<PrivacyDnsEvent[]>([])
  let feeds        = $state<PrivacyFeedStatus[]>([])
  let domainCount  = $state(0)
  let httpTrackers = $state(0)
  let dnsTrackers  = $state(0)
  let loading      = $state(false)
  let scanning     = $state(false)
  let scanMsg      = $state<string | null>(null)
  let filterTrackerHttp = $state(false)
  let filterTrackerDns  = $state(false)
  let activeTab    = $state<'hits' | 'http' | 'dns'>('hits')

  async function load() {
    loading = true
    try {
      const [hitsRes, feedsRes, httpRes, dnsRes] = await Promise.all([
        api.privacy.hits(),
        api.privacy.feeds(),
        api.privacy.httpEvents(),
        api.privacy.dnsEvents(),
      ])
      hits         = hitsRes.hits ?? []
      feeds        = feedsRes.feeds ?? []
      domainCount  = feedsRes.domain_count ?? 0
      httpEvts     = httpRes.events ?? []
      httpTrackers = httpRes.tracker_count ?? 0
      dnsEvts      = dnsRes.events ?? []
      dnsTrackers  = dnsRes.tracker_count ?? 0
    } catch (e) {
      console.error('PrivacyView: load failed', e)
    } finally {
      loading = false
    }
  }

  async function triggerScan() {
    scanning = true
    scanMsg  = null
    try {
      const res = await api.privacy.scan()
      scanMsg = res.triggered
        ? `Scan complete — ${res.detections_found} detection(s) found`
        : 'Scan failed'
      await load()
    } catch (e: any) {
      scanMsg = `Error: ${e?.message ?? 'scan failed'}`
    } finally {
      scanning = false
    }
  }

  const filteredHttp = $derived(
    filterTrackerHttp ? httpEvts.filter(e => e.is_tracker) : httpEvts
  )
  const filteredDns = $derived(
    filterTrackerDns ? dnsEvts.filter(e => e.is_tracker) : dnsEvts
  )
  const totalTrackers = $derived(httpTrackers + dnsTrackers)

  // ── Formatters ─────────────────────────────────────────────────────────────
  function shortStr(s: string | null, max = 40): string {
    if (!s) return '—'
    return s.length > max ? s.slice(0, max - 2) + '…' : s
  }
  function shortUri(u: string | null): string {
    if (!u) return '—'
    try {
      const url = new URL(u.startsWith('http') ? u : 'http://x' + u)
      const path = url.pathname + url.search
      return path.length > 50 ? path.slice(0, 48) + '…' : path
    } catch {
      return u.length > 50 ? u.slice(0, 48) + '…' : u
    }
  }
  function formatBytes(n: number | null): string {
    if (n === null || n === undefined) return '—'
    if (n < 1024) return `${n} B`
    if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`
    return `${(n / 1048576).toFixed(1)} MB`
  }
  function formatTs(ts: string | null): string {
    if (!ts) return '—'
    try {
      return new Date(ts).toLocaleTimeString([], {
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
      })
    } catch { return ts }
  }

  onMount(load)
</script>

<div class="privacy-root">

  <!-- ── Header ────────────────────────────────────────────────────────────── -->
  <div class="pv-header">
    <div class="pv-title">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M8 2L2 5v4c0 3 2.5 5.5 6 6.5C11.5 14.5 14 12 14 9V5L8 2Z"
          stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
        <path d="M5.5 8l1.5 1.5L10.5 6" stroke="currentColor" stroke-width="1.4"
          stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      Privacy Monitor
    </div>
    <div class="pv-header-right">
      {#if scanMsg}
        <span class="pv-scan-msg" class:ok={scanMsg.startsWith('Scan complete')}>{scanMsg}</span>
      {/if}
      <button class="pv-scan-btn" onclick={triggerScan} disabled={scanning} title="Run privacy scan now">
        {#if scanning}
          <span class="pv-spinner"></span> Scanning…
        {:else}
          ⟳ Scan Now
        {/if}
      </button>
      <button class="pv-refresh-btn" onclick={load} disabled={loading} title="Refresh">
        {loading ? '…' : '↺'}
      </button>
    </div>
  </div>

  <!-- ── Feed status cards ─────────────────────────────────────────────────── -->
  <div class="pv-feeds">
    <div class="feed-card {domainCount > 0 ? 'feed-ok' : 'feed-warn'}">
      <div class="feed-label">Blocklist Domains</div>
      <div class="feed-value">{domainCount.toLocaleString()}</div>
    </div>
    {#each feeds as f}
      <div class="feed-card {f.last_sync ? 'feed-ok' : 'feed-warn'}">
        <div class="feed-label">{f.feed}</div>
        <div class="feed-value">{(f.domain_count ?? 0).toLocaleString()}</div>
        <div class="feed-sync">{f.last_sync ? `synced ${formatTs(f.last_sync)}` : 'not synced'}</div>
      </div>
    {/each}
    {#if feeds.length === 0 && !loading}
      <div class="feed-card feed-warn feed-wide">
        <div class="feed-label">Blocklist status</div>
        <div class="feed-value">—</div>
        <div class="feed-sync">Downloading tracker list… refresh in a few minutes</div>
      </div>
    {/if}
    <div class="feed-card">
      <div class="feed-label">HTTP Events</div>
      <div class="feed-value">{httpEvts.length}</div>
    </div>
    <div class="feed-card">
      <div class="feed-label">DNS Queries</div>
      <div class="feed-value">{dnsEvts.length}</div>
    </div>
    <div class="feed-card {totalTrackers > 0 ? 'feed-alert' : ''}">
      <div class="feed-label">Tracker Contacts</div>
      <div class="feed-value tracker-count">{totalTrackers}</div>
    </div>
    <div class="feed-card {hits.length > 0 ? 'feed-alert' : ''}">
      <div class="feed-label">Detections</div>
      <div class="feed-value">{hits.length}</div>
    </div>
  </div>

  <!-- ── Tabs ──────────────────────────────────────────────────────────────── -->
  <div class="pv-tabs">
    <button class="pv-tab" class:active={activeTab === 'hits'} onclick={() => activeTab = 'hits'}>
      Detections
      {#if hits.length > 0}<span class="tab-badge">{hits.length}</span>{/if}
    </button>
    <button class="pv-tab" class:active={activeTab === 'dns'} onclick={() => activeTab = 'dns'}>
      DNS Queries
      {#if dnsTrackers > 0}<span class="tab-badge tab-tracker">{dnsTrackers} trackers</span>{/if}
    </button>
    <button class="pv-tab" class:active={activeTab === 'http'} onclick={() => activeTab = 'http'}>
      HTTP Traffic
      {#if httpTrackers > 0}<span class="tab-badge tab-tracker">{httpTrackers} trackers</span>{/if}
    </button>
  </div>

  <!-- ── Content ───────────────────────────────────────────────────────────── -->
  <div class="pv-content">

    <!-- ── Detections tab ── -->
    {#if activeTab === 'hits'}
      {#if loading}
        <div class="pv-empty"><span class="pv-loading">Loading…</span></div>
      {:else if hits.length === 0}
        <div class="pv-empty">
          <div class="pv-empty-icon">🔒</div>
          <div class="pv-empty-title">No privacy detections</div>
          <div class="pv-empty-sub">
            {#if domainCount === 0}
              Blocklist not yet populated — click <strong>Scan Now</strong> after backend syncs feeds.
            {:else}
              No cookie exfiltration, tracking pixel, or tracker DNS queries detected in recent traffic.
            {/if}
          </div>
        </div>
      {:else}
        <div class="pv-table-wrap">
          <table class="pv-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Rule</th>
                <th>Domain</th>
                <th>Severity</th>
              </tr>
            </thead>
            <tbody>
              {#each hits as hit}
                <tr>
                  <td class="mono">{formatTs(hit.created_at)}</td>
                  <td><span class="type-badge">{hit.rule_id.split('-')[1] ?? hit.rule_id}</span></td>
                  <td>{hit.rule_name}</td>
                  <td class="mono tracker-domain" title={hit.entity_key ?? ''}>{shortStr(hit.entity_key, 45)}</td>
                  <td><span class="sev-badge sev-{hit.severity}">{hit.severity}</span></td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

    <!-- ── DNS Queries tab ── -->
    {:else if activeTab === 'dns'}
      <div class="pv-traffic-toolbar">
        <label class="tracker-filter">
          <input type="checkbox" bind:checked={filterTrackerDns} />
          Show tracker domains only
        </label>
        <span class="pv-traffic-count">{filteredDns.length} queries</span>
      </div>
      {#if loading}
        <div class="pv-empty"><span class="pv-loading">Loading…</span></div>
      {:else if filteredDns.length === 0}
        <div class="pv-empty">
          <div class="pv-empty-title">{filterTrackerDns ? 'No tracker DNS queries' : 'No DNS query events'}</div>
          <div class="pv-empty-sub">
            DNS queries from Zeek dns.log are used to detect tracker domain lookups on encrypted networks.
          </div>
        </div>
      {:else}
        <div class="pv-table-wrap">
          <table class="pv-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Src IP</th>
                <th>Query</th>
                <th>Type</th>
                <th>Tracker</th>
              </tr>
            </thead>
            <tbody>
              {#each filteredDns as evt}
                <tr class:tracker-row={evt.is_tracker}>
                  <td class="mono">{formatTs(evt.timestamp)}</td>
                  <td class="mono">{evt.src_ip ?? '—'}</td>
                  <td class="mono domain-cell {evt.is_tracker ? 'tracker-domain' : ''}" title={evt.query ?? ''}>
                    {shortStr(evt.query, 52)}
                  </td>
                  <td class="mono qtype-cell">{evt.qtype ?? '—'}</td>
                  <td>
                    {#if evt.is_tracker}
                      <span class="tracker-flag">⚠ TRACKER</span>
                    {:else}
                      <span class="clean-flag">✓</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

    <!-- ── HTTP Traffic tab ── -->
    {:else}
      <div class="pv-traffic-toolbar">
        <label class="tracker-filter">
          <input type="checkbox" bind:checked={filterTrackerHttp} />
          Show tracker domains only
        </label>
        <span class="pv-traffic-count">{filteredHttp.length} events</span>
      </div>
      {#if loading}
        <div class="pv-empty"><span class="pv-loading">Loading…</span></div>
      {:else if filteredHttp.length === 0}
        <div class="pv-empty">
          <div class="pv-empty-title">{filterTrackerHttp ? 'No tracker contacts in HTTP' : 'No plain HTTP events'}</div>
          <div class="pv-empty-sub">Most traffic is HTTPS — check DNS Queries tab for encrypted tracker detection.</div>
        </div>
      {:else}
        <div class="pv-table-wrap">
          <table class="pv-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Src IP</th>
                <th>Domain</th>
                <th>Method</th>
                <th>Status</th>
                <th>Path</th>
                <th>↑ Req</th>
                <th>↓ Resp</th>
                <th>Tracker</th>
              </tr>
            </thead>
            <tbody>
              {#each filteredHttp as evt}
                <tr class:tracker-row={evt.is_tracker}>
                  <td class="mono">{formatTs(evt.timestamp)}</td>
                  <td class="mono">{evt.src_ip ?? '—'}</td>
                  <td class="mono domain-cell {evt.is_tracker ? 'tracker-domain' : ''}" title={evt.domain ?? ''}>
                    {shortStr(evt.domain, 38)}
                  </td>
                  <td class="method-cell">{evt.method ?? '—'}</td>
                  <td class="mono {(evt.status ?? 0) >= 400 ? 'status-err' : ''}">{evt.status ?? '—'}</td>
                  <td class="mono uri-cell" title={evt.uri ?? ''}>{shortUri(evt.uri)}</td>
                  <td class="mono">{formatBytes(evt.req_bytes)}</td>
                  <td class="mono">{formatBytes(evt.resp_bytes)}</td>
                  <td>
                    {#if evt.is_tracker}
                      <span class="tracker-flag">⚠ TRACKER</span>
                    {:else}
                      <span class="clean-flag">✓</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    {/if}

  </div><!-- .pv-content -->
</div>

<style>
  /* ── Root ── */
  .privacy-root {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    background: var(--bg-primary);
  }

  /* ── Header ── */
  .pv-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
    flex-shrink: 0;
    gap: 12px;
  }
  .pv-title {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 13px;
    font-weight: 600;
    color: rgba(255,255,255,0.8);
  }
  .pv-header-right { display: flex; align-items: center; gap: 8px; }

  .pv-scan-msg {
    font-size: 11.5px;
    color: rgba(255,255,255,0.4);
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pv-scan-msg.ok { color: #22c55e; }

  .pv-scan-btn {
    display: flex; align-items: center; gap: 5px;
    padding: 5px 12px;
    background: rgba(0,212,255,0.1);
    border: 1px solid rgba(0,212,255,0.25);
    border-radius: 6px; color: #00d4ff; font-size: 12px;
    cursor: pointer; transition: background 0.12s;
  }
  .pv-scan-btn:hover:not(:disabled) { background: rgba(0,212,255,0.18); }
  .pv-scan-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  .pv-refresh-btn {
    width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px; color: rgba(255,255,255,0.45);
    font-size: 14px; cursor: pointer; transition: background 0.12s;
  }
  .pv-refresh-btn:hover:not(:disabled) { background: rgba(255,255,255,0.08); }

  .pv-spinner {
    width: 10px; height: 10px;
    border: 1.5px solid rgba(0,212,255,0.3);
    border-top-color: #00d4ff;
    border-radius: 50%;
    animation: spin 0.7s linear infinite; flex-shrink: 0;
  }
  @keyframes spin { to { transform: rotate(360deg) } }

  /* ── Feed cards ── */
  .pv-feeds {
    display: flex; align-items: stretch; gap: 10px;
    padding: 12px 16px; border-bottom: 1px solid var(--border);
    flex-shrink: 0; flex-wrap: wrap;
  }
  .feed-card {
    display: flex; flex-direction: column; gap: 2px;
    padding: 8px 14px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 8px; min-width: 100px;
  }
  .feed-card.feed-ok  { border-color: rgba(34,197,94,0.2);  background: rgba(34,197,94,0.04); }
  .feed-card.feed-warn{ border-color: rgba(234,179,8,0.25); background: rgba(234,179,8,0.04); }
  .feed-card.feed-alert{ border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.06); }
  .feed-card.feed-wide { flex: 1; }

  .feed-label {
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.5px; color: rgba(255,255,255,0.35);
  }
  .feed-value {
    font-size: 18px; font-weight: 700;
    color: rgba(255,255,255,0.85);
    font-variant-numeric: tabular-nums;
    font-family: var(--font-mono);
  }
  .feed-value.tracker-count { color: #ef4444; }
  .feed-sync { font-size: 10px; color: rgba(255,255,255,0.3); font-family: var(--font-mono); }

  /* ── Tabs ── */
  .pv-tabs {
    display: flex; gap: 2px; padding: 0 16px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0;
  }
  .pv-tab {
    display: flex; align-items: center; gap: 6px;
    padding: 9px 14px; background: none; border: none;
    border-bottom: 2px solid transparent;
    color: rgba(255,255,255,0.4); font-size: 12.5px;
    cursor: pointer; transition: color 0.12s, border-color 0.12s;
    margin-bottom: -1px; font-family: var(--font-sans);
  }
  .pv-tab:hover { color: rgba(255,255,255,0.7); }
  .pv-tab.active { color: rgba(255,255,255,0.85); border-bottom-color: #00d4ff; }

  .tab-badge {
    font-size: 10px; font-weight: 700;
    background: rgba(239,68,68,0.18); color: #f87171;
    border-radius: 4px; padding: 1px 5px;
  }
  .tab-badge.tab-tracker { background: rgba(234,179,8,0.15); color: #fbbf24; }

  /* ── Content ── */
  .pv-content {
    flex: 1; overflow: hidden; display: flex;
    flex-direction: column; min-height: 0;
  }

  /* ── Empty state ── */
  .pv-empty {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 40px 24px; gap: 10px; text-align: center;
  }
  .pv-empty-icon { font-size: 32px; opacity: 0.5; }
  .pv-empty-title { font-size: 14px; font-weight: 600; color: rgba(255,255,255,0.5); }
  .pv-empty-sub {
    font-size: 12px; color: rgba(255,255,255,0.28);
    line-height: 1.5; max-width: 420px;
  }
  .pv-loading { font-size: 12px; color: rgba(255,255,255,0.3); font-style: italic; }

  /* ── Traffic toolbar ── */
  .pv-traffic-toolbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 16px; border-bottom: 1px solid var(--border);
    background: var(--bg-secondary); flex-shrink: 0;
  }
  .tracker-filter {
    display: flex; align-items: center; gap: 7px;
    font-size: 12px; color: rgba(255,255,255,0.55);
    cursor: pointer; user-select: none;
  }
  .pv-traffic-count { font-size: 11px; color: rgba(255,255,255,0.28); font-family: var(--font-mono); }

  /* ── Table ── */
  .pv-table-wrap {
    flex: 1; overflow-y: auto; min-height: 0;
  }
  .pv-table-wrap::-webkit-scrollbar { width: 4px; }
  .pv-table-wrap::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  .pv-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .pv-table thead th {
    position: sticky; top: 0; background: var(--bg-secondary);
    padding: 6px 12px; text-align: left;
    font-size: 10.5px; font-weight: 600; letter-spacing: 0.4px;
    color: rgba(255,255,255,0.35); text-transform: uppercase;
    border-bottom: 1px solid var(--border); white-space: nowrap;
  }
  .pv-table tbody tr {
    border-bottom: 1px solid rgba(255,255,255,0.04);
    transition: background 0.08s;
  }
  .pv-table tbody tr:hover { background: rgba(255,255,255,0.03); }
  .pv-table td {
    padding: 6px 12px; color: rgba(255,255,255,0.72);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    max-width: 200px;
  }

  /* ── Row / cell styles ── */
  .tracker-row { background: rgba(234,179,8,0.04) !important; }
  .tracker-row:hover { background: rgba(234,179,8,0.08) !important; }

  .mono { font-family: var(--font-mono); }
  .domain-cell { max-width: 300px; }
  .uri-cell    { max-width: 200px; }
  .qtype-cell  { color: rgba(0,212,255,0.7); font-size: 11px; }

  .method-cell { font-weight: 600; color: rgba(0,212,255,0.85); font-family: var(--font-mono); }
  .status-err  { color: #f87171; }
  .tracker-domain { color: #fbbf24; }

  .tracker-flag {
    font-size: 10.5px; font-weight: 700; color: #fbbf24;
    background: rgba(234,179,8,0.15); border: 1px solid rgba(234,179,8,0.3);
    border-radius: 3px; padding: 1px 6px; white-space: nowrap;
  }
  .clean-flag { font-size: 11px; color: rgba(34,197,94,0.6); }

  /* ── Type badge ── */
  .type-badge {
    display: inline-block; padding: 2px 6px;
    background: rgba(59,130,246,0.12); color: #60a5fa;
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: 3px; font-size: 10px; font-family: var(--font-mono);
    text-transform: none;
  }

  /* ── Severity badges ── */
  .sev-badge {
    display: inline-block; padding: 2px 7px; border-radius: 4px;
    font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px;
  }
  .sev-critical { background: rgba(239,68,68,0.2);   color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
  .sev-high     { background: rgba(249,115,22,0.2);  color: #fb923c; border: 1px solid rgba(249,115,22,0.3); }
  .sev-medium   { background: rgba(234,179,8,0.18);  color: #fbbf24; border: 1px solid rgba(234,179,8,0.3); }
  .sev-low      { background: rgba(34,197,94,0.15);  color: #4ade80; border: 1px solid rgba(34,197,94,0.25); }
  .sev-info     { background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.25); }
</style>
