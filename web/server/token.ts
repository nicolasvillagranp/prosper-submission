// POST /api/token {topic_id, record?, voice_id?} with "Authorization: Bearer <Supabase access token>".
//
// Checks who is asking, that the topic is theirs and the daily interview cap, records the session,
// and returns a LiveKit token whose room dispatches the expert agent with the topic to play.

import { fail, ok, type Result } from './http.js'

export interface TokenDeps {
  dailyCap: number
  livekitUrl: string
  userFromJwt(jwt: string): Promise<{ id: string; email: string } | null>
  topicOwner(topicId: string): Promise<string | null>
  sessionsSince(userId: string, sinceIso: string): Promise<number>
  createSession(row: { user_id: string; topic_id: string; room: string; record: boolean }): Promise<string>
  sign(identity: string, name: string, room: string, agentMetadata: string): Promise<string>
  newId(): string
  now(): Date
}

export function startOfDayUtc(now: Date): string {
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())).toISOString()
}

export async function token(authorization: string | null, body: Record<string, unknown>, deps: TokenDeps): Promise<Result> {
  const jwt = authorization?.match(/^Bearer (.+)$/)?.[1]
  const user = jwt ? await deps.userFromJwt(jwt) : null
  if (!user) return fail(401, 'Please sign in again.')

  const topicId = String(body.topic_id ?? '')
  if (!topicId || (await deps.topicOwner(topicId)) !== user.id) return fail(404, 'Topic not found.')

  if ((await deps.sessionsSince(user.id, startOfDayUtc(deps.now()))) >= deps.dailyCap) {
    return fail(429, `You've done your ${deps.dailyCap} interviews for today. Come back tomorrow!`)
  }

  const record = body.record === true
  const room = `interview-${deps.newId()}`
  const sessionId = await deps.createSession({ user_id: user.id, topic_id: topicId, room, record })
  // The agent checks voice_id against config/voices.yaml, so any value here is safe.
  const voiceId = typeof body.voice_id === 'string' && body.voice_id ? body.voice_id : undefined
  const metadata = JSON.stringify({ topic_id: topicId, session_id: sessionId, record, voice_id: voiceId })
  const jwtForRoom = await deps.sign(user.id, user.email, room, metadata)
  return ok({ url: deps.livekitUrl, token: jwtForRoom, room, session_id: sessionId })
}
