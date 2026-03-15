<script lang="ts">
  import { api, type IngestJobStatus } from '../lib/api.ts'

  let dragOver = $state(false)
  let jobs = $state<IngestJobStatus[]>([])
  let uploading = $state(false)
  let error = $state<string | null>(null)
  let fileInput: HTMLInputElement

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return
    uploading = true
    error = null
    for (const file of Array.from(files)) {
      try {
        const job = await api.ingest.upload(file)
        jobs = [job, ...jobs]
        pollJob(job.job_id)
      } catch (e) {
        error = `Failed to upload ${file.name}: ${String(e)}`
      }
    }
    uploading = false
  }

  async function pollJob(jobId: string) {
    const interval = setInterval(async () => {
      try {
        const status = await api.ingest.status(jobId)
        jobs = jobs.map(j => j.job_id === jobId ? status : j)
        if (status.status === 'complete' || status.status === 'error') {
          clearInterval(interval)
        }
      } catch {
        clearInterval(interval)
      }
    }, 1500)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    dragOver = false
    handleFiles(e.dataTransfer?.files ?? null)
  }

  function pct(job: IngestJobStatus) {
    if (!job.events_total) return 0
    return Math.round((job.events_processed / job.events_total) * 100)
  }

  function statusColor(s: string) {
    return { pending: 'var(--text-muted)', running: 'var(--accent-blue)', complete: 'var(--accent-green)', error: 'var(--accent-red)' }[s] ?? 'var(--text-muted)'
  }
</script>

<div class="view">
  <div class="view-header">
    <h1>Ingest</h1>
  </div>

  {#if error}
    <div class="error-banner">⚠ {error}</div>
  {/if}

  <!-- Drop zone -->
  <div
    class="drop-zone"
    class:drag-over={dragOver}
    role="region"
    aria-label="File drop zone"
    ondragover={(e) => { e.preventDefault(); dragOver = true }}
    ondragleave={() => dragOver = false}
    ondrop={onDrop}
    onclick={() => fileInput.click()}
  >
    <input
      bind:this={fileInput}
      type="file"
      multiple
      accept=".evtx,.json,.ndjson,.jsonl,.csv,.log"
      style="display:none"
      onchange={(e) => handleFiles((e.target as HTMLInputElement).files)}
    />
    <div class="drop-icon">📥</div>
    <div class="drop-title">{uploading ? 'Uploading…' : 'Drop event files here'}</div>
    <div class="drop-sub">EVTX · JSON · NDJSON · CSV · or click to browse</div>
    <div class="drop-note">Files are processed locally — nothing leaves this machine</div>
  </div>

  <!-- Jobs list -->
  {#if jobs.length > 0}
    <div class="jobs-list">
      {#each jobs as job}
        <div class="job-card card">
          <div class="job-header">
            <span class="job-filename">{job.filename}</span>
            <span class="job-status" style="color: {statusColor(job.status)}">{job.status}</span>
          </div>
          {#if job.status === 'running'}
            <div class="progress-bar">
              <div class="progress-fill" style="width: {pct(job)}%"></div>
            </div>
            <div class="job-count">{job.events_processed.toLocaleString()} / {job.events_total.toLocaleString()} events</div>
          {:else if job.status === 'complete'}
            <div class="job-count success">✓ {job.events_processed.toLocaleString()} events ingested</div>
          {:else if job.status === 'error'}
            <div class="job-error">✗ {job.error}</div>
          {:else}
            <div class="job-count">Pending…</div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
  .view-header { display: flex; align-items: center; padding: 12px 20px; border-bottom: 1px solid var(--border); background: var(--bg-secondary); flex-shrink: 0; }
  h1 { font-size: 16px; font-weight: 600; }

  .drop-zone {
    margin: 20px; padding: 48px 24px;
    border: 2px dashed var(--border); border-radius: var(--radius-lg);
    text-align: center; cursor: pointer;
    transition: all 0.15s;
    background: var(--bg-secondary);
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    flex-shrink: 0;
  }
  .drop-zone:hover { border-color: var(--accent-blue); background: rgba(88,166,255,0.03); }
  .drop-zone.drag-over { border-color: var(--accent-blue); background: rgba(88,166,255,0.08); }
  .drop-icon { font-size: 40px; }
  .drop-title { font-size: 16px; font-weight: 600; }
  .drop-sub { color: var(--text-secondary); font-size: 13px; }
  .drop-note { color: var(--text-muted); font-size: 11px; margin-top: 4px; }

  .jobs-list { flex: 1; overflow-y: auto; padding: 0 20px 20px; display: flex; flex-direction: column; gap: 12px; }

  .job-card { display: flex; flex-direction: column; gap: 8px; }
  .job-header { display: flex; justify-content: space-between; align-items: center; }
  .job-filename { font-size: 13px; font-weight: 500; font-family: var(--font-mono); }
  .job-status { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
  .job-count { font-size: 12px; color: var(--text-secondary); }
  .job-count.success { color: var(--accent-green); }
  .job-error { font-size: 12px; color: var(--accent-red); }

  .progress-bar { height: 4px; background: var(--bg-tertiary); border-radius: 2px; overflow: hidden; }
  .progress-fill { height: 100%; background: var(--accent-blue); border-radius: 2px; transition: width 0.3s ease; }

  .error-banner { padding: 12px 20px; background: rgba(248,81,73,0.1); color: var(--severity-critical); border-bottom: 1px solid rgba(248,81,73,0.3); font-size: 13px; }
</style>
