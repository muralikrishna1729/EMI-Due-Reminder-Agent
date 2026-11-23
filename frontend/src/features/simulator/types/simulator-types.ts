export type AgentState = 'GREETING' | 'VERIFYING' | 'NEGOTIATING' | 'ENDED'

export interface StartConversationResponse {
  sessionId: string
  reply: string
  state: AgentState
}

export interface TextTurnResponse {
  reply: string
  state: AgentState
  ended: boolean
  disposition: string | null
  holdSeconds: number
}

export interface TranscriptMessage {
  id: string
  role: 'agent' | 'customer'
  text: string
  createdAt: string
  status?: 'confirmed' | 'unconfirmed'
}

export type SessionUncertainty = 'creation' | 'turn' | null
