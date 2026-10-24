import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Clock, Search } from 'lucide-react'

import { api, formatDate, normalizeAr, type ContractStatus, type ContractSummary } from '../api'

const STATUS: Record<ContractStatus, { label: string; style: string; dot: string }> = {
  active: { label: 'Active', style: 'border-emerald-400/50 text-emerald-300', dot: 'bg-emerald-400' },
  expiring_soon: { label: 'Expiring soon', style: 'border-amber-400/50 text-amber-300', dot: 'bg-amber-400' },
  expired: { label: 'Expired', style: 'border-rose-400/50 text-rose-300', dot: 'bg-rose-500' },
  unknown: { label: 'No dates', style: 'border-line-strong text-muted', dot: 'bg-slate-500' },
}

const PAGE_SIZE = 15

function Select({ label, value, onChange, options }: {
  label: string
  value: string
  onChange: (v: string) => void
  options: [string, string][]
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-xl border border-line-strong bg-ink-900 px-4 py-3"
    >
      <option value="">{label}</option>
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  )
}

export default function Contracts() {
  const navigate = useNavigate()
  const [all, setAll] = useState<ContractSummary[] | null>(null)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({ q: '', type: '', status: '', source: '' })
  const [page, setPage] = useState(0)
  const [today] = useState(() => new Date().toISOString())
  const { q, type, status, source } = filters
  // Any filter change starts again from the first page.
  const setFilter = (key: keyof typeof filters) => (value: string) => {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(0)
  }

  useEffect(() => {
    api.contracts().then(setAll).catch((e) => setError(e.message))
  }, [])

  const types = useMemo(() => [...new Set((all ?? []).map((c) => c.contract_type))].sort(), [all])
  const rows = useMemo(() => {
    const needle = normalizeAr(q.trim().toLowerCase())
    return (all ?? []).filter(
      (c) =>
        (!needle || normalizeAr(`${c.title} ${c.supplier ?? ''} ${c.supplier_ar ?? ''}`.toLowerCase()).includes(needle)) &&
        (!type || c.contract_type === type) &&
        (!status || c.status === status) &&
        (!source || c.source === source),
    )
  }, [all, q, type, status, source])

  const expiring = (all ?? []).filter((c) => c.status === 'expiring_soon').length
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const visible = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  return (
    <div className="space-y-4">
      <section className="card relative flex flex-wrap items-end gap-6 overflow-hidden p-6 sm:p-8">
        <div className="min-w-0 flex-1">
          <h1 className="text-4xl font-extrabold sm:text-5xl">Contracts</h1>
          <p className="mt-2 text-lg text-muted">Find supplier agreements and track renewal dates.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <label className="flex min-w-[260px] flex-1 items-center gap-3 rounded-xl border border-line-strong bg-ink-900 px-4 focus-within:border-accent">
              <Search className="h-5 w-5 text-muted" aria-hidden />
              <input
                value={q}
                onChange={(e) => setFilter('q')(e.target.value)}
                placeholder="Search contracts…"
                aria-label="Search contracts"
                className="w-full bg-transparent py-3 outline-none placeholder:text-muted"
              />
            </label>
            <Select label="Contract type" value={type} onChange={setFilter('type')} options={types.map((t) => [t, t])} />
            <Select
              label="Status"
              value={status}
              onChange={setFilter('status')}
              options={Object.entries(STATUS).map(([k, v]) => [k, v.label])}
            />
            <Select label="Source" value={source} onChange={setFilter('source')} options={[['synthetic', 'Sample suppliers'], ['cuad', 'CUAD']]} />
          </div>
        </div>
        <img src="/mascots/mascot-contracts.webp" alt="" className="hidden h-52 object-contain md:block" />
      </section>

      {expiring > 0 && (
        <button
          onClick={() => setFilter('status')('expiring_soon')}
          className="flex w-full items-center gap-3 rounded-xl border border-amber-400/60 bg-amber-400/10 px-5 py-4 text-left font-semibold text-amber-300"
        >
          <Clock className="h-5 w-5" aria-hidden />
          {expiring} contract{expiring > 1 ? 's' : ''} expire in the next 60 days
        </button>
      )}

      <section className="card overflow-hidden">
        <div className="flex items-center gap-4 px-6 py-4">
          <p className="text-lg font-bold">{rows.length} {rows.length === 1 ? 'contract' : 'contracts'}</p>
          <span className="h-6 w-px bg-line" />
          <p className="text-sm text-muted">As of {formatDate(today)}</p>
        </div>
        {error && <p className="px-6 pb-4 text-rose-300">{error}</p>}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left">
            <thead className="bg-ink-850 text-sm text-muted">
              <tr>
                <th className="px-6 py-3 font-medium">Supplier / contract</th>
                <th className="px-4 py-3 font-medium">Contract type</th>
                <th className="px-4 py-3 font-medium">Language</th>
                <th className="px-4 py-3 font-medium">Start date</th>
                <th className="px-4 py-3 font-medium">End date</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {all === null && !error && (
                <tr><td colSpan={6} className="px-6 py-8 text-center text-muted">Loading…</td></tr>
              )}
              {all !== null && rows.length === 0 && (
                <tr><td colSpan={6} className="px-6 py-8 text-center text-muted">No contracts match these filters.</td></tr>
              )}
              {visible.map((c) => {
                const s = STATUS[c.status]
                return (
                  <tr
                    key={c.id}
                    onClick={() => navigate(`/chat?contract=${c.id}`)}
                    className="cursor-pointer border-t border-line hover:bg-ink-850/70"
                    title="Ask about this contract"
                  >
                    <td className="max-w-[420px] px-6 py-3">
                      {/* A real link, so the row also works from the keyboard. */}
                      <Link
                        to={`/chat?contract=${c.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="block truncate hover:text-accent"
                      >
                        {c.supplier ?? c.title}
                      </Link>
                      {c.supplier && <p className="truncate text-xs text-muted">{c.title}</p>}
                    </td>
                    <td className="px-4 py-3">{c.contract_type}</td>
                    <td className="px-4 py-3 uppercase text-muted">{c.language}</td>
                    <td className="px-4 py-3">{formatDate(c.start_date)}</td>
                    <td className="px-4 py-3">{formatDate(c.end_date)}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1 text-sm ${s.style}`}>
                        <span className={`h-2 w-2 rounded-full ${s.dot}`} />
                        {s.label}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-line px-6 py-4">
          <p className="text-sm text-muted">
            Showing {rows.length ? page * PAGE_SIZE + 1 : 0}–{Math.min(rows.length, (page + 1) * PAGE_SIZE)} of {rows.length} contracts
          </p>
          <div className="flex items-center gap-3">
            <button onClick={() => setPage(page - 1)} disabled={page === 0} className="rounded-lg border border-line p-2 disabled:opacity-40" aria-label="Previous page">
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-sm">{page + 1} / {pages}</span>
            <button onClick={() => setPage(page + 1)} disabled={page >= pages - 1} className="rounded-lg border border-line p-2 disabled:opacity-40" aria-label="Next page">
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
