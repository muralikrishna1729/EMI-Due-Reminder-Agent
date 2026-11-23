import type { TranscriptMessage } from '../types/simulator-types'
export function MessageBubble({ message }: { message: TranscriptMessage }) {
  const time = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date(message.createdAt))
  return <article className={`message-bubble ${message.role}`}><p>{message.text}</p><span>{message.status === 'unconfirmed' ? 'Unconfirmed · ' : ''}{time}</span></article>
}
