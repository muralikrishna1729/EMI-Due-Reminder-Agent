import { AudioLines, ChevronRight, CircleHelp, Clock3, LayoutDashboard, ShieldAlert } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { ConnectionStatus } from '@/components/shared/connection-status'

const navigation = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/simulator', label: 'Live Simulator', icon: AudioLines },
  { to: '/calls', label: 'Call History', icon: Clock3 },
  { to: '/escalations', label: 'Escalations', icon: ShieldAlert },
]

export function Sidebar({ open, onNavigate }: { open: boolean; onNavigate: () => void }) {
  return (
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
      <div className="brand">
        <span className="brand-mark">EV</span>
        <div>
          <strong>EMI Voice Agent</strong>
          <span>Agent Operations Console</span>
        </div>
      </div>
      <nav aria-label="Primary navigation">
        <p className="nav-label">Workspace</p>
        {navigation.map(({ to, label, icon: Icon }) => (
          <NavLink
            end={to === '/'}
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            <Icon size={18} />
            <span>{label}</span>
            <ChevronRight size={15} />
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <ConnectionStatus />
        <div className="environment">
          <CircleHelp size={15} />
          <span>Development environment</span>
        </div>
      </div>
    </aside>
  )
}
