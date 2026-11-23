import { Menu, X } from 'lucide-react'
import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { ConnectionStatus } from '@/components/shared/connection-status'
import { Sidebar } from './sidebar'

const pageMeta: Record<string, { title: string; description: string }> = {
  '/': {
    title: 'Overview',
    description: 'Monitor the foundation of your EMI outreach operation.',
  },
  '/simulator': {
    title: 'Live Simulator',
    description: 'Prepare the conversation workspace for an agent session.',
  },
  '/calls': {
    title: 'Call History',
    description: 'Review completed conversations when a history API is available.',
  },
  '/escalations': {
    title: 'Escalations',
    description: 'Manage cases that require human follow-up.',
  },
}

export function AppShell() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const meta = pageMeta[location.pathname] ?? pageMeta['/']

  return (
    <div className="app-shell">
      <Sidebar open={open} onNavigate={() => setOpen(false)} />
      {open && (
        <button className="scrim" aria-label="Close navigation" onClick={() => setOpen(false)} />
      )}
      <main className="main-panel">
        <header className="topbar">
          <button
            className="mobile-menu"
            aria-label={open ? 'Close navigation' : 'Open navigation'}
            onClick={() => setOpen(!open)}
          >
            {open ? <X /> : <Menu />}
          </button>
          <div>
            <p className="eyebrow">Agent Operations Console</p>
            <h1>{meta.title}</h1>
            <p className="page-description">{meta.description}</p>
          </div>
          <ConnectionStatus compact />
        </header>
        <div className="page-content">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
