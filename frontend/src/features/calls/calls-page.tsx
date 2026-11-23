import type { ReactNode } from 'react'
import { Clock3, DatabaseZap } from 'lucide-react'

export function CallsPage() {
  return (
    <EmptyIntegration
      icon={<Clock3 size={25} />}
      title="Call history is ready for its data source"
      description="The backend does not currently expose a call-history endpoint, so no records are shown here. This workspace will connect to real conversation records when that API is available."
    />
  )
}

interface EmptyIntegrationProps {
  icon: ReactNode
  title: string
  description: string
}

export function EmptyIntegration({
  icon,
  title,
  description,
}: EmptyIntegrationProps) {
  return (
    <section className="empty-page">
      <div className="empty-icon">{icon}</div>
      <p className="eyebrow">Integration pending</p>
      <h2>{title}</h2>
      <p>{description}</p>
      <div className="endpoint-note">
        <DatabaseZap size={16} />
        Waiting for a dedicated backend endpoint
      </div>
    </section>
  )
}
