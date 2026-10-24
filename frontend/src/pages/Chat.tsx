import { Fragment, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Database, FileText, Loader2, SendHorizontal, ThumbsDown, ThumbsUp } from 'lucide-react'

import { api, isArabic, type ChatAnswer, type Citation, type ContractDetail, type ContractSummary } from '../api'

type Message =
  | { role: 'user'; text: string }
  | { role: 'assistant'; answer: ChatAnswer; vote?: 'up' | 'down' }
  | { role: 'error'; text: string }

const EXAMPLES = [
  'What is the late delivery penalty for Al-Sharq Pharma?',
  'كم مدة الإشعار المطلوبة لإنهاء عقد الرياض للخدمات اللوجستية دون سبب؟',
  'How many Red Sea Freight orders were delivered late this year?',
]

const CONFIDENCE_STYLE = {
  high: 'border-emerald-400/60 text-emerald-300',
  medium: 'border-amber-400/60 text-amber-300',
  low: 'border-rose-400/60 text-rose-300',
}

function AnswerText({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  const parts = text.split(/(\[\d+\])/g)
  return (
    <p dir={isArabic(text) ? 'rtl' : 'ltr'} className="leading-7 whitespace-pre-wrap">
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/)
        if (!m) return <Fragment key={i}>{p}</Fragment>
        return (
          <button
            key={i}
            onClick={() => onCite(Number(m[1]))}
            className="mx-0.5 rounded border border-accent/70 px-1 text-xs font-semibold text-accent hover:bg-accent/15"
            aria-label={`Show source ${m[1]}`}
          >
            {m[1]}
          </button>
        )
      })}
    </p>
  )
}

