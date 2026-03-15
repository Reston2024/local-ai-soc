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
  rule_id: string
  rule_name: string
  event_id: string
  severity: string
  fired_at: string
  details: Record<string, unknown>
}

export interface GraphEntity {
  id: string
  type: string
  label: string
  properties: Record<string, unknown>
  first_seen: string
  last_seen: string
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

const BASE = ''  // proxied via Vite dev server, or same origin in prod

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
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
    list: (params?: { limit?: number; severity?: string }) => {
      const q = new URLSearchParams()
      if (params?.limit !== undefined) q.set('limit', String(params.limit))
      if (params?.severity) q.set('severity', params.severity)
      return request<{ detections: Detection[]; total: number }>(`/api/detections?${q}`)
    },
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
  },

  query: {
    ask: async (question: string, context_events?: string[]): Promise<string> => {
      const res = await fetch('/api/query/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      const res = await fetch('/api/ingest/upload', { method: 'POST', body: form })
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
      return res.json()
    },
    status: (jobId: string) => request<IngestJobStatus>(`/api/ingest/status/${jobId}`),
  },
}
