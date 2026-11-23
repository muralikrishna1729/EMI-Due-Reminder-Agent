import { CircleAlert } from 'lucide-react'
import { ConversationPanel } from './components/conversation-panel'
import { SessionSetup } from './components/session-setup'
import { useSimulator } from './hooks/use-simulator'

export function SimulatorPage() {
  const simulator = useSimulator()
  const setupDisabled = simulator.status === 'active' || simulator.status === 'completed'

  return (
    <div className="workspace-grid">
      <div>
        <SessionSetup
          accountId={simulator.accountId}
          disabled={setupDisabled}
          isCreating={simulator.isCreating}
          uncertainty={simulator.uncertainty}
          onAccountChange={simulator.setAccountId}
          onStart={() => void simulator.startSession()}
          onAcknowledge={simulator.acknowledgeUncertainSession}
          onFresh={simulator.startFreshSession}
        />
        {simulator.error && <div className="simulator-error"><CircleAlert size={17} />{simulator.error}</div>}
      </div>
      <ConversationPanel
        messages={simulator.messages}
        state={simulator.agentState}
        completed={simulator.status === 'completed'}
        sending={simulator.isSending}
        holdSeconds={simulator.holdSeconds}
        disposition={simulator.disposition}
        onSend={simulator.sendMessage}
      />
    </div>
  )
}
