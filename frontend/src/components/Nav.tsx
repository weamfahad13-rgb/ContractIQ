import { NavLink, Link } from 'react-router-dom'
import { FileText } from 'lucide-react'

/** `compact` hides the name on phones so the app nav tabs fit. */
export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="flex shrink-0 items-center gap-2.5 text-xl font-bold tracking-tight" aria-label="ContractIQ home">
      <FileText className="h-7 w-7 text-accent" strokeWidth={2.2} aria-hidden />
      <span className={compact ? 'hidden sm:inline' : undefined}>ContractIQ</span>
    </Link>
  )
}

const tabs = [
  { to: '/chat', label: 'Chat' },
  { to: '/contracts', label: 'Contracts' },
  { to: '/evaluation', label: 'Evaluation' },
]

export function AppNav() {
  return (
    <header className="border-b border-line bg-ink-950/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-4 px-4 sm:px-6">
        <Logo compact />
        <nav className="flex gap-1 sm:gap-6">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              className={({ isActive }) =>
                `border-b-2 px-1.5 py-5 text-sm font-medium transition sm:px-2 sm:text-base ${
                  isActive ? 'border-accent text-accent' : 'border-transparent text-slate-200 hover:text-white'
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
        <div className="hidden w-[140px] sm:block" />
      </div>
    </header>
  )
}
