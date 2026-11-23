import { useMutation } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { SimulatorApiError, startConversation, submitTextTurn } from '../api/simulator-api'
import type { AgentState, SessionUncertainty, TranscriptMessage } from '../types/simulator-types'

type SessionStatus = 'idle' | 'active' | 'completed'

function message(role: TranscriptMessage['role'], text: string, status: TranscriptMessage['status'] = 'confirmed'): TranscriptMessage {
  return { id: crypto.randomUUID(), role, text, status, createdAt: new Date().toISOString() }
}

export function useSimulator() {
  const creationLock = useRef(false)
  const turnLock = useRef(false)
  const [accountId, setAccountId] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [agentState, setAgentState] = useState<AgentState | null>(null)
  const [messages, setMessages] = useState<TranscriptMessage[]>([])
  const [status, setStatus] = useState<SessionStatus>('idle')
  const [disposition, setDisposition] = useState<string | null>(null)
  const [holdSeconds, setHoldSeconds] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [uncertainty, setUncertainty] = useState<SessionUncertainty>(null)

  const createMutation = useMutation({ mutationFn: startConversation, retry: false })
  const turnMutation = useMutation({ mutationFn: ({ id, text }: { id: string; text: string }) => submitTextTurn(id, text), retry: false })
  const activeOrUncertain = status === 'active' || uncertainty !== null

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (activeOrUncertain) event.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [activeOrUncertain])

  useEffect(() => {
    const confirmNavigation = (event: MouseEvent) => {
      const target = event.target
      if (!activeOrUncertain || !(target instanceof Element)) return
      const link = target.closest('a[href]')
      if (link && !window.confirm('Leave this active session? The backend session will remain active.')) {
        event.preventDefault()
      }
    }
    document.addEventListener('click', confirmNavigation, true)
    return () => document.removeEventListener('click', confirmNavigation, true)
  }, [activeOrUncertain])

  const startSession = useCallback(async () => {
    const normalized = accountId.trim()
    if (!normalized) { setError('Enter an account ID to start a conversation.'); return }
    if (creationLock.current || createMutation.isPending || uncertainty === 'creation') return
    creationLock.current = true; setError(null)
    try {
      const result = await createMutation.mutateAsync(normalized)
      setSessionId(result.sessionId); setAgentState(result.state); setMessages([message('agent', result.reply)]); setStatus('active')
    } catch (caught) {
      const apiError = caught as SimulatorApiError
      setError(apiError.message)
      if (apiError.kind === 'uncertain') setUncertainty('creation')
    } finally { creationLock.current = false }
  }, [accountId, createMutation, uncertainty])

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || !sessionId || status !== 'active' || uncertainty || turnLock.current || turnMutation.isPending) return false
    turnLock.current = true; setError(null); setHoldSeconds(0)
    const customerMessage = message('customer', trimmed)
    setMessages((current) => [...current, customerMessage])
    try {
      const result = await turnMutation.mutateAsync({ id: sessionId, text: trimmed })
      setMessages((current) => [...current, message('agent', result.reply)])
      setAgentState(result.state); setHoldSeconds(result.holdSeconds); setDisposition(result.disposition)
      if (result.ended) setStatus('completed')
      return true
    } catch (caught) {
      const apiError = caught as SimulatorApiError
      setError(apiError.message)
      if (apiError.kind === 'uncertain') {
        setMessages((current) => current.map((item) => item.id === customerMessage.id ? { ...item, status: 'unconfirmed' } : item))
        setUncertainty('turn')
      }
      return false
    } finally { turnLock.current = false }
  }, [sessionId, status, uncertainty, turnMutation])

  const acknowledgeUncertainSession = () => { setUncertainty(null); setError(null); setStatus('idle'); setSessionId(null); setMessages([]); setAgentState(null) }
  const startFreshSession = () => { setUncertainty(null); setError(null); setStatus('idle'); setSessionId(null); setMessages([]); setAgentState(null); setDisposition(null); setHoldSeconds(0) }

  return { accountId, setAccountId, agentState, messages, status, disposition, holdSeconds, error, uncertainty, startSession, sendMessage, acknowledgeUncertainSession, startFreshSession, isCreating: createMutation.isPending, isSending: turnMutation.isPending }
}
