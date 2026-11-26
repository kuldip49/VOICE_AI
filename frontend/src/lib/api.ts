// Typed client for the FastAPI backend. All requests go to /api (proxied by Vite in dev).
// The optional admin key is entered by the operator in Settings and kept in localStorage —
// no secret is ever bundled into the frontend build.

export type Category = 'HOT' | 'WARM' | 'COLD'
export interface Source { chunk_id: number; document: string; title: string; score: number; excerpt: string }
export interface Message { id: number; role: 'user' | 'assistant'; content: string; language: string; intents: string[]; sources: Source[]; generated_by: string | null; created_at: string }
export interface Lead { id: number; interest: string | null; budget: number | null; timeline: string | null; authority: string | null; requirements: string | null; intent_level: string; score: number; category: Category; status: string; score_breakdown: Record<string, number>; score_reasons: string[]; updated_at: string }
export interface Customer { id: number; name: string | null; email: string | null; phone: string | null; language: string; created_at: string }
export interface Summary { id: number; conversation_id: string; summary: string; requirements: string | null; objections: string[]; interests: string[]; budget: number | null; purchase_intent: string; sentiment: string; lead_score: number; lead_category: Category; follow_up_action: string; appointment_info: string | null; generated_by: string; created_at: string }
export interface Conversation { id: string; customer_id: number; customer_name: string | null; channel: string; language: string; status: string; started_at: string; ended_at: string | null; message_count: number; lead_category: Category | null; lead_score: number | null; state: { offered_slots?: string[]; pending_slot?: string; awaiting?: string }; summary: Summary | null; messages?: Message[] }
export interface Sentiment { label: string; confidence: number; explanation: string; recommended_action: string; objections: string[]; method?: string }
export interface ToolCall { tool: string; ok: boolean; detail: string | null }
export interface TurnResponse { conversation: Conversation; user_message: Message; assistant_message: Message; tool_calls: ToolCall[]; sentiment: Sentiment | null; lead: Lead; customer: Customer }
export interface Appointment { id: number; customer_id: number; customer_name: string | null; conversation_id: string | null; start_time: string; end_time: string; label: string; status: string; topic: string; notes: string | null; created_at: string }
export interface LeadRow extends Customer { lead: Lead; conversation_count: number; last_contact: string | null; upcoming_appointment: Appointment | null; last_sentiment: string | null }
export interface LeadDetail extends LeadRow { memories: { key: string; value: string; updated_at: string }[]; conversations: Conversation[]; appointments: Appointment[]; sentiments: (Sentiment & { created_at: string })[] }
export interface LeadRescueBrief { risk_reason: string; next_action: string; follow_up_draft: string; generated_by: string; knowledge_sources: { document: string; title: string; excerpt: string }[] }
export interface CallRecording { id: number; conversation_id: string; customer_id: number; customer_name: string; started_at: string | null; ended_at: string | null; duration_seconds: number; size_bytes: number; content_type: string; created_at: string }
export interface KnowledgeDoc { id: number; filename: string; content_type: string; size_bytes: number; status: 'processing' | 'ready' | 'failed'; chunk_count: number; error: string | null; created_at: string }
export interface SearchResult { found: boolean; method: string; top_score: number | null; threshold: number; results: (Source & { content: string })[] }
export interface ProviderStatus { configured_provider: string; active: string; mode: 'llm' | 'demo'; grok_key_present: boolean; grok_model: string; gemini_key_present: boolean; ollama_url: string; ollama_model: string; embeddings: boolean }
export interface Overview {
  totals: { conversations: number; engaged_conversations: number; leads: number; hot: number; warm: number; cold: number; appointments: number; appointment_conversion_rate: number; average_lead_score: number; won: number }
  lead_distribution: { category: Category; count: number }[]
  sentiment_distribution: { label: string; count: number }[]
  top_questions: { topic: string; count: number }[]
  top_objections: { objection: string; count: number }[]
  popular_products: { product: string; count: number }[]
  daily: { date: string; conversations: number; leads: number; appointments: number }[]
  weekly: { week: string; conversations: number }[]
  upcoming_appointments: Appointment[]
  recent_conversations: Conversation[]
  recent_leads: (Customer & { lead: Lead })[]
}
export interface SettingsBundle {
  settings: {
    business_profile: { company_name: string; description: string; agent_name: string; product_noun: string; contact_email: string; contact_phone: string; products: Record<string, string[]> }
    agent_instructions: { system_prompt: string }
    scheduling: { working_days: number[]; start_hour: number; end_hour: number; slot_minutes: number; days_ahead: number; min_notice_minutes: number }
    lead_scoring: { weights: Record<string, number>; hot_threshold: number; warm_threshold: number }
    voice: { default_language: string; speech_rate: number; auto_speak: boolean }
  }
  environment: { environment: string; database: string; provider: ProviderStatus; admin_auth_enabled: boolean; cors_origins: string[]; max_upload_mb: number; rate_limit_per_minute: number; timezone: string; calendar_provider: string; chunks_with_embeddings: number; telephony: { provider: string; phone_number: string | null; account_configured: boolean; stream_configured: boolean; speech_configured: boolean; wss_url: string | null; ready: boolean } }
}
export interface PublicSettings { business_profile: { company_name: string; agent_name: string }; lead_scoring_weights: Record<string, number>; voice: SettingsBundle['settings']['voice']; provider: ProviderStatus; auth_required: boolean }

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const ADMIN_KEY = 'salespilot.adminKey'
export const adminKey = {
  get: () => { try { return localStorage.getItem(ADMIN_KEY) ?? '' } catch { return '' } },
  set: (v: string) => { try { if (v) localStorage.setItem(ADMIN_KEY, v); else localStorage.removeItem(ADMIN_KEY) } catch { /* storage unavailable */ } },
}

