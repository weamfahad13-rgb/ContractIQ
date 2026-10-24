import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Outlet, Route, Routes } from 'react-router-dom'

import './index.css'
import { AppNav } from './components/Nav'
import Chat from './pages/Chat'
import Contracts from './pages/Contracts'
import Evaluation from './pages/Evaluation'
import Landing from './pages/Landing'

function AppLayout() {
  return (
    <div className="page-glow flex min-h-screen flex-col">
      <AppNav />
      <main className="mx-auto flex w-full max-w-[1400px] flex-1 flex-col px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route element={<AppLayout />}>
          <Route path="/chat" element={<Chat />} />
          <Route path="/contracts" element={<Contracts />} />
          <Route path="/evaluation" element={<Evaluation />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
