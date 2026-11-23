import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/app-shell'
import { CallsPage } from './features/calls/calls-page'
import { EscalationsPage } from './features/escalations/escalations-page'
import { OverviewPage } from './features/overview/overview-page'
import { SimulatorPage } from './features/simulator/simulator-page'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="simulator" element={<SimulatorPage />} />
        <Route path="calls" element={<CallsPage />} />
        <Route path="escalations" element={<EscalationsPage />} />
      </Route>
      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  )
}
