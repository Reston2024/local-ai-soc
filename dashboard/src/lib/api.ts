// Typed API client for AI-SOC-Brain backend

export interface HayabusaHealth {
  status: 'ok' | 'warning'
  binary: string | null
  detection_count: number
  detail?: string | null
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  components: Record<string, { status: string; detail?: string; [key: string]: unknown }>
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
  process_id: number | null
  event_type: string | null
  severity: string
  raw_event: string | null
  tags: string[]
  ingested_at: string
}

export interface EventsListResponse {
  events: NormalizedEvent[]
  total: number
  page: number
  page_size: number
  has_next: boolean
}

// ---------------------------------------------------------------------------
// Phase 40 — Atomic Red Team interfaces
// ---------------------------------------------------------------------------

export interface AtomicTest {
  test_number: number
  test_name: string
  supported_platforms: string[]
  executor_name: string
  elevation_required: boolean
  command: string
  cleanup_command: string
  prereq_command: string
  invoke_command: string
  invoke_prereq: string
  invoke_cleanup: string
  validation: { verdict: 'pass' | 'fail'; validated_at: string } | null
}

export interface AtomicTechnique {
  technique_id: string
  display_name: string
  coverage: 'validated' | 'detected' | 'none'
  tests: AtomicTest[]
}

export interface AtomicsResponse {
  techniques: AtomicTechnique[]
  total_techniques: number
  total_tests: number
}

export interface ValidationResult {
  verdict: 'pass' | 'fail'
  detection_id: string | null
  checked_at: string
}

// ---------------------------------------------------------------------------
// Phase 39 — MITRE CAR Analytics interface
// ---------------------------------------------------------------------------

export interface CARAnalytic {
  analytic_id: string
  technique_id: string
  title: string
  description: string
  log_sources: string
  analyst_notes: string
  pseudocode: string
  coverage_level: string
  platforms: string
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
  created_at?: string
  src_ip?: string | null
  attack_technique?: string
  attack_tactic?: string
  explanation?: string
  details?: Record<string, unknown>
  car_analytics?: CARAnalytic[] | null
  correlation_type?: string       // 'PORT_SCAN' | 'BRUTE_FORCE' | 'BEACON' | 'CHAIN'
  matched_event_count?: number    // convenience count for row badge
  verdict?: string | null         // Phase 44: 'TP' | 'FP' | null
  detection_source?: string | null  // Phase 48/49: 'sigma' | 'hayabusa' | 'chainsaw' | 'correlation' | null
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
  confidence?: number        // P22-T02: heuristic confidence score 0.0–1.0
  audit_id?: string          // P22-T01: LLM audit provenance ID
  grounding_event_ids?: string[]  // P22-T01: event IDs used as grounding context
  is_grounded?: boolean           // P22-T01: whether response is grounded in retrieved evidence
}

export interface PlaybookStep {
  step_number: number
  title: string
  description: string
  requires_approval: boolean
  evidence_prompt: string | null
  // Phase 38 additions
  attack_techniques: string[]
  escalation_threshold: 'critical' | 'high' | null
  escalation_role: string | null
  time_sla_minutes: number | null
  containment_actions: string[]
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
  source: 'cisa' | 'cert_sg' | 'aws' | 'microsoft' | 'guardsight' | 'community' | 'custom'  // Phase 46 expansion
  category: string  // Phase 46: malware|ransomware|phishing|identity|network|cloud|insider|supply_chain|web|endpoint|data_breach|ics_ot|vulnerability
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
  active_case_id: string | null  // Phase 38: set on escalation acknowledge
}

export interface PlaybooksListResponse {
  playbooks: Playbook[]
  total: number
}

export interface PlaybookRunsListResponse {
  runs: PlaybookRun[]
  total: number
}

export interface Report {
  id: string
  type: string
  title: string
  subject_id: string | null
  period_start: string | null
  period_end: string | null
  created_at: string
}

export interface ReportsListResponse {
  reports: Report[]
}

