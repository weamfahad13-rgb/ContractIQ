export type ContractStatus = 'active' | 'expiring_soon' | 'expired' | 'unknown'

export interface ContractSummary {
  id: number
  title: string
  supplier: string | null
  supplier_ar: string | null
  contract_type: string
  language: 'en' | 'ar'
  source: 'cuad' | 'synthetic'
  start_date: string | null
  end_date: string | null
  chunks: number
  status: ContractStatus
}

export interface ContractDetail extends Omit<ContractSummary, 'chunks' | 'status'> {
  full_text: string
  chunks: { id: number; ord: number; heading: string; start_char: number; end_char: number }[]
}

export interface Citation {
  n: number
  chunk_id: number
  contract_id: number
  contract_title: string
  heading: string
  start_char: number
  end_char: number
  score: number
  cited: boolean
}

export interface ChatAnswer {
  question: string
  route: 'contracts' | 'data' | 'both'
  scoped_contract_id: number | null
  answer: string
  confidence: 'high' | 'medium' | 'low'
  citations: Citation[]
  data: { sql?: string; columns?: string[]; rows?: (string | null)[][]; error?: string } | null
}

export interface RetrievalRun {
  mode: 'vector' | 'hybrid' | 'rerank' | 'fusion'
  lang: 'en' | 'ar'
  n: number
  recall_at_k: number
  mrr: number
  avg_latency_ms: number
  per_category: Record<string, number>
  failures: { question: string; category: string; contract: string }[]
}

export interface Evaluation {
  retrieval?: { evaluated_at: string; k: number; n_questions: number; runs: RetrievalRun[] }
  answers?: {
    evaluated_at: string
    n: number
    faithfulness: number
    relevance: number
    not_found_rate: number | null
    avg_latency_ms: number
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Request failed (${res.status})`)
  }
  return res.json()
}

export const api = {
  contracts: () => request<ContractSummary[]>('/api/contracts'),
  contract: (id: number) => request<ContractDetail>(`/api/contracts/${id}`),
  evaluation: () => request<Evaluation>('/api/evaluation'),
  chat: (question: string, contractId: number | null) =>
    request<ChatAnswer>('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, contract_id: contractId }),
    }),
}

export const GITHUB_URL = 'https://github.com/'

export const isArabic = (text: string) => /[؀-ۿ]/.test(text)

/** Same folding as the backend: أ/إ/آ→ا, ة→ه, ى→ي, no diacritics. */
export const normalizeAr = (text: string) =>
  text.replace(/[ً-ْـ]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي')

export function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export const pct = (x: number | undefined) => (x === undefined ? '—' : `${(x * 100).toFixed(1)}%`)
