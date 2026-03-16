/**
 * Typed API client for AI SOC Brain.
 *
 * Phase 2 additions:
 *   postIngest       — batch ingest via POST /ingest
 *   ingestSyslog     — single syslog line via POST /ingest/syslog
 *   openEventStream  — SSE stream from GET /events/stream
 *
 * Phase 5 additions:
 *   AlertItem        — typed alert with threat_score and attack_tags fields
 *   getAlerts()      — now returns Promise<AlertItem[]>
 *   getThreats()     — GET /threats → alerts sorted by threat_score desc (score > 0)
 */

const BASE = ''

// ---- Phase 5: Typed alert with threat scoring + ATT&CK tags --------------

export interface AlertItem {
  id: string
  timestamp: string
  rule: string
  severity: string
  event_id: string
  description: string
  threat_score: number          // Phase 5 — default 0 from backend
  attack_tags: Array<{ tactic: string; technique: string }>  // Phase 5 — default []
}

// ---- Phase 1 (preserved) -------------------------------------------------

export async function getHealth(): Promise<{ status: string; ingestion_sources?: string[] }> {
  const r = await fetch(`${BASE}/health`)
  return r.json()
}

export async function getEvents(): Promise<any[]> {
  const r = await fetch(`${BASE}/events`)
  return r.json()
}

export async function getTimeline(): Promise<any[]> {
  const r = await fetch(`${BASE}/timeline`)
  return r.json()
}

export async function getGraph(): Promise<{ nodes: any[]; edges: any[] }> {
  const r = await fetch(`${BASE}/graph`)
  return r.json()
}

export async function getAlerts(): Promise<AlertItem[]> {
  const r = await fetch(`${BASE}/alerts`)
  return r.json()
}

// ---- Phase 5: GET /threats — scored alerts only --------------------------

/**
 * Return alerts sorted by threat_score descending, score > 0 only.
 * Useful for the threat-priority panel.
 */
export async function getThreats(): Promise<AlertItem[]> {
  const r = await fetch(`${BASE}/threats`)
  return r.json()
}

export async function loadFixtures(): Promise<{ loaded: number; alerts: number }> {
  const r = await fetch(`${BASE}/fixtures/load`, { method: 'POST' })
  return r.json()
}

// ---- Phase 2 additions ---------------------------------------------------

/**
 * Batch-ingest events from any source via POST /ingest.
 * @param events  Array of raw event dicts
 * @param source  Ingest source label: "api" | "vector" | "syslog" | "fixture"
 */
export async function postIngest(
  events: Record<string, unknown>[],
  source: 'api' | 'vector' | 'syslog' | 'fixture' = 'api'
): Promise<{ accepted: number; alerts: number; source: string }> {
  const r = await fetch(`${BASE}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ events, source }),
  })
  return r.json()
}

/**
 * Ingest a single raw syslog line (RFC3164, RFC5424, or CEF).
 */
export async function ingestSyslog(
  line: string
): Promise<{ accepted: number; alerts: number; event_id: string }> {
  const r = await fetch(`${BASE}/ingest/syslog`, {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain' },
    body: line,
  })
  return r.json()
}

/**
 * Open a Server-Sent Events stream to GET /events/stream.
 *
 * @param onEvent   Called with each parsed event object as it arrives.
 * @param onError   Called on connection error (optional).
 * @returns         EventSource instance — call .close() to stop.
 */
export function openEventStream(
  onEvent: (event: Record<string, unknown>) => void,
  onError?: (e: Event) => void
): EventSource {
  const es = new EventSource(`${BASE}/events/stream`)
  es.onmessage = (e) => {
    if (e.data === ':heartbeat') return
    try {
      onEvent(JSON.parse(e.data))
    } catch {
      // malformed frame — ignore
    }
  }
  if (onError) es.onerror = onError
  return es
}
