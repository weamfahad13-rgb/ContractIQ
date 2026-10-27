import { useEffect, useState } from 'react'
import { FileCheck2, Gauge, ListOrdered, Target } from 'lucide-react'

import { api, pct, type Evaluation as Ev, type RetrievalRun } from '../api'

const VERSIONS = [
  { mode: 'vector', label: 'v1 Vector search' },
  { mode: 'hybrid', label: 'v2 Hybrid search' },
  { mode: 'rerank', label: 'v3 + Reranker' },
  { mode: 'fusion', label: 'v4 + Rank fusion' },
] as const

const toPct = (v: number) => Math.round(v * 1000) / 10

export default function Evaluation() {
  const [ev, setEv] = useState<Ev | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    api.evaluation().then(setEv).catch((e) => setError(e.message))
  }, [])

  const runs = ev?.retrieval?.runs ?? []
  const run = (mode: string, lang: string) => runs.find((r) => r.mode === mode && r.lang === lang) as RetrievalRun | undefined
  const best = { en: run('fusion', 'en'), ar: run('fusion', 'ar') }
  const k = ev?.retrieval?.k ?? 5

  const cards = [
    { icon: Target, label: 'Retrieval accuracy', value: pct(best.en?.recall_at_k), note: `Recall@${k}, English questions` },
    { icon: ListOrdered, label: 'Ranking quality', value: best.en ? best.en.mrr.toFixed(3) : '—', note: 'MRR, English questions' },
    {
      icon: FileCheck2,
      label: 'Answer faithfulness',
      value: pct(ev?.answers?.faithfulness),
      note: ev?.answers
        ? `${ev.answers.n} answers judged · ${pct(ev.answers.not_found_rate ?? undefined)} said "not found" on a labeled clause`
        : 'Needs an LLM API key',
    },
    {
      icon: Gauge,
      label: 'Avg. retrieval time',
      value: best.en && best.ar ? `${Math.round((best.en.avg_latency_ms + best.ar.avg_latency_ms) / 2)} ms` : '—',
      note: 'Per question, English and Arabic, local GPU',
    },
  ]

  // Per version: accuracy in each language, and time per question (averaged over both languages).
  const speed = VERSIONS.flatMap((v) => {
    const en = run(v.mode, 'en')
    const ar = run(v.mode, 'ar')
    if (!en || !ar) return []
    return [{ label: v.label, en: toPct(en.recall_at_k), ar: toPct(ar.recall_at_k),
              ms: Math.round((en.avg_latency_ms + ar.avg_latency_ms) / 2) }]
  })
  const maxMs = Math.max(1, ...speed.map((v) => v.ms))
  const categories = Object.keys(best.en?.per_category ?? {}).map((c) => ({
    category: c,
    en: best.en!.per_category[c],
    ar: best.ar?.per_category[c],
  }))

  return (
    <div className="space-y-5">
      <section className="card p-6 sm:p-8">
        <h1 className="text-4xl font-extrabold sm:text-5xl">Evaluation</h1>
        <p className="mt-2 text-lg text-muted">
          Tested on expert-labeled contracts from CUAD
          {ev?.retrieval && ` · ${ev.retrieval.n_questions} questions · ${new Date(ev.retrieval.evaluated_at).toLocaleDateString('en-GB')}`}
        </p>
        {error && <p className="mt-3 text-rose-300">{error}</p>}
        {ev && !ev.retrieval && (
          <p className="mt-3 text-amber-300">No results yet. Run <code>python -m contractiq.evaluate</code>.</p>
        )}
        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {cards.map(({ icon: Icon, label, value, note }) => (
            <div key={label} className="flex gap-4 rounded-xl border border-line-strong bg-ink-900/60 p-5">
              <Icon className="h-8 w-8 shrink-0 text-accent" aria-hidden />
              <div>
                <p className="text-sm">{label}</p>
                <p className="mt-1 text-3xl font-extrabold">{value}</p>
                <p className="mt-1 text-xs text-muted">{note}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="card relative p-6">
          <h2 className="text-xl font-bold">Accuracy vs. speed</h2>
          <p className="text-sm text-muted">What each version gains in accuracy, and what it costs in time</p>
          <div className="mt-5 flex justify-between gap-8">
            <div className="min-w-0 max-w-4xl flex-1 space-y-5">
              <div className="grid grid-cols-[1fr_1fr] gap-4 text-xs text-muted">
                <span>Accuracy (Recall@{k})</span>
                <span>Time per question</span>
              </div>
              {speed.map((v) => (
                <div key={v.label}>
                  <p className="mb-1.5 text-sm font-semibold">{v.label}</p>
                  <div className="grid grid-cols-[1fr_1fr] items-center gap-4">
                    <div className="space-y-1">
                      {([['English', v.en, 'bg-accent'], ['Arabic', v.ar, 'bg-blue-400']] as const).map(([lang, val, color]) => (
                        <div key={lang} className="flex items-center gap-2">
                          <span className="w-14 shrink-0 text-xs text-muted">{lang}</span>
                          <div className="h-2.5 flex-1 rounded-full bg-ink-800">
                            <div className={`h-full rounded-full ${color}`} style={{ width: `${val}%` }} />
                          </div>
                          <span className="w-12 text-right text-xs tabular-nums">{val}%</span>
                        </div>
                      ))}
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-2.5 flex-1 rounded-full bg-ink-800">
                        <div className="h-full rounded-full bg-amber-400" style={{ width: `${(100 * v.ms) / maxMs}%` }} />
                      </div>
                      <span className="w-14 text-right text-xs tabular-nums">{v.ms} ms</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <img src="/mascots/mascot-evaluation.webp" alt="" className="hidden h-72 w-auto self-center object-contain xl:block" />
          </div>
        </section>

      <section className="card overflow-hidden">
        <h2 className="px-6 pt-5 pb-3 text-xl font-bold">Results by clause type</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left">
            <thead className="bg-ink-850 text-sm text-muted">
              <tr>
                <th className="px-6 py-3 font-medium">Clause type</th>
                <th className="px-4 py-3 font-medium">English Recall@{k}</th>
                <th className="px-4 py-3 font-medium">Arabic Recall@{k}</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((c) => (
                <tr key={c.category} className="border-t border-line">
                  <td className="px-6 py-2.5">{c.category}</td>
                  <td className="px-4 py-2.5">{pct(c.en)}</td>
                  <td className="px-4 py-2.5">{pct(c.ar)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {best.en && best.en.failures.length > 0 && (
        <section className="card overflow-hidden">
          <h2 className="px-6 pt-5 pb-3 text-xl font-bold">Questions to review</h2>
          <p className="px-6 pb-3 text-sm text-muted">Cases where the labeled clause wasn't in the top {k} results (best version, English).</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="bg-ink-850 text-muted">
                <tr>
                  <th className="px-6 py-3 font-medium">Question</th>
                  <th className="px-4 py-3 font-medium">Expected clause</th>
                  <th className="px-4 py-3 font-medium">Contract</th>
                </tr>
              </thead>
              <tbody>
                {best.en.failures.slice(0, 10).map((f, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="px-6 py-2.5">{f.question}</td>
                    <td className="px-4 py-2.5">{f.category}</td>
                    <td className="max-w-[320px] truncate px-4 py-2.5 text-muted" title={f.contract}>{f.contract}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