function detailToText(detail: unknown): string {
  if (!detail) return 'Request failed'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg ?? String(d)).join('; ')
  if (typeof detail === 'object' && detail && 'message' in detail) return String((detail as { message: string }).message)
  return JSON.stringify(detail)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const key = adminKey.get()
  if (key) headers.set('X-Admin-Key', key)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  let res: Response
  try {
    res = await fetch(`/api${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'Cannot reach the Kiln & Signal service. Start it with start-backend.ps1 (port 8000).')
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { msg = detailToText((await res.json()).detail) } catch { /* not json */ }
    if (res.status === 401) msg = 'Admin key required. Enter it in Settings → Access.'
    if (res.status === 502 || res.status === 504) msg = 'Cannot reach the Kiln & Signal service. Start it with start-backend.ps1 (port 8000).'
    throw new ApiError(res.status, msg)
  }
  const type = res.headers.get('content-type') ?? ''
  return (type.includes('application/json') ? res.json() : res.text()) as Promise<T>
}

const json = (body: unknown) => JSON.stringify(body)

export const api = {
  health: () => request<{ status: string; llm: string }>('/health'),
  publicSettings: () => request<PublicSettings>('/settings/public'),
  startConversation: (language: 'en' | 'hi', channel: 'voice' | 'text', customer_id?: number) =>
    request<Conversation>('/conversations', { method: 'POST', body: json({ language, channel, customer_id }) }),
  sendMessage: (id: string, text: string, channel: 'voice' | 'text') =>
    request<TurnResponse>(`/conversations/${id}/messages`, { method: 'POST', body: json({ text, channel }) }),
  endConversation: (id: string) => request<Conversation>(`/conversations/${id}/end`, { method: 'POST' }),
  uploadRecording: (id: string, blob: Blob, durationSeconds: number) => {
    const form = new FormData()
    const ext = blob.type.includes('mp4') ? 'mp4' : blob.type.includes('ogg') ? 'ogg' : 'webm'
    form.append('file', blob, `conversation.${ext}`)
    return request<CallRecording>(`/conversations/${id}/recording?duration_seconds=${durationSeconds}`, { method: 'POST', body: form })
  },
  recordings: () => request<CallRecording[]>('/recordings'),
  recordingAudio: async (id: number) => {
    const key = adminKey.get()
    const res = await fetch(`/api/recordings/${id}/audio`, { headers: key ? { 'X-Admin-Key': key } : {} })
    if (!res.ok) throw new ApiError(res.status, res.status === 401 ? 'Admin key required.' : `Audio unavailable (HTTP ${res.status})`)
    return res.blob()
  },
  conversations: () => request<Conversation[]>('/conversations'),
  toolLogs: (id: string) => request<{ id: number; tool: string; input: unknown; output: unknown; success: boolean; error: string | null; duration_ms: number; created_at: string }[]>(`/conversations/${id}/tool-logs`),
  leads: (p: { q?: string; category?: string; status?: string; sort?: string }) => {
    const qs = new URLSearchParams(Object.entries(p).filter(([, v]) => v) as [string, string][])
    return request<LeadRow[]>(`/leads?${qs}`)
  },
  lead: (id: number) => request<LeadDetail>(`/leads/${id}`),
  leadRescueBrief: (id: number) => request<LeadRescueBrief>(`/leads/${id}/rescue-brief`, { method: 'POST' }),
  updateLead: (id: number, body: Partial<{ status: string; name: string; email: string; phone: string }>) =>
    request<LeadRow>(`/leads/${id}`, { method: 'PATCH', body: json(body) }),
  deleteLead: (id: number) => request<{ deleted: number }>(`/leads/${id}`, { method: 'DELETE' }),
  deleteMemories: (id: number, key?: string) => request<{ deleted: number }>(`/customers/${id}/memories${key ? `?key=${encodeURIComponent(key)}` : ''}`, { method: 'DELETE' }),
  exportCsv: async () => {
    const key = adminKey.get()
    const res = await fetch('/api/leads/export.csv', { headers: key ? { 'X-Admin-Key': key } : {} })
    if (!res.ok) throw new ApiError(res.status, res.status === 401 ? 'Admin key required.' : `Export failed (HTTP ${res.status})`)
    return res.blob()
  },
  appointments: (upcoming = false) => request<Appointment[]>(`/appointments${upcoming ? '?upcoming=true' : ''}`),
  slots: (date?: string) => request<{ start_time: string; label: string }[]>(`/appointments/slots${date ? `?date=${date}` : ''}`),
  book: (customer_id: number, start_time: string, notes?: string) =>
    request<Appointment>('/appointments', { method: 'POST', body: json({ customer_id, start_time, notes }) }),
  cancelAppointment: (id: number) => request<Appointment>(`/appointments/${id}/cancel`, { method: 'POST' }),
  reschedule: (id: number, start_time: string) => request<Appointment>(`/appointments/${id}/reschedule`, { method: 'POST', body: json({ start_time }) }),
  documents: () => request<KnowledgeDoc[]>('/knowledge/documents'),
  chunks: (id: number) => request<{ id: number; index: number; title: string; content: string; has_embedding: boolean }[]>(`/knowledge/documents/${id}/chunks`),
  upload: (file: File) => { const fd = new FormData(); fd.append('file', file); return request<KnowledgeDoc>('/knowledge/documents', { method: 'POST', body: fd }) },
  deleteDocument: (id: number) => request<{ deleted: number }>(`/knowledge/documents/${id}`, { method: 'DELETE' }),
  search: (query: string, top_k = 3) => request<SearchResult>('/knowledge/search', { method: 'POST', body: json({ query, top_k }) }),
  overview: (days = 14) => request<Overview>(`/analytics/overview?days=${days}`),
  settings: () => request<SettingsBundle>('/settings'),
  saveSettings: <K extends keyof SettingsBundle['settings']>(key: K, value: Partial<SettingsBundle['settings'][K]>) =>
    request<SettingsBundle['settings'][K]>(`/settings/${key}`, { method: 'PUT', body: json(value) }),
}