export interface TemplateMeta {
  investigations: number
  closed_cases: number
  playbook_runs: number
  actors: number
  actor_list: Array<{ name: string; group_id: string }>
  case_list: Array<{ case_id: string; title: string; case_status: string }>
  run_list: Array<{ run_id: string; playbook_id: string; status: string; started_at: string }>
}

export interface MitreTechniqueEntry {
  sources: string[]   // e.g. ["detected", "playbook_covered"]
  status: string      // "detected" | "hunted" | "playbook_covered" | "not_covered"
}

export interface MitreCoverageResponse {
  tactics: string[]
  coverage: Record<string, Record<string, MitreTechniqueEntry>>
}

export interface TrendDataPoint {
  date: string   // "YYYY-MM-DD"
  value: number
}

export type TrendsResponse = Record<string, TrendDataPoint[]>

// ---------------------------------------------------------------------------
// Phase 35 — Overview dashboard + triage interfaces
// ---------------------------------------------------------------------------

export interface TelemetrySummary {
  event_type_counts: Record<string, number>
  total_events: number
  total_detections: number
  ioc_matches: number
  assets_count: number
  top_rules: Array<{ rule_name: string; severity: string; count: number }>
}

export interface TriageResult {
  run_id: string
  severity_summary: string
  result_text: string
  detection_count: number
  model_name: string
  created_at: string
}

export interface TriageRunResult {
  run_id?: string
  severity_summary?: string
  detection_count: number
  model_name?: string
  created_at?: string
  message?: string
}

// ---------------------------------------------------------------------------
// Phase 34 — Asset Inventory + ATT&CK Coverage interfaces
// ---------------------------------------------------------------------------

export interface Asset {
  ip: string
  hostname: string | null
  tag: "internal" | "external"
  risk_score: number
  last_seen: string
  first_seen: string
  alert_count: number
}

export interface TacticCoverage {
  tactic: string
  tactic_short: string
  total_techniques: number
  covered_count: number
  techniques: Array<{
    tech_id: string
    name: string
    covered: boolean
    rule_titles: string[]
  }>
}

export interface ActorMatch {
  name: string
  aliases: string[]
  group_id: string
  overlap_pct: number
  confidence: "High" | "Medium" | "Low"
  matched_count: number
  total_count: number
}

// ---------------------------------------------------------------------------
// Phase 33 — Threat Intelligence interfaces
// ---------------------------------------------------------------------------

export interface IocHit {
  id: number;
  event_timestamp: string;
  hostname: string | null;
  src_ip: string | null;
  dst_ip: string | null;
  ioc_value: string;
  ioc_type: string;
  ioc_source: string;
  risk_score: number;
  actor_tag: string | null;
  malware_family: string | null;
  matched_at: string;
  extra_json?: string | null;  // present when ioc_source='misp' — JSON context
}

export interface FeedStatus {
  feed: 'feodo' | 'cisa_kev' | 'threatfox' | 'misp' | string;
  last_sync: string | null;
  ioc_count: number;
  status: 'ok' | 'stale' | 'never' | 'error';
}

export interface MispIoc {
  ioc_value: string;
  ioc_type: string;
  confidence: number;
  feed_source: string;
  actor_tag: string | null;
  malware_family: string | null;
  extra_json: string | null;   // JSON string: {misp_event_id, misp_tags, misp_category, misp_comment}
  last_seen: string | null;
  first_seen: string | null;
}

// ---------------------------------------------------------------------------
// Phase 32 — Hunting + OSINT interfaces
// ---------------------------------------------------------------------------

export interface HuntPreset {
  id: string
  name: string
  mitre: string
  desc: string
  query: string
}

export interface HuntRow {
  event_id?: string
  ts?: string
  hostname?: string
  severity?: string
  event_type?: string
  src_ip?: string
  dst_ip?: string
  dst_port?: number
  process_name?: string
  user_name?: string
  [key: string]: unknown
}

