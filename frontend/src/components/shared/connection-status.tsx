import { CircleAlert, LoaderCircle, Radio } from 'lucide-react'
import { useHealth } from '@/features/overview/api/health'

interface ConnectionStatusProps {
  compact?: boolean
}

export function ConnectionStatus({ compact = false }: ConnectionStatusProps) {
  const health = useHealth()
  const online = health.isSuccess && health.data.status.toLowerCase() === 'ok'
  const Icon = health.isPending ? LoaderCircle : online ? Radio : CircleAlert

  const label = compact
    ? online
      ? 'Connected'
      : health.isPending
        ? 'Checking'
        : 'Unavailable'
    : health.isPending
      ? 'Checking connection'
      : online
        ? 'Backend connected'
        : 'Backend unavailable'

  return (
    <div
      className={`connection-status ${online ? 'is-online' : 'is-offline'}`}
      title={health.error?.message}
    >
      <Icon
        aria-hidden="true"
        className={health.isPending ? 'spin' : ''}
        size={15}
      />
      <span>{label}</span>
    </div>
  )
}
