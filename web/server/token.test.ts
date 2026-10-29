import { describe, expect, it } from 'vitest'

import { startOfDayUtc, token, type TokenDeps } from './token'

const NOW = new Date('2026-10-28T09:30:00Z')

function deps(overrides: Partial<TokenDeps> = {}) {
  const sessions: Record<string, unknown>[] = []
  const signed: { identity: string; room: string; metadata: string }[] = []
  const d: TokenDeps = {
    dailyCap: 3,
    livekitUrl: 'wss://example.livekit.cloud',
    userFromJwt: async (jwt) => (jwt === 'good' ? { id: 'u1', email: 'u1@x.com' } : null),
    topicOwner: async (id) => ({ t1: 'u1', t2: 'u2' } as Record<string, string>)[id] ?? null,
    sessionsSince: async () => 1,
    createSession: async (row) => {
      sessions.push(row)
      return 's-1'
    },
    sign: async (identity, _name, room, metadata) => {
      signed.push({ identity, room, metadata })
      return 'livekit-jwt'
    },
    newId: () => 'abc',
    now: () => NOW,
    ...overrides,
  }
  return { d, sessions, signed }
}

describe('token', () => {
  it('records the session and returns a token that dispatches the expert', async () => {
    const { d, sessions, signed } = deps()
    const r = await token('Bearer good', { topic_id: 't1', record: true, voice_id: 'v9' }, d)
    expect(r).toEqual({
      status: 200,
      body: { ok: true, url: 'wss://example.livekit.cloud', token: 'livekit-jwt', room: 'interview-abc', session_id: 's-1' },
    })
    expect(sessions).toEqual([{ user_id: 'u1', topic_id: 't1', room: 'interview-abc', record: true }])
    expect(signed[0].identity).toBe('u1')
    expect(JSON.parse(signed[0].metadata)).toEqual({ topic_id: 't1', session_id: 's-1', record: true, voice_id: 'v9' })
  })

  it('needs a valid sign-in', async () => {
    const { d } = deps()
    expect((await token(null, { topic_id: 't1' }, d)).status).toBe(401)
    expect((await token('Bearer bad', { topic_id: 't1' }, d)).status).toBe(401)
  })

  it("hides someone else's topic", async () => {
    const { d, sessions } = deps()
    expect((await token('Bearer good', { topic_id: 't2' }, d)).status).toBe(404)
    expect((await token('Bearer good', {}, d)).status).toBe(404)
    expect(sessions).toEqual([])
  })

  it('enforces the daily cap from midnight UTC', async () => {
    let since = ''
    const { d, sessions } = deps({
      sessionsSince: async (_u, s) => {
        since = s
        return 3
      },
    })
    const r = await token('Bearer good', { topic_id: 't1' }, d)
    expect(r.status).toBe(429)
    expect(since).toBe('2026-10-28T00:00:00.000Z')
    expect(sessions).toEqual([])
  })

  it('records only when asked', async () => {
    const { d, sessions } = deps()
    await token('Bearer good', { topic_id: 't1', record: 'yes' }, d)
    expect(sessions[0].record).toBe(false)
  })

  it('computes the start of the UTC day', () => {
    expect(startOfDayUtc(new Date('2026-10-28T23:59:59+02:00'))).toBe('2026-10-28T00:00:00.000Z')
  })
})
