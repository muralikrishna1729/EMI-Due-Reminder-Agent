import { LoaderCircle, Play, RotateCcw } from 'lucide-react'
import type { SessionUncertainty } from '../types/simulator-types'

interface SessionSetupProps {
  accountId: string
  disabled: boolean
  isCreating: boolean
  uncertainty: SessionUncertainty
  onAccountChange: (value: string) => void
  onStart: () => void
  onAcknowledge: () => void
  onFresh: () => void
}

export function SessionSetup({
  accountId,
  disabled,
  isCreating,
  uncertainty,
  onAccountChange,
  onStart,
  onAcknowledge,
  onFresh,
}: SessionSetupProps) {
  if (uncertainty) {
    return (
      <section className="workspace-card session-card">
        <p className="eyebrow">Outcome unconfirmed</p>
        <h2>Backend reconciliation is unavailable</h2>
        <p className="helper-text">
          The backend may have processed the previous request. Starting a new test session will not terminate any earlier backend session.
        </p>
        <button className="primary-action" onClick={onAcknowledge}>
          I understand, start a fresh session
        </button>
      </section>
    )
  }

  if (disabled) {
    return (
      <section className="workspace-card session-card">
        <p className="eyebrow">Active session</p>
        <h2>Conversation in progress</h2>
        <p className="helper-text">
          This workspace is connected to the current backend session.
        </p>
        <button className="secondary-action" onClick={onFresh}>
          <RotateCcw size={16} />
          Start another test session
        </button>
      </section>
    )
  }

  return (
    <section className="workspace-card session-card">
      <p className="eyebrow">Session setup</p>
      <h2>Start a test conversation</h2>
      <label>
        Demo account ID
        <input
          value={accountId}
          onChange={(event) => onAccountChange(event.target.value)}
          placeholder="Enter an account ID"
          disabled={isCreating}
        />
      </label>
      <button
        className="primary-action"
        disabled={isCreating}
        onClick={onStart}
      >
        {isCreating ? (
          <LoaderCircle className="spin" size={16} />
        ) : (
          <Play size={16} />
        )}
        {isCreating ? 'Starting conversation' : 'Start conversation'}
      </button>
    </section>
  )
}
