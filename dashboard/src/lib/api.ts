// Typed API client for AI-SOC-Brain backend

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  components: Record<string, { status: string; detail?: string }>
  version: string
}

export interface NormalizedEvent {
  event_id: string
  source_type: string
  source_file: string | null
  timestamp: string
  hostname: string | null
  username: string | null
  process_name: string | null
  process_pid: number | null
  event_type: string | null
  severity: string
  raw_data: Record<string, unknown>
  tags: string[]
  ingested_at: string
}

export interface EventsListResponse {
  events: NormalizedEvent[]
  total: number
  offset: number
  limit: number
}

export interface Detection {
  id: string
  detection_id?: string
  rule_id: string
  rule_name: string
  event_id?: string
  matched_event_ids?: string[]
  severity: string
  fired_at?: string
  attack_technique?: string
  attack_tactic?: string
  explanation?: string
  details?: Record<string, unknown>
}

export interface GraphEntity {
  id?: string
  entity_id?: string
  type?: string
  entity_type?: string
  label?: string
  entity_name?: string
  properties?: Record<string, unknown>
  attributes?: Record<string, unknown>
  first_seen?: string
  last_seen?: string
}

export interface GraphEdge {
  id: string
  source_id: string
  target_id: string
  edge_type: string
  properties: Record<string, unknown>
  created_at: string
}

export interface GraphResponse {
  entities: GraphEntity[]
  edges: GraphEdge[]
  entity_count: number
  edge_count: number
}

// Phase 4 graph response (from GET /graph)
export interface Phase4GraphResponse {
  nodes: any[]
  edges: any[]
  attack_paths: any[]
  stats: Record<string, number>
}

export interface IngestJobStatus {
  job_id: string
  status: 'pending' | 'running' | 'complete' | 'error'
  filename: string
  events_processed: number
  events_total: number
  error: string | null
  started_at: string
  completed_at: string | null
}

export interface TimelineItem {
  item_id: string
  item_type: 'event' | 'detection' | 'edge' | 'playbook'
  timestamp: string
  title: string
  severity: string | null
  attack_technique: string | null
  attack_tactic: string | null
  entity_labels: string[]
  raw_id: string
}

export interface TimelineResponse {
  items: TimelineItem[]
  total: number
}