export interface HuntResult {
  hunt_id: string
  query: string
  sql: string
  rows: HuntRow[]
  row_count: number
  created_at: string
}

export interface HuntHistoryItem {
  hunt_id: string
  query: string
  sql_text: string
  row_count: number
  analyst_id: string
  created_at: string
}

export interface OsintWhois {
  registrar?: string | null
  creation_date?: string | null
  country?: string | null
  org?: string | null
}

export interface OsintAbuseIPDB {
  abuseConfidenceScore?: number
  totalReports?: number
  countryCode?: string
  isp?: string
}

export interface OsintGeo {
  country_name?: string | null
  country_iso_code?: string | null
  city?: string | null
  latitude?: number | null
  longitude?: number | null
  autonomous_system_number?: number | null
  autonomous_system_organization?: string | null
}

export interface OsintVirusTotal {
  malicious?: number
  suspicious?: number
  harmless?: number
  country?: string
  reputation?: number
}

export interface OsintShodan {
  org?: string
  isp?: string
  country_name?: string
  open_ports?: number[]
  hostnames?: string[]
}

export interface OsintResult {
  ip: string
  whois: OsintWhois | null
  abuseipdb: OsintAbuseIPDB | null
  geo: OsintGeo | null
  virustotal: OsintVirusTotal | null
  shodan: OsintShodan | null
  cached: boolean
  fetched_at: string
}

// ---------------------------------------------------------------------------
// Provenance interfaces (Phase 21-05)
// ---------------------------------------------------------------------------

export interface IngestProvenanceRecord {
  prov_id: string
  raw_sha256: string
  source_file: string
  parser_name: string
  parser_version?: string
  operator_id?: string
  ingested_at: string
}

export interface DetectionProvenanceRecord {
  prov_id: string
  detection_id: string
  rule_id?: string
  rule_title?: string
  rule_sha256: string
  pysigma_version: string
  field_map_version: string
  operator_id?: string
  detected_at: string
}

export interface LlmProvenanceRecord {
  audit_id: string
  model_id: string
  prompt_template_name?: string
  prompt_template_sha256?: string
  response_sha256?: string
  operator_id?: string
  grounding_event_ids: string[]
  created_at: string
}

export interface PlaybookProvenanceRecord {
  prov_id: string
  run_id: string
  playbook_id?: string
  playbook_file_sha256: string
  playbook_version?: string
  trigger_event_ids: string[]
  operator_id_who_approved?: string
  created_at: string
}

// ---------------------------------------------------------------------------
// Model drift status interface (Phase 22-04)
// ---------------------------------------------------------------------------

export interface ModelStatus {
  active_model: string | null
  last_known_model: string | null
  drift_detected: boolean
  last_change: {
    event_id: string
    detected_at: string
    previous_model: string | null
    active_model: string
    change_source: string
  } | null
}

// ---------------------------------------------------------------------------
// Operator management interfaces (Phase 19-04)
// ---------------------------------------------------------------------------

export interface Operator {
  operator_id: string
  username: string
  role: 'admin' | 'analyst'
  is_active: boolean
  created_at: string
  last_seen_at: string | null
}

export interface OperatorCreateResponse {
  operator_id: string
  username: string
  role: string
  api_key: string   // one-time display
  created_at: string
}

export interface OperatorRotateResponse {
  operator_id: string
  api_key: string   // one-time display
}

// ---------------------------------------------------------------------------
// Phase 42 — Anomaly scoring interfaces
// ---------------------------------------------------------------------------

export interface AnomalyEvent {
  event_id: string
  timestamp: string
  hostname: string | null
  process_name: string | null
  src_ip: string | null
  event_type: string | null
  severity: string
  anomaly_score: number
}

export interface AnomalyListResponse {
  anomalies: AnomalyEvent[]
  total: number
}

export interface ScorePoint {
  timestamp: string
  score: number
}

export interface EntityProfile {
  entity_key: string
  event_count: number
  avg_score: number
  max_score: number
  scores: ScorePoint[]
}

