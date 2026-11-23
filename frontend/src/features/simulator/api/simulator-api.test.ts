import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  SimulatorApiError,
  startConversation,
  submitTextTurn,
} from './simulator-api'

describe('simulator API', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('normalizes the account identifier and returns a validated session', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ session_id: 'session-1', reply: 'Hello', state: 'GREETING' }), {
        status: 200,
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(startConversation(' acc-88392 ')).resolves.toEqual({
      sessionId: 'session-1',
      reply: 'Hello',
      state: 'GREETING',
    })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/calls',
      expect.objectContaining({ body: JSON.stringify({ account_id: 'ACC-88392' }), method: 'POST' }),
    )
  })

  it('rejects a malformed successful turn response as uncertain', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ reply: 'Missing state' }), { status: 200 })))
    await expect(submitTextTurn('session-1', 'Hello')).rejects.toMatchObject({ kind: 'uncertain' })
  })

  it('classifies validation errors as safe to correct', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Unknown Account' }), { status: 404 })))
    await expect(startConversation('UNKNOWN')).rejects.toMatchObject({ kind: 'validation', message: 'Unknown Account', status: 404 } satisfies Partial<SimulatorApiError>)
  })

  it('classifies a network failure as uncertain', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(submitTextTurn('session-1', 'Hello')).rejects.toMatchObject({ kind: 'uncertain' })
  })
})
