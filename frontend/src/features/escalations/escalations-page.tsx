import { ShieldAlert } from 'lucide-react'
import { EmptyIntegration } from '@/features/calls/calls-page'

export function EscalationsPage() {
  return (
    <EmptyIntegration
      icon={<ShieldAlert size={25} />}
      title="Escalation management is awaiting integration"
      description="A dedicated escalation-list endpoint has not been exposed by the backend. Cases, ownership, and resolution actions will appear here only when real operational data can be requested."
    />
  )
}
