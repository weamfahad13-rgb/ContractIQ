import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import './index.css'
import AppLayout from './components/AppLayout'
import Chat from './pages/Chat'
import Contracts from './pages/Contracts'
import Evaluation from './pages/Evaluation'
import Landing from './pages/Landing'
import NotFound from './pages/NotFound'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route element={<AppLayout />}>
          <Route path="/chat" element={<Chat />} />
          <Route path="/contracts" element={<Contracts />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
