import type { AgentState } from '../types/simulator-types'

const labels: Record<AgentState, string> = { GREETING: 'Greeting', VERIFYING: 'Verifying identity', NEGOTIATING: 'Payment discussion', ENDED: 'Completed' }

export function SessionStatus({ state }: { state: AgentState | null }) {
  return <span className="state-badge">{state ? labels[state] : 'Awaiting session'}</span>
}
