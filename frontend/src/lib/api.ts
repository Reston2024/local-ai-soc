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

// --- Phase 6: Causality Engine ---

export interface CausalityGraphNode {
  id: string
  type: string
  label: string
  attributes: Record<string, unknown>
  first_seen: string
  last_seen: string
  evidence: string[]
}

export interface CausalityGraphEdge {
  id: string
  type: string
  src: string   // NOTE: src not source
  dst: string   // NOTE: dst not target
  timestamp: string
  evidence_event_ids: string[]
}

export interface AttackPath {
  id: string
  node_ids: string[]
  edge_ids: string[]
  severity: string
  first_event: string
  last_event: string
}

export interface MitreTechnique {
  technique: string
  tactic: string
  name: string
}

export interface CausalityGraphResponse {
  alert_id: string
  nodes: CausalityGraphNode[]
  edges: CausalityGraphEdge[]
  attack_paths: AttackPath[]
  chain: Record<string, unknown>[]
  techniques: MitreTechnique[]
  score: number
  first_event: string
  last_event: string
}

export interface InvestigationQueryRequest {
  q?: string
  entity_id?: string | null
  technique?: string | null
  severity?: string | null
  limit?: number
  offset?: number
}

export interface InvestigationQueryResponse {
  nodes: CausalityGraphNode[]
  edges: CausalityGraphEdge[]
  total: number
  limit: number
  offset: number
}

export interface InvestigationSummaryResponse {
  alert_id: string
  summary: string
  techniques: MitreTechnique[]
  score: number
}

// NOTE: All causality endpoints use /api/ prefix (per CONTEXT.md locked decision)

export async function getAttackGraph(
  alertId: string,
  opts?: { from?: string; to?: string }
): Promise<CausalityGraphResponse> {
  const params = new URLSearchParams()
  if (opts?.from) params.set('from', opts.from)
  if (opts?.to) params.set('to', opts.to)
  const qs = params.toString() ? `?${params.toString()}` : ''
  const r = await fetch(`/api/graph/${encodeURIComponent(alertId)}${qs}`)
  return r.json()
}

export async function getAttackChain(alertId: string): Promise<CausalityGraphResponse> {
  const r = await fetch(`/api/attack_chain/${encodeURIComponent(alertId)}`)
  return r.json()
}

export async function investigationQuery(
  params: InvestigationQueryRequest
): Promise<InvestigationQueryResponse> {
  const r = await fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return r.json()
}

export async function getInvestigationSummary(
  alertId: string
): Promise<InvestigationSummaryResponse> {
  const r = await fetch(`/api/investigate/${encodeURIComponent(alertId)}/summary`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  return r.json()
}
