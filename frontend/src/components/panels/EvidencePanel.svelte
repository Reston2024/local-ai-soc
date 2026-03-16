<script lang="ts">
  let { selected } = $props<{ selected?: any }>()
</script>

<aside class="evidence-panel card">
  <h3>Evidence</h3>
  {#if selected}
    <div class="field"><span class="key">ID</span><span class="val">{selected.id}</span></div>
    <div class="field"><span class="key">Type</span><span class="val">{selected.type}</span></div>
    <div class="field"><span class="key">Label</span><span class="val">{selected.label}</span></div>
    {#if selected.timestamp}
      <div class="field"><span class="key">Time</span><span class="val">{selected.timestamp}</span></div>
    {/if}
    {#if selected.src_ip}
      <div class="field"><span class="key">Src IP</span><span class="val">{selected.src_ip}</span></div>
    {/if}
    {#if selected.dst_ip}
      <div class="field"><span class="key">Dst IP</span><span class="val">{selected.dst_ip}</span></div>
    {/if}
    {#if selected.query}
      <div class="field"><span class="key">Query</span><span class="val">{selected.query}</span></div>
    {/if}
    {#if selected.threat_score && selected.threat_score > 0}
      <div class="field">
        <span class="key">Score</span>
        <span class="val">
          <span class="score-badge {selected.threat_score > 60 ? 'score-red' : selected.threat_score >= 30 ? 'score-yellow' : 'score-green'}">
            {selected.threat_score}
          </span>
        </span>
      </div>
    {/if}
    {#if selected.attack_tags && selected.attack_tags.length > 0}
      <div class="field field-column">
        <span class="key">ATT&CK</span>
        <div class="tags">
          {#each selected.attack_tags as tag}
            <span class="attack-pill">{tag.tactic} · {tag.technique}</span>
          {/each}
        </div>
      </div>
    {/if}
  {:else}
    <p class="muted">Click a graph node to view details</p>
  {/if}
</aside>

<style>
  .evidence-panel { width: 200px; flex-shrink: 0; overflow-y: auto; border-radius: 0; border-top: none; border-bottom: none; border-right: none; }
  h3 { margin-bottom: 8px; color: #6b7280; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
  .field { display: flex; gap: 6px; padding: 4px 0; border-bottom: 1px solid #1f2937; flex-wrap: wrap; }
  .key { color: #6b7280; font-size: 11px; min-width: 50px; }
  .val { color: #e5e7eb; font-size: 11px; word-break: break-all; }
  .muted { color: #6b7280; font-size: 11px; }
  .field-column { flex-direction: column; align-items: flex-start; }
  .tags { display: flex; flex-wrap: wrap; gap: 2px; margin-top: 2px; }
  .score-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }
  .score-green { background: #22c55e; color: white; }
  .score-yellow { background: #eab308; color: white; }
  .score-red { background: #ef4444; color: white; }
  .attack-pill { display: inline-block; padding: 2px 6px; border-radius: 4px; background: #3b82f6; color: white; font-size: 0.75rem; margin: 2px; }
</style>