function DataTable({ data }: { data: NonNullable<ChatAnswer['data']> }) {
  if (data.error) return <p className="text-sm text-rose-300">Couldn't query the procurement data: {data.error}</p>
  if (!data.rows?.length) return <p className="text-sm text-muted">The query returned no rows.</p>
  return (
    <div className="mt-3">
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full text-left text-sm">
          <thead className="bg-ink-850 text-muted">
            <tr>{data.columns!.map((c) => <th key={c} className="px-3 py-2 font-medium">{c}</th>)}</tr>
          </thead>
          <tbody>
            {data.rows.slice(0, 10).map((r, i) => (
              <tr key={i} className="border-t border-line">
                {r.map((v, j) => <td key={j} className="px-3 py-1.5">{v ?? '—'}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RecordsSource({ data }: { data: NonNullable<ChatAnswer['data']> }) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-start gap-3 border-b border-line p-5">
        <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl border border-line bg-ink-850">
          <Database className="h-6 w-6 text-violet-300" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">Purchase-order records</p>
          <p className="text-sm text-muted">Computed from the procurement database, not from a contract clause</p>
        </div>
      </div>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5 text-sm">
        {data.error ? (
          <p className="text-rose-300">The query failed: {data.error}</p>
        ) : (
          <>
            <p className="text-muted">{data.rows?.length ?? 0} row{data.rows?.length === 1 ? '' : 's'} returned by this query:</p>
            <pre className="overflow-x-auto rounded-xl border border-line-strong bg-ink-950 p-4 text-xs leading-5 whitespace-pre-wrap text-slate-300">
              {data.sql}
            </pre>
          </>
        )}
      </div>
    </div>
  )
}

function SourcePanel({ citations, active, setActive, confidence, data }: {
  citations: Citation[]
  active: number
  setActive: (i: number) => void
  confidence?: ChatAnswer['confidence']
  data?: ChatAnswer['data']
}) {
  const [contract, setContract] = useState<ContractDetail | null>(null)
  const [full, setFull] = useState(false)
  const markRef = useRef<HTMLElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const cite = citations[active]

  useEffect(() => {
    if (!cite) return
    if (contract?.id !== cite.contract_id) api.contract(cite.contract_id).then(setContract)
  }, [cite, contract?.id])

  // Each new source opens on just the cited clause.
  useEffect(() => {
    setFull(false)
  }, [cite])

  // In the full view, scroll only the text panel to the clause (scrollIntoView would also scroll the page).
  useEffect(() => {
    const box = scrollRef.current
    const mark = markRef.current
    if (!full || !box || !mark) return
    const offset = mark.getBoundingClientRect().top - box.getBoundingClientRect().top
    box.scrollTo({ top: box.scrollTop + offset - 24 })
  }, [contract, cite, full])

  if (!cite && data) return <RecordsSource data={data} />

  if (!cite) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
        <img src="/mascots/mascot-chat.webp" alt="" className="h-64 object-contain" />
        <p className="max-w-xs text-muted">Ask a question and the clause behind the answer will show up here.</p>
      </div>
    )
  }

  const text = contract?.id === cite.contract_id ? contract.full_text : ''
  const squash = (s: string) => s.replace(/[ \t]{2,}/g, ' ').replace(/\n{3,}/g, '\n\n')

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-start gap-3 border-b border-line p-5">
        <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl border border-line bg-ink-850">
          <FileText className="h-6 w-6 text-accent" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold" title={cite.contract_title}>{cite.contract_title}</p>
          <p className="truncate text-sm text-muted">{cite.heading}</p>
        </div>
        {confidence && (
          <span className={`shrink-0 rounded-full border px-2.5 py-1 text-xs ${CONFIDENCE_STYLE[confidence]}`}>
            {confidence[0].toUpperCase() + confidence.slice(1)} confidence
          </span>
        )}
      </div>
      <div
        ref={scrollRef}
        dir={contract?.language === 'ar' ? 'rtl' : 'ltr'}
        className="relative min-h-0 flex-1 overflow-y-auto p-5 text-sm leading-6 whitespace-pre-wrap text-slate-300"
      >
        {!text ? (
          <Loader2 className="h-5 w-5 animate-spin text-muted" aria-label="Loading contract" />
        ) : !full ? (
          <div className="space-y-4">
            <p className="rounded-xl border border-line-strong bg-ink-900/60 p-4 leading-7 text-slate-200">
              {squash(text.slice(cite.start_char, cite.end_char)).trim()}
            </p>
            <button onClick={() => setFull(true)} className="text-sm whitespace-normal text-accent hover:underline">
              Show in full contract
            </button>
          </div>
        ) : (
          <>
            <button
              onClick={() => setFull(false)}
              className="sticky top-0 z-10 mb-3 rounded-lg border border-line bg-ink-850 px-3 py-1.5 text-sm whitespace-normal text-accent"
            >
              Show only the cited clause
            </button>
            <div>
              {squash(text.slice(0, cite.start_char))}
              <mark ref={markRef} className="rounded bg-mark px-1 text-ink-950">
                {squash(text.slice(cite.start_char, cite.end_char))}
              </mark>
              {squash(text.slice(cite.end_char))}
            </div>
          </>
        )}
      </div>
      <div className="flex items-center gap-3 border-t border-line p-4">
        <button
          onClick={() => setActive(Math.max(0, active - 1))}
          disabled={active === 0}
          className="rounded-lg border border-line p-2 disabled:opacity-40"
          aria-label="Previous source"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="text-sm">Source {active + 1} / {citations.length}</span>
        <button
          onClick={() => setActive(Math.min(citations.length - 1, active + 1))}
          disabled={active === citations.length - 1}
          className="rounded-lg border border-line p-2 disabled:opacity-40"
          aria-label="Next source"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

export default function Chat() {
  const [params, setParams] = useSearchParams()
  const scope = params.get('contract') ? Number(params.get('contract')) : null
  const [contracts, setContracts] = useState<ContractSummary[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [focus, setFocus] = useState<{ msg: number; idx: number } | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.contracts().then(setContracts).catch(() => setContracts([]))
  }, [])
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  async function ask(question: string) {
    const q = question.trim()
    if (!q || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: q }])
    setBusy(true)
    try {
      const answer = await api.chat(q, scope)
      setMessages((m) => {
        const next = [...m, { role: 'assistant' as const, answer }]
        const firstCited = answer.citations.findIndex((c) => c.cited)
        setFocus({ msg: next.length - 1, idx: Math.max(0, firstCited) })
        return next
      })
    } catch (e) {
      setMessages((m) => [...m, { role: 'error', text: (e as Error).message }])
    } finally {
      setBusy(false)
    }
  }

  const focused = focus ? messages[focus.msg] : undefined
  const focusedAnswer = focused?.role === 'assistant' ? focused.answer : undefined
  const samples = contracts.filter((c) => c.source === 'synthetic')
  const cuad = contracts.filter((c) => c.source === 'cuad')

  return (
    <div className="grid min-h-0 flex-1 gap-5 lg:h-[calc(100vh-7.5rem)] lg:flex-none lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)]">
      <section className="card flex min-h-[70vh] flex-col lg:min-h-0">
        <div className="flex flex-wrap items-end justify-between gap-3 p-6 pb-2">
          <div>
            <h1 className="text-3xl font-extrabold">Chat</h1>
            <p className="text-muted">Answers grounded in the contracts</p>
          </div>
          <label className="flex items-center gap-2 text-sm text-muted">
            Search in
            <select
              value={scope ?? ''}
              onChange={(e) => setParams(e.target.value ? { contract: e.target.value } : {})}
              className="max-w-[260px] rounded-lg border border-line bg-ink-850 px-3 py-2 text-white"
            >
              <option value="">All contracts</option>
              <optgroup label="Sample suppliers">
                {samples.map((c) => <option key={c.id} value={c.id}>{c.supplier} · {c.contract_type}</option>)}
              </optgroup>
              <optgroup label="CUAD contracts">
                {cuad.map((c) => <option key={c.id} value={c.id}>{c.title.slice(0, 60)}</option>)}
              </optgroup>
            </select>
          </label>
        </div>

        <div ref={listRef} className="min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-4">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-3 py-10">
              <p className="mb-2 text-muted">Try one of these</p>
              {EXAMPLES.map((q) => (
                <button
                  key={q}
                  onClick={() => ask(q)}
                  dir={isArabic(q) ? 'rtl' : 'ltr'}
                  className="w-full max-w-lg rounded-xl border border-line bg-ink-850/60 px-4 py-3 text-start hover:border-accent/60"
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          {messages.map((m, i) =>
            m.role === 'user' ? (
              <div key={i} className="flex justify-end">
                <p dir={isArabic(m.text) ? 'rtl' : 'ltr'} className="max-w-[80%] rounded-xl border border-line-strong bg-ink-800 px-4 py-3">
                  {m.text}
                </p>
              </div>
            ) : m.role === 'error' ? (
              <p key={i} className="rounded-xl border border-rose-400/40 bg-rose-500/10 px-4 py-3 text-rose-200">{m.text}</p>
            ) : (
              <div key={i} className="flex gap-3">
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-accent/60">
                  <FileText className="h-5 w-5 text-accent" aria-hidden />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold">ContractIQ</p>
                    {m.answer.data && (
                      <span className="flex items-center gap-1 rounded bg-violet-500/20 px-1.5 py-0.5 text-xs text-violet-200">
                        <Database className="h-3 w-3" aria-hidden /> SQL
                      </span>
                    )}
                  </div>
                  <div className="mt-2 rounded-xl border border-line bg-ink-850 px-4 py-3">
                    <AnswerText
                      text={m.answer.answer}
                      onCite={(n) => setFocus({ msg: i, idx: Math.max(0, m.answer.citations.findIndex((c) => c.n === n)) })}
                    />
                    {m.answer.data && <DataTable data={m.answer.data} />}
                  </div>
                  {m.answer.citations.some((c) => c.cited) && (
                    <>
                      <p className="mt-3 text-sm text-muted">Sources</p>
                      <div className="mt-1.5 flex flex-wrap gap-2">
                        {m.answer.citations.filter((c) => c.cited).map((c) => (
                          <button
                            key={c.n}
                            onClick={() => setFocus({ msg: i, idx: m.answer.citations.indexOf(c) })}
                            className={`max-w-full truncate rounded-lg border px-3 py-1.5 text-sm hover:border-accent ${
                              focus?.msg === i && m.answer.citations[focus.idx] === c ? 'border-accent text-accent' : 'border-accent/40'
                            }`}
                          >
                            [{c.n}] {c.contract_title.split(' - ').pop()} · {c.heading.slice(0, 40)}
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                  <div className="mt-2 flex gap-3 text-muted">
                    {(['up', 'down'] as const).map((v) => {
                      const Icon = v === 'up' ? ThumbsUp : ThumbsDown
                      return (
                        <button
                          key={v}
                          aria-label={v === 'up' ? 'Helpful' : 'Not helpful'}
                          onClick={() => setMessages((ms) => ms.map((x, j) => (j === i && x.role === 'assistant' ? { ...x, vote: v } : x)))}
                          className={m.vote === v ? 'text-accent' : 'hover:text-white'}
                        >
                          <Icon className="h-4 w-4" />
                        </button>
                      )
                    })}
                  </div>
                </div>
              </div>
            ),
          )}
          {busy && (
            <div className="flex items-center gap-2 text-muted">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Searching the contracts…
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault()
            ask(input)
          }}
          className="p-6 pt-2"
        >
          <div className="flex items-center gap-3 rounded-xl border border-line-strong bg-ink-900 p-2 pl-5 focus-within:border-accent">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              dir={isArabic(input) ? 'rtl' : 'ltr'}
              placeholder="Ask about the contracts…"
              maxLength={500}
              className="min-w-0 flex-1 bg-transparent py-2 outline-none placeholder:text-muted"
            />
            <button
              type="submit"
              disabled={busy || input.trim().length < 2}
              className="grid h-12 w-12 place-items-center rounded-lg bg-accent text-ink-950 disabled:opacity-40"
              aria-label="Send"
            >
              <SendHorizontal className="h-5 w-5" />
            </button>
          </div>
          <p className="mt-2 text-xs text-muted">Check the cited clauses for full context.</p>
        </form>
      </section>

      <aside className="card flex h-[75vh] flex-col overflow-hidden lg:h-auto lg:min-h-0">
        <div className="shrink-0 border-b border-line px-5 pt-5 pb-3">
          <h2 className="text-xl font-bold">Source document</h2>
        </div>
        <div className="min-h-0 flex-1">
          <SourcePanel
            citations={focusedAnswer?.citations ?? []}
            active={focus?.idx ?? 0}
            setActive={(idx) => focus && setFocus({ ...focus, idx })}
            confidence={focusedAnswer?.confidence}
            data={focusedAnswer?.data}
          />
        </div>
      </aside>
    </div>
  )
}
