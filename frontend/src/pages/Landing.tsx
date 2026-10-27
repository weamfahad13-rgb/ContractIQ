import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, BarChart3, FileSearch, MessageSquareText } from 'lucide-react'

import { api, GITHUB_URL, pct, type Evaluation } from '../api'
import { Logo } from '../components/Nav'

const features = [
  { icon: MessageSquareText, title: 'Ask your contracts', body: 'Find terms, penalties, and renewal dates.' },
  { icon: BarChart3, title: 'Explore purchase orders', body: 'Turn purchasing data into clear insights.' },
  { icon: FileSearch, title: 'Check every source', body: 'Trace answers to the exact clause.' },
]

const steps = [
  { title: 'Explore sample contracts', body: 'Real supplier contracts, ready to search.' },
  { title: 'Ask a question', body: 'In Arabic or English.' },
  { title: 'Review the evidence', body: 'See the exact clause for every answer.' },
]

const stack = ['Python', 'FastAPI', 'PostgreSQL + pgvector', 'BGE-M3', 'React']

function Github({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.53-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.42-2.7 5.39-5.26 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  )
}

function bestRun(ev: Evaluation | null, lang: 'en' | 'ar') {
  return ev?.retrieval?.runs.find((r) => r.mode === 'fusion' && r.lang === lang)
}

export default function Landing() {
  const [ev, setEv] = useState<Evaluation | null>(null)
  useEffect(() => {
    api.evaluation().then(setEv).catch(() => setEv(null))
  }, [])

  const en = bestRun(ev, 'en')
  const ar = bestRun(ev, 'ar')
  const k = ev?.retrieval?.k ?? 5
  const metrics = [
    { label: 'English questions', value: pct(en?.recall_at_k), note: `Retrieval accuracy (Recall@${k})` },
    { label: 'Arabic questions', value: pct(ar?.recall_at_k), note: `Same questions, asked in Arabic (Recall@${k})` },
  ]

  return (
    <div className="page-glow min-h-screen">
      <header className="mx-auto flex max-w-[1400px] items-center justify-between px-4 py-6 sm:px-10">
        <Logo />
        <nav className="hidden gap-10 text-slate-200 md:flex">
          <a href="#features" className="hover:text-white">Features</a>
          <a href="#how" className="hover:text-white">How it works</a>
        </nav>
        <Link to="/chat" className="rounded-xl border border-accent/70 px-5 py-2.5 font-semibold hover:bg-accent/10">
          Try it now
        </Link>
      </header>

      <section className="mx-auto grid max-w-[1400px] items-center gap-8 px-4 pt-6 pb-12 sm:px-10 lg:grid-cols-[1.05fr_1fr]">
        <div>
          <p className="mb-4 text-sm font-semibold tracking-[0.2em] text-accent">AI FOR PROCUREMENT TEAMS</p>
          <h1 className="text-5xl leading-[1.02] font-extrabold tracking-tight sm:text-7xl">
            Your contracts.
            <br />
            <span className="text-accent">Clear answers.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg text-slate-300 sm:text-xl">
            Ask about supplier contracts and purchase orders. Get clear answers with the exact clause and source.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link
              to="/chat"
              className="flex items-center gap-2 rounded-xl bg-accent px-7 py-4 text-lg font-bold text-ink-950 hover:bg-accent-strong"
            >
              Try it now <ArrowRight className="h-5 w-5" aria-hidden />
            </Link>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 rounded-xl border border-slate-400/60 px-7 py-4 text-lg font-semibold hover:bg-white/5"
            >
              <Github className="h-5 w-5" aria-hidden /> View on GitHub
            </a>
          </div>
          <p className="mt-6 text-sm text-muted">Contract citations · Purchase-order insights</p>
        </div>
        <div className="relative mx-auto w-full max-w-[680px]">
          <div className="absolute inset-[12%] rounded-full bg-accent/10 blur-2xl" aria-hidden />
          <img
            src="/mascots/mascot-landing.webp"
            alt="ContractIQ mascot pointing at a highlighted contract clause"
            className="relative w-full drop-shadow-2xl"
          />
        </div>
      </section>

      <section id="features" className="mx-auto grid max-w-[1400px] gap-5 px-4 sm:px-10 md:grid-cols-3">
        {features.map(({ icon: Icon, title, body }) => (
          <div key={title} className="card flex gap-5 p-6">
            <div className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl border border-line bg-ink-850">
              <Icon className="h-8 w-8 text-accent" aria-hidden />
            </div>
            <div>
              <h3 className="text-xl font-bold">{title}</h3>
              <p className="mt-1 text-muted">{body}</p>
            </div>
          </div>
        ))}
      </section>

      <section id="how" className="mx-auto mt-14 max-w-[1400px] px-4 sm:px-10">
        <div className="grid items-center gap-8 border-t border-line pt-10 lg:grid-cols-[300px_1fr]">
          <h2 className="text-4xl font-extrabold">How it works</h2>
          <ol className="grid gap-6 md:grid-cols-3">
            {steps.map((s, i) => (
              <li key={s.title} className="flex gap-4">
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full border border-accent/70 font-semibold text-accent">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div>
                  <p className="font-semibold">{s.title}</p>
                  <p className="text-sm text-muted">{s.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto mt-16 max-w-[1400px] px-4 sm:px-10">
        <h2 className="text-4xl font-extrabold">Measured results</h2>
        <p className="mt-2 text-muted">Evaluated on expert-labeled contracts from CUAD.</p>
        <div className="mt-6 grid gap-5 md:grid-cols-2">
          {metrics.map((m) => (
            <div key={m.label} className="card p-6">
              <p className="font-semibold">{m.label}</p>
              <p className="mt-3 text-4xl font-extrabold text-accent">{m.value}</p>
              <p className="mt-2 text-sm text-muted">{m.note}</p>
            </div>
          ))}
        </div>
        <Link to="/evaluation" className="mt-4 inline-block text-sm text-accent hover:underline">
          See the full evaluation →
        </Link>
      </section>

      <footer className="mx-auto mt-16 max-w-[1400px] border-t border-line px-4 py-8 sm:px-10">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted">
          <span className="font-semibold text-slate-200">Built with</span>
          {stack.map((s) => (
            <span key={s}>{s}</span>
          ))}
        </div>
      </footer>
    </div>
  )
}