export interface ScoreTrendResponse {
  trend: ScorePoint[]
  entity_key: string
}

// ---------------------------------------------------------------------------
// Phase 41 — Threat Map interfaces
// ---------------------------------------------------------------------------

export interface MapIpInfo {
  lat: number | null
  lon: number | null
  country: string | null
  country_iso: string | null
  city: string | null
  asn: string | null
  ip_type: 'tor' | 'vpn' | 'datacenter' | 'residential' | 'isp' | null
  ipsum_tier: number | null
  is_tor: boolean
  is_proxy: boolean
  is_datacenter: boolean
}

export interface MapFlow {
  src_ip: string
  dst_ip: string
  conn_count: number
  direction: 'inbound' | 'outbound' | 'lateral'
}

export interface MapStats {
  total_ips: number
  tor_count: number
  vpn_count: number
  datacenter_count: number
  top_src_country: string | null
  top_src_country_conn_count: number
  flow_count: number
}

export interface MapData {
  flows: MapFlow[]
  ips: Record<string, MapIpInfo>
  stats: MapStats
  home_lat: number | null
  home_lon: number | null
}

// ── Phase 51: OSINT Investigation ──────────────────────────────────────────

export interface OsintJob {
  job_id: string
  status: 'RUNNING' | 'FINISHED' | 'ERROR-FAILED' | 'ABORTED' | 'TIMEOUT'
  target: string
  usecase: string
  started_at: string
  completed_at?: string
  error?: string
}

export interface OsintFinding {
  id: number
  investigation_id: string
  event_type: string
  data: string
  source_module?: string
  confidence: number
  created_at: string
  misp_hit: number          // 1 if matches MISP ioc_store
  misp_event_ids: string    // JSON string of event source tags
}

export interface OsintInvestigationDetail extends OsintJob {
  findings: OsintFinding[]
  findings_by_type: Record<string, OsintFinding[]>
  findings_count: number
  dnstwist_findings?: Record<string, DnsTwistLookalike[]>
}