export interface ChatHistoryMessage {
  id: string
  investigation_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface PlaybookStep {
  step_number: number
  title: string
  description: string
  requires_approval: boolean
  evidence_prompt: string | null
}

export interface Playbook {
  playbook_id: string
  name: string
  description: string
  trigger_conditions: string[]
  steps: PlaybookStep[]
  version: string
  is_builtin: boolean
  created_at: string
}

export interface PlaybookStepResult {
  step_number: number
  outcome: 'confirmed' | 'skipped'
  analyst_note: string
  completed_at: string
}

export interface PlaybookRun {
  run_id: string
  playbook_id: string
  investigation_id: string
  status: 'running' | 'completed' | 'cancelled'
  started_at: string
  completed_at: string | null
  steps_completed: PlaybookStepResult[]
  analyst_notes: string
}

export interface PlaybooksListResponse {
  playbooks: Playbook[]
  total: number
}

export interface PlaybookRunsListResponse {
  runs: PlaybookRun[]
  total: number
}

const BASE = ''  // proxied via Vite dev server, or same origin in prod

/** Returns the current API token from localStorage or Vite env fallback. */
function getApiToken(): string {
  if (typeof localStorage !== 'undefined') {
    const stored = localStorage.getItem('api_token')
    if (stored) return stored
  }
  return import.meta.env.VITE_API_TOKEN ?? 'changeme'
}

/** Returns auth headers for every request. */
function authHeaders(): Record<string, string> {
  return { 'Authorization': `Bearer ${getApiToken()}` }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${path}: ${res.status} ${text}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  events: {
    list: (params?: { offset?: number; limit?: number; hostname?: string; severity?: string }) => {
      const q = new URLSearchParams()
      if (params?.offset !== undefined) q.set('offset', String(params.offset))
      if (params?.limit !== undefined) q.set('limit', String(params.limit))
      if (params?.hostname) q.set('hostname', params.hostname)
      if (params?.severity) q.set('severity', params.severity)
      return request<EventsListResponse>(`/api/events?${q}`)
    },
    get: (id: string) => request<NormalizedEvent>(`/api/events/${id}`),
    search: (query: string, limit = 10) =>
      request<{ results: Array<{ event: NormalizedEvent; score: number }> }>(
        `/api/events/search?q=${encodeURIComponent(query)}&limit=${limit}`
      ),
  },

  detections: {
    list: (params?: { limit?: number; severity?: string; page?: number; page_size?: number }) => {
      const q = new URLSearchParams()
      if (params?.limit !== undefined) q.set('limit', String(params.limit))
      if (params?.severity) q.set('severity', params.severity)
      if (params?.page !== undefined) q.set('page', String(params.page))
      if (params?.page_size !== undefined) q.set('page_size', String(params.page_size))
      return request<{ detections: Detection[]; total: number; page?: number; page_size?: number }>(`/api/detect?${q}`)
    },
    run: () => request<{ count: number; detections: Detection[] }>('/api/detect/run', { method: 'POST' }),
  },

  graph: {
    entity: (id: string, depth = 1) =>
      request<GraphResponse>(`/api/graph/entity/${id}?depth=${depth}`),
    entities: (params?: { type?: string; limit?: number }) => {
      const q = new URLSearchParams()
      if (params?.type) q.set('type', params.type)
      if (params?.limit !== undefined) q.set('limit', String(params.limit))
      return request<{ entities: GraphEntity[] }>(`/api/graph/entities?${q}`)
    },
    traverse: (entityId: string, depth = 2) =>
      request<any>(`/api/graph/traverse/${encodeURIComponent(entityId)}?depth=${depth}`),
    caseGraph: (caseId: string) =>
      request<{ case_id: string; entities: GraphEntity[]; edges: any[]; total_entities: number; total_edges: number }>(
        `/api/graph/${encodeURIComponent(caseId)}`
      ),
    global: (limit = 100) =>
      request<{ entities: GraphEntity[]; edges: any[]; total_entities: number; total_edges: number }>(
        `/api/graph/global?limit=${limit}`
      ),
  },

  investigate: (detectionId: string) =>
    request<any>('/api/investigate', {
      method: 'POST',
      body: JSON.stringify({ detection_id: detectionId }),
    }),

  investigateEntity: (entityId: string, entityType = 'process') =>
    request<any>('/api/investigate', {
      method: 'POST',
      body: JSON.stringify({ entity_id: entityId, entity_type: entityType }),
    }),

  correlate: () => request<any>('/api/correlate', { method: 'POST' }),

  ingestEvents: (events: any[]) =>
    request<any>('/api/ingest/events', {
      method: 'POST',
      body: JSON.stringify({ events }),
    }),

  query: {
    ask: async (question: string, context_events?: string[]): Promise<string> => {
      const res = await fetch('/api/query/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ question, context_events }),
      })
      if (!res.ok) throw new Error(`Query failed: ${res.status}`)
      // SSE stream — collect full text
      const reader = res.body?.getReader()
      if (!reader) throw new Error('No response body')
      const decoder = new TextDecoder()
      let text = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        // SSE format: "data: {...}\n\n"
        for (const line of chunk.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const msg = JSON.parse(line.slice(6))
              if (msg.token) text += msg.token
              if (msg.done) break
            } catch { /* skip non-JSON lines */ }
          }
        }
      }
      return text
    },
  },

  ingest: {
    upload: async (file: File): Promise<IngestJobStatus> => {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/ingest/file', { method: 'POST', headers: { ...authHeaders() }, body: form })
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
      return res.json()
    },
    status: (jobId: string) => request<IngestJobStatus>(`/api/ingest/status/${jobId}`),
  },

  metrics: {
    kpis: () => request<KpiSnapshot>('/api/metrics/kpis'),
  },

  playbooks: {
    list: () => request<PlaybooksListResponse>('/api/playbooks'),
    get: (id: string) => request<Playbook>(`/api/playbooks/${id}`),
    runs: (id: string) => request<PlaybookRunsListResponse>(`/api/playbooks/${id}/runs`),
    startRun: (playbookId: string, investigationId: string) =>
      request<PlaybookRun>(`/api/playbooks/${playbookId}/run/${investigationId}`, { method: 'POST' }),
  },

  playbookRuns: {
    get: (runId: string) => request<PlaybookRun>(`/api/playbook-runs/${runId}`),
    advanceStep: (runId: string, stepN: number, body: { analyst_note: string; outcome: 'confirmed' | 'skipped' }) =>
      request<PlaybookRun>(`/api/playbook-runs/${runId}/step/${stepN}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    cancel: (runId: string) =>
      request<PlaybookRun>(`/api/playbook-runs/${runId}/cancel`, { method: 'PATCH' }),
  },

  investigations: {
    timeline: (investigationId: string) =>
      request<TimelineResponse>(`/api/investigations/${investigationId}/timeline`),

    chatHistory: (investigationId: string) =>
      request<{ messages: ChatHistoryMessage[] }>(`/api/investigations/${investigationId}/chat/history`),

    chatStream: async (
      investigationId: string,
      question: string,
      onToken: (token: string) => void,
      onDone: () => void,
      signal?: AbortSignal,
    ): Promise<void> => {
      const res = await fetch(`/api/investigations/${investigationId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ question }),
        signal,
      })
      if (!res.ok) throw new Error(`Chat failed: ${res.status}`)
      const reader = res.body?.getReader()
      if (!reader) throw new Error('No response body')
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        for (const line of chunk.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const msg = JSON.parse(line.slice(6))
              if (msg.token) onToken(msg.token)
              if (msg.done) { onDone(); return }
            } catch { /* skip */ }
          }
        }
      }
      onDone()
    },
  },
}

