import { Outlet } from 'react-router-dom'

import { AppNav } from './Nav'

export default function AppLayout() {
  return (
    <div className="page-glow flex min-h-screen flex-col">
      <AppNav />
      <main className="mx-auto flex w-full max-w-[1400px] flex-1 flex-col px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
