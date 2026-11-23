import { Mic, Volume2 } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { AgentState, TranscriptMessage } from '../types/simulator-types'
import { MessageBubble } from './message-bubble'
import { MessageComposer } from './message-composer'
import { SessionStatus } from './session-status'

interface ConversationPanelProps {
  messages: TranscriptMessage[]
  state: AgentState | null
  completed: boolean
  sending: boolean
  holdSeconds: number
  disposition: string | null
  onSend: (text: string) => Promise<boolean>
}

export function ConversationPanel({
  messages,
  state,
  completed,
  sending,
  holdSeconds,
  disposition,
  onSend,
}: ConversationPanelProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const disabled = !state || completed || sending

  return (
    <section className="workspace-card transcript-card">
      <div className="card-heading">
        <div>
          <p className="eyebrow">Conversation</p>
          <h2>Transcript workspace</h2>
        </div>
        <SessionStatus state={state} />
      </div>

      {holdSeconds > 0 && (
        <div className="hold-notice">
          The agent requested a {holdSeconds}-second hold. No silence was sent automatically.
        </div>
      )}

      {completed && (
        <div className="completion-notice">
          Conversation completed{disposition ? ` · ${disposition}` : ''}
        </div>
      )}

      <div className="transcript">
        {messages.length ? (
          messages.map((item) => <MessageBubble key={item.id} message={item} />)
        ) : (
          <div className="empty-transcript">
            <strong>No active conversation</strong>
            <p>Start a real backend session to view its transcript.</p>
          </div>
        )}
        {sending && <p className="processing">Agent is processing the message…</p>}
        <div ref={endRef} />
      </div>

      <MessageComposer disabled={disabled} onSend={onSend} />

      <div className="mode-row">
        <span>
          <Mic size={15} />
          Push-to-talk
        </span>
        <span>
          <Volume2 size={15} />
          Hands-free voice
        </span>
        <span>Available in a future milestone</span>
      </div>
    </section>
  )
}