// Phase 4: direct graph helpers (bypass /api prefix — backend graph routes at /graph)
export async function getGraph(): Promise<Phase4GraphResponse> {
  const r = await fetch(`${BASE}/graph`, { headers: authHeaders() })
  return r.json()
}

export async function getGraphCorrelate(eventId: string): Promise<any> {
  const r = await fetch(`${BASE}/graph/correlate?event_id=${encodeURIComponent(eventId)}`, { headers: authHeaders() })
  return r.json()
}

// --- Phase 9: Intelligence & Analyst Augmentation ---

export interface ScoreRequest {
  detection_id?: string;
  event_ids?: string[];
}

export interface ScoreResponse {
  scored_entities: Record<string, number>;
  top_entity: string | null;
  top_score: number;
}

export interface ThreatItem {
  id: string;
  rule_name: string;
  severity: string;
  risk_score: number;
  attack_technique: string | null;
  attack_tactic: string | null;
}

export interface TopThreatsResponse {
  threats: ThreatItem[];
  total: number;
}

export interface ExplainRequest {
  detection_id?: string;
  investigation?: Record<string, unknown>;
}

export interface ExplainResponse {
  what_happened: string;
  why_it_matters: string;
  recommended_next_steps: string;
  evidence_context: string;
  error?: string;
}

export interface SavedInvestigation {
  id: string;
  detection_id: string;
  graph_snapshot: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface KpiValue {
  label: string
  value: number
  unit: string
  trend: 'up' | 'down' | 'flat'
}

export interface KpiSnapshot {
  computed_at: string
  mttd: KpiValue
  mttr: KpiValue
  mttc: KpiValue
  false_positive_rate: KpiValue
  alert_volume_24h: KpiValue
  active_rules: KpiValue
  open_cases: KpiValue
  assets_monitored: KpiValue
  log_sources: KpiValue
}

export async function score(request: ScoreRequest): Promise<ScoreResponse> {
  const resp = await fetch('/api/score', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(request),
  });
  if (!resp.ok) throw new Error(`score: HTTP ${resp.status}`);
  return resp.json();
}

export async function topThreats(limit = 10): Promise<TopThreatsResponse> {
  const resp = await fetch(`/api/top-threats?limit=${limit}`, { headers: authHeaders() });
  if (!resp.ok) throw new Error(`topThreats: HTTP ${resp.status}`);
  return resp.json();
}

export async function explain(request: ExplainRequest): Promise<ExplainResponse> {
  const resp = await fetch('/api/explain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(request),
  });
  if (!resp.ok) throw new Error(`explain: HTTP ${resp.status}`);
  return resp.json();
}

export async function saveInvestigation(
  detectionId: string,
  graphSnapshot: Record<string, unknown>,
  metadata: Record<string, unknown> = {},
): Promise<SavedInvestigation> {
  const resp = await fetch('/api/investigations/saved', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      detection_id: detectionId,
      graph_snapshot: graphSnapshot,
      metadata,
    }),
  });
  if (!resp.ok) throw new Error(`saveInvestigation: HTTP ${resp.status}`);
  return resp.json();
}
