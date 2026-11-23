import { Send } from 'lucide-react'
import { useState, type KeyboardEvent } from 'react'

interface MessageComposerProps {
  disabled: boolean
  onSend: (text: string) => Promise<boolean>
}

export function MessageComposer({ disabled, onSend }: MessageComposerProps) {
  const [draft, setDraft] = useState('')

  const submit = async () => {
    if (!draft.trim() || disabled) {
      return
    }
    if (await onSend(draft)) {
      setDraft('')
    }
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void submit()
    }
  }

  return (
    <div className="composer">
      <textarea
        aria-label="Message agent"
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type a message to the agent"
        rows={2}
      />
      <button
        aria-label="Send message"
        disabled={disabled || !draft.trim()}
        onClick={() => void submit()}
      >
        <Send size={18} />
      </button>
    </div>
  )
}
