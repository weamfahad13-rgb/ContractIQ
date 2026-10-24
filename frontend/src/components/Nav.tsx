import { NavLink, Link } from 'react-router-dom'
import { FileText } from 'lucide-react'

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5 text-xl font-bold tracking-tight">
      <FileText className="h-7 w-7 text-accent" strokeWidth={2.2} aria-hidden />
      ContractIQ
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
        <Logo />
        <nav className="flex gap-1 sm:gap-6">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              className={({ isActive }) =>
                `border-b-2 px-2 py-5 text-sm font-medium transition sm:text-base ${
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
