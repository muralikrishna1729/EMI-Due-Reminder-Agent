import type { AgentState, StartConversationResponse, TextTurnResponse } from '../types/simulator-types'

const REQUEST_TIMEOUT_MS = 20_000
const agentStates = new Set<AgentState>(['GREETING', 'VERIFYING', 'NEGOTIATING', 'ENDED'])

export type SimulatorErrorKind = 'validation' | 'uncertain'

export class SimulatorApiError extends Error {
  readonly kind: SimulatorErrorKind
  readonly status?: number

  constructor(kind: SimulatorErrorKind, message: string, status?: number) {
    super(message)
    this.name = 'SimulatorApiError'
    this.kind = kind
    this.status = status
  }
}

export async function startConversation(accountId: string): Promise<StartConversationResponse> {
  const payload = await post('/api/calls', { account_id: accountId.trim().toUpperCase() })

  if (!isStartConversationResponse(payload)) {
    throw new SimulatorApiError('uncertain', 'The server returned an incomplete session response.')
  }

  return {
    sessionId: payload.session_id,
    reply: payload.reply,
    state: payload.state,
  }
}

export async function submitTextTurn(sessionId: string, text: string): Promise<TextTurnResponse> {
  const payload = await post(`/api/calls/${encodeURIComponent(sessionId)}/turn`, { text })

  if (!isTextTurnResponse(payload)) {
    throw new SimulatorApiError('uncertain', 'The server returned an incomplete turn response.')
  }

  return {
    reply: payload.reply,
    state: payload.state,
    ended: payload.ended,
    disposition: payload.disposition,
    holdSeconds: payload.hold_seconds,
  }
}

async function post(path: string, body: Record<string, string>): Promise<unknown> {
  const controller = new AbortController()
  const timeout = globalThis.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
    const payload = await readJson(response)

    if (!response.ok) {
      const message = getErrorMessage(payload, response.status)
      if (response.status >= 400 && response.status < 500) {
        throw new SimulatorApiError('validation', message, response.status)
      }
      throw new SimulatorApiError('uncertain', message, response.status)
    }

    return payload
  } catch (error) {
    if (error instanceof SimulatorApiError) {
      throw error
    }
    throw new SimulatorApiError(
      'uncertain',
      'The connection was interrupted before the server response could be confirmed.',
    )
  } finally {
    globalThis.clearTimeout(timeout)
  }
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    throw new SimulatorApiError(
      response.ok ? 'uncertain' : response.status >= 500 ? 'uncertain' : 'validation',
      response.ok ? 'The server returned an invalid response.' : 'The server returned an unreadable error response.',
      response.status,
    )
  }
}

function getErrorMessage(payload: unknown, status: number): string {
  if (isRecord(payload) && typeof payload.detail === 'string') {
    return payload.detail
  }
  return status >= 500
    ? 'The service could not confirm the request outcome.'
    : 'The request could not be completed.'
}

function isStartConversationResponse(value: unknown): value is {
  session_id: string
  reply: string
  state: AgentState
} {
  return (
    isRecord(value) &&
    typeof value.session_id === 'string' &&
    value.session_id.length > 0 &&
    typeof value.reply === 'string' &&
    isAgentState(value.state)
  )
}

function isTextTurnResponse(value: unknown): value is {
  reply: string
  state: AgentState
  ended: boolean
  disposition: string | null
  hold_seconds: number
} {
  return (
    isRecord(value) &&
    typeof value.reply === 'string' &&
    isAgentState(value.state) &&
    typeof value.ended === 'boolean' &&
    (typeof value.disposition === 'string' || value.disposition === null) &&
    typeof value.hold_seconds === 'number' &&
    Number.isFinite(value.hold_seconds)
  )
}

function isAgentState(value: unknown): value is AgentState {
  return typeof value === 'string' && agentStates.has(value as AgentState)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