export interface DnsTwistLookalike {
  fuzzer: string
  domain?: string           // raw dnstwist library field (standalone /dnstwist endpoint)
  lookalike_domain?: string // SQLite row field (from GET /investigate/{job_id})
  dns_a?: string
  dns_ns?: string
  dns_mx?: string
  whois_registrar?: string
  whois_created?: string
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

/** Build a download URL that includes the Bearer token as a query param.
 *  Used for binary endpoints (PDF, ZIP) that the browser opens directly
 *  rather than being fetched via the request() helper. */
export function getDownloadUrl(path: string): string {
  const token = getApiToken()
  const sep = path.includes('?') ? '&' : '?'
  return `${BASE}${path}${sep}token=${encodeURIComponent(token)}`
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
    list: (params?: { offset?: number; limit?: number; hostname?: string; severity?: string; event_type?: string }) => {
      const q = new URLSearchParams()
      const limit = params?.limit ?? 50
      const offset = params?.offset ?? 0
      const page = Math.floor(offset / limit) + 1
      q.set('page', String(page))
      q.set('page_size', String(limit))
      if (params?.hostname) q.set('hostname', params.hostname)
      if (params?.severity) q.set('severity', params.severity)
      if (params?.event_type) q.set('event_type', params.event_type)   // Phase 31
      return request<EventsListResponse>(`/api/events?${q}`)
    },
    get: (id: string) => request<NormalizedEvent>(`/api/events/${id}`),
    search: (query: string, limit = 10) =>
      request<{ events: NormalizedEvent[]; total: number; query: string }>(
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
      const res = await fetch('/api/query/ask/stream', {
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
    perf: () => request<PerfMetrics>('/api/metrics/perf'),
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
    patchRun: (runId: string, body: { active_case_id?: string | null }) =>
      request<PlaybookRun>(`/api/playbook-runs/${runId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
  },

  reports: {
    list: () =>
      request<ReportsListResponse>('/api/reports'),

    generateInvestigation: (investigationId: string, opts?: { include_chat?: boolean; include_playbook_runs?: boolean }) =>
      request<Report>(`/api/reports/investigation/${encodeURIComponent(investigationId)}`, {
        method: 'POST',
        body: JSON.stringify({ include_chat: opts?.include_chat ?? true, include_playbook_runs: opts?.include_playbook_runs ?? true }),
      }),

    generateExecutive: (opts: { period_start: string; period_end: string; title?: string }) =>
      request<Report>('/api/reports/executive', {
        method: 'POST',
        body: JSON.stringify({ period_start: opts.period_start, period_end: opts.period_end, title: opts.title ?? 'Executive Security Summary' }),
      }),

    /** Returns a URL to open directly in a browser tab — uses getDownloadUrl for auth token injection. */
    pdfUrl: (reportId: string) => getDownloadUrl(`/api/reports/${encodeURIComponent(reportId)}/pdf`),

    /** Returns a URL for ZIP download — uses getDownloadUrl for auth token injection. */
    complianceDownloadUrl: (framework: 'nist-csf' | 'thehive') =>
      getDownloadUrl(`/api/reports/compliance?framework=${framework}`),

    templateMeta: () =>
      request<TemplateMeta>('/api/reports/template/meta'),

    generateTemplate: (type: string, params?: Record<string, string>) => {
      const typeToPath: Record<string, string> = {
        template_session_log: '/api/reports/template/session-log',
        template_incident: `/api/reports/template/incident/${encodeURIComponent(params?.case_id ?? '')}`,
        template_playbook_log: `/api/reports/template/playbook-log/${encodeURIComponent(params?.run_id ?? '')}`,
        template_pir: `/api/reports/template/pir/${encodeURIComponent(params?.case_id ?? '')}`,
        template_ti_bulletin: '/api/reports/template/ti-bulletin',
        template_severity_ref: '/api/reports/template/severity-ref',
      }
      const path = typeToPath[type] ?? '/api/reports/template/session-log'
      const body = type === 'template_ti_bulletin' ? JSON.stringify({ actor_name: params?.actor_name ?? '' }) : undefined
      return request<Report>(path, { method: 'POST', body })
    },
  },

  analytics: {
    mitreCoverage: () =>
      request<MitreCoverageResponse>('/api/analytics/mitre-coverage'),

    trends: (params: { metric: string; days?: number }) => {
      const q = new URLSearchParams()
      q.set('metric', params.metric)
      if (params.days !== undefined) q.set('days', String(params.days))
      return request<TrendsResponse>(`/api/analytics/trends?${q}`)
    },
  },

  investigations: {
    timeline: (investigationId: string) =>
      request<TimelineResponse>(`/api/investigations/${investigationId}/timeline`),

    chatHistory: (investigationId: string) =>
      request<{ messages: ChatHistoryMessage[] }>(`/api/investigations/${investigationId}/chat/history`),

    runAgentic: async (
      detectionId: string,
      onStep: (step: AgentStep) => void,
      onReasoning: (text: string) => void,
      onVerdict: (verdict: AgentVerdict) => void,
      onLimit: (reason: string) => void,
      onDone: () => void,
      onError: (message: string) => void,
      signal?: AbortSignal,
    ): Promise<void> => {
      const res = await fetch('/api/investigate/agentic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ detection_id: detectionId }),
        signal,
      })
      if (!res.ok) {
        onError(`Agent request failed: ${res.status}`)
        return
      }
      const reader = res.body?.getReader()
      if (!reader) { onError('No response body'); return }
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line.startsWith('event: ')) continue
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw || raw === '{}') continue
          try {
            const parsed = JSON.parse(raw)
            // Dispatch based on data shape — each event type has a unique key
            if ('call_number' in parsed && 'tool_name' in parsed) {
              onStep(parsed as AgentStep)
            } else if ('text' in parsed) {
              // Filter out reasoning chunks that are just the verdict JSON — the model
              // often emits the verdict as plain text before calling final_answer.
              // These will be captured via the proper 'verdict' event instead.
              const txt: string = parsed.text || ''
              const looksLikeVerdict = txt.includes('"verdict"') && (txt.includes('"TP"') || txt.includes('"FP"'))
              if (!looksLikeVerdict) onReasoning(txt)
            } else if ('verdict' in parsed) {
              onVerdict(parsed as AgentVerdict)
            } else if ('reason' in parsed) {
              onLimit(parsed.reason)
            } else if ('message' in parsed) {
              onError(parsed.message)
            }
          } catch { /* skip malformed */ }
        }
      }
      onDone()
    },

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

  provenance: {
    recent: (limit = 20) =>
      request<{ records: Array<{ record_id: string; record_type: string; label: string; created_at: string }> }>(
        `/api/provenance/recent?limit=${limit}`,
        { headers: authHeaders() },
      ),
    ingest: (eventId: string) =>
      request<IngestProvenanceRecord>(`/api/provenance/ingest/${encodeURIComponent(eventId)}`, { headers: authHeaders() }),
    detection: (detectionId: string) =>
      request<DetectionProvenanceRecord>(`/api/provenance/detection/${encodeURIComponent(detectionId)}`, { headers: authHeaders() }),
    llm: (auditId: string) =>
      request<LlmProvenanceRecord>(`/api/provenance/llm/${encodeURIComponent(auditId)}`, { headers: authHeaders() }),
    playbook: (runId: string) =>
      request<PlaybookProvenanceRecord>(`/api/provenance/playbook/${encodeURIComponent(runId)}`, { headers: authHeaders() }),
  },

  recommendations: {
    list: (params?: { status?: string; case_id?: string; limit?: number; offset?: number }) => {
      const q = new URLSearchParams()
      if (params?.status) q.set('status', params.status)
      if (params?.case_id) q.set('case_id', params.case_id)
      if (params?.limit !== undefined) q.set('limit', String(params.limit))
      if (params?.offset !== undefined) q.set('offset', String(params.offset))
      return request<RecommendationsListResponse>(`/api/recommendations?${q}`)
    },
    get: (id: string) => request<RecommendationItem>(`/api/recommendations/${encodeURIComponent(id)}`),
    dispatch: (id: string) => dispatchRecommendation(id),
  },

  settings: {
    operators: {
      list: () =>
        request<{ operators: Operator[] }>('/api/operators'),

      create: (body: { username: string; role: string }) =>
        request<OperatorCreateResponse>('/api/operators', {
          method: 'POST',
          body: JSON.stringify(body),
        }),

      deactivate: (operatorId: string) =>
        request<void>(`/api/operators/${encodeURIComponent(operatorId)}`, {
          method: 'DELETE',
        }),

      rotateKey: (operatorId: string) =>
        request<OperatorRotateResponse>(
          `/api/operators/${encodeURIComponent(operatorId)}/rotate-key`,
          { method: 'POST' },
        ),

      enableTotp: (operatorId: string) =>
        request<{ qr_code: string; provisioning_uri: string }>(
          `/api/operators/${encodeURIComponent(operatorId)}/totp/enable`,
          { method: 'POST' },
        ),

      disableTotp: (operatorId: string) =>
        request<void>(
          `/api/operators/${encodeURIComponent(operatorId)}/totp`,
          { method: 'DELETE' },
        ),
    },

    modelStatus: (): Promise<ModelStatus> =>
      request<ModelStatus>('/api/settings/model-status'),
  },

  hunts: {
    query: (query: string, analyst_id = 'analyst') =>
      request<HuntResult>('/api/hunts/query', {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, analyst_id }),
      }),
    presets: () =>
      request<{ presets: HuntPreset[] }>('/api/hunts/presets', { headers: authHeaders() }),
    getResults: (hunt_id: string) =>
      request<HuntHistoryItem>(`/api/hunts/${hunt_id}/results`, { headers: authHeaders() }),
    history: (limit = 20) =>
      request<{ hunts: HuntHistoryItem[] }>(`/api/hunts/history?limit=${limit}`, { headers: authHeaders() }),
  },

  osint: {
    get: (ip: string) =>
      request<OsintResult>(`/api/osint/${ip}`, { headers: authHeaders() }),

    startInvestigation: async (target: string, usecase: string = 'passive'): Promise<OsintJob> => {
      const r = await fetch('/api/osint/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ target, usecase }),
      })
      if (!r.ok) throw new Error(await r.text())
      return r.json()
    },

    getInvestigation: async (jobId: string): Promise<OsintInvestigationDetail> => {
      const r = await fetch(`/api/osint/investigate/${encodeURIComponent(jobId)}`, { headers: authHeaders() })
      if (!r.ok) throw new Error(await r.text())
      return r.json()
    },

    listInvestigations: async (): Promise<{ investigations: OsintJob[] }> => {
      const r = await fetch('/api/osint/investigations', { headers: authHeaders() })
      if (!r.ok) throw new Error(await r.text())
      return r.json()
    },

    cancelInvestigation: async (jobId: string): Promise<void> => {
      await fetch(`/api/osint/investigate/${encodeURIComponent(jobId)}`, { method: 'DELETE', headers: authHeaders() })
    },

    runDnsTwist: async (domain: string): Promise<{ domain: string; lookalikes: DnsTwistLookalike[] }> => {
      const r = await fetch('/api/osint/dnstwist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ domain }),
      })
      if (!r.ok) throw new Error(await r.text())
      return r.json()
    },
  },

  intel: {
    iocHits: async (limit = 200): Promise<IocHit[]> => {
      const res = await fetch(`${BASE}/api/intel/ioc-hits?limit=${limit}`, {
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    feeds: async (): Promise<FeedStatus[]> => {
      const res = await fetch(`${BASE}/api/intel/feeds`, {
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    mispEvents: async (limit = 50): Promise<MispIoc[]> => {
      const res = await fetch(`${BASE}/api/intel/misp-events?limit=${limit}`, {
        headers: authHeaders(),
      });
      if (!res.ok) return [];
      return res.json();
    },
  },

  assets: {
    list: (limit = 200): Promise<Asset[]> =>
      request<Asset[]>(`/api/assets?limit=${limit}`),

    get: (ip: string): Promise<Asset> =>
      request<Asset>(`/api/assets/${encodeURIComponent(ip)}`),

    tag: (ip: string, tag: string): Promise<void> =>
      request<void>(`/api/assets/${encodeURIComponent(ip)}/tag`, {
        method: 'POST',
        body: JSON.stringify({ tag }),
      }),
  },

  attack: {
    coverage: (): Promise<TacticCoverage[]> =>
      request<TacticCoverage[]>('/api/attack/coverage'),

    actorMatches: (): Promise<ActorMatch[]> =>
      request<ActorMatch[]>('/api/attack/actor-matches'),
  },

  atomics: {
    list: () => request<AtomicsResponse>('/api/atomics'),
    validate: (technique_id: string, test_number: number) =>
      request<ValidationResult>('/api/atomics/validate', {
        method: 'POST',
        body: JSON.stringify({ technique_id, test_number }),
      }),
  },

  telemetry: {
    summary: (): Promise<TelemetrySummary> =>
      request<TelemetrySummary>('/api/telemetry/summary'),
  },

  triage: {
    latest: (): Promise<{ result: TriageResult | null }> =>
      request<{ result: TriageResult | null }>('/api/triage/latest'),
    run: (): Promise<TriageRunResult> =>
      request<TriageRunResult>('/api/triage/run', { method: 'POST' }),
  },

  map: {
    getData: (window: string = '24h'): Promise<MapData> =>
      request<MapData>(`/api/map/data?window=${window}`),
  },

  anomaly: {
    list: (minScore = 0.5, limit = 100) =>
      request<AnomalyListResponse>(`/api/anomaly?min_score=${minScore}&limit=${limit}`),
    entityProfile: (subnet: string, process: string) =>
      request<EntityProfile>(
        `/api/anomaly/entity?subnet=${encodeURIComponent(subnet)}&process=${encodeURIComponent(process)}`
      ),
    trend: (entityKey: string, hours = 24) =>
      request<ScoreTrendResponse>(
        `/api/anomaly/trend?entity_key=${encodeURIComponent(entityKey)}&hours=${hours}`
      ),
  },

  feedback: {
    submit: (req: FeedbackRequest): Promise<FeedbackResponse> =>
      request<FeedbackResponse>('/api/feedback', { method: 'POST', body: JSON.stringify(req) }),
    similar: (detection_id: string, rule_id?: string, rule_name?: string): Promise<SimilarCasesResponse> => {
      const params = new URLSearchParams({ detection_id })
      if (rule_id) params.set('rule_id', rule_id)
      if (rule_name) params.set('rule_name', rule_name)
      return request<SimilarCasesResponse>(`/api/feedback/similar?${params}`)
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

// ---------------------------------------------------------------------------
// Phase 47 — Performance gauge interfaces
// ---------------------------------------------------------------------------

export interface SocBrainPerf {
  cpu_pct: number
  ram_pct: number
  disk_pct: number
  ram_detail: string
  disk_detail: string
}

export interface GmktecPerf {
  cpu_pct: number | null
  heap_pct: number | null
  disk_pct: number | null
  heap_detail: string | null
  disk_detail: string | null
}

export interface PerfMetrics {
  soc_brain: SocBrainPerf
  gmktec: GmktecPerf
  timestamp: string
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
  // Phase 44 feedback fields
  verdicts_given?: number
  tp_rate?: number
  fp_rate?: number
  classifier_accuracy?: number | null
  training_samples?: number
}

// ---------------------------------------------------------------------------
// Phase 44 — Analyst feedback interfaces
// ---------------------------------------------------------------------------

export interface FeedbackRequest {
  detection_id: string
  verdict: 'TP' | 'FP'
  rule_id?: string
  rule_name?: string
  severity?: number
}

export interface FeedbackResponse {
  ok: boolean
  verdict: string
}

export interface SimilarCase {
  detection_id: string
  verdict: 'TP' | 'FP'
  rule_name: string | null
  similarity_pct: number
  summary: string | null
}

export interface SimilarCasesResponse {
  cases: SimilarCase[]
}

// ---------------------------------------------------------------------------
// Phase 45 — Agentic Investigation interfaces
// ---------------------------------------------------------------------------

export interface AgentStep {
  call_number: number
  tool_name: string
  arguments: Record<string, unknown>
  result: string
}

export interface AgentReasoning {
  text: string
}

export interface AgentVerdict {
  verdict: 'TP' | 'FP'
  confidence: number   // 0-100
  narrative: string
}

export interface AgentLimit {
  reason: 'timeout' | 'max_calls'
}

export interface AgentRunResult {
  steps: AgentStep[]
  reasoningChunks: string[]
  verdict: AgentVerdict | null
  limitReason: string | null
  error: string | null
}

// ---------------------------------------------------------------------------
// Recommendation dispatch (Phase 27-04)
// ---------------------------------------------------------------------------

export interface RecommendationItem {
  recommendation_id: string
  case_id: string
  type: string
  proposed_action: string
  target: string
  scope: string
  rationale: string[]
  inference_confidence: string
  model_id: string
  status: string
  analyst_approved: boolean
  approved_by: string
  generated_at: string
  expires_at: string
  created_at: string
}

export interface RecommendationsListResponse {
  items: RecommendationItem[]
  total: number
}

export interface DispatchResult {
  dispatched: boolean
  recommendation_id: string
  artifact_type: string
}

export async function dispatchRecommendation(id: string): Promise<DispatchResult> {
  const res = await fetch(`/api/recommendations/${encodeURIComponent(id)}/dispatch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? body.error ?? `dispatch failed: ${res.status}`)
  }
  return res.json()
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
