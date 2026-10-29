// The real dependencies of the /api functions: Supabase with the secret key, and LiveKit.

import { randomUUID } from 'node:crypto'

import { createClient } from '@supabase/supabase-js'
import { AccessToken, RoomAgentDispatch, RoomConfiguration } from 'livekit-server-sdk'

import { env } from './http.js'
import type { SignupDeps } from './signup.js'
import type { TokenDeps } from './token.js'

const emailList = (value?: string) => (value ?? '').split(',').map((e) => e.trim().toLowerCase()).filter(Boolean)

function admin() {
  return createClient(env('SUPABASE_URL'), env('SUPABASE_SECRET_KEY'), {
    auth: { autoRefreshToken: false, persistSession: false },
  })
}

export function signupDeps(): SignupDeps {
  const db = admin()
  return {
    inviteCode: env('INVITE_CODE'),
    allowedEmails: emailList(process.env.ALLOWED_EMAILS),
    adminEmails: emailList(process.env.ADMIN_EMAILS),
    maxUsers: Number(process.env.MAX_USERS || 20),
    async listEmails() {
      const { data, error } = await db.auth.admin.listUsers({ page: 1, perPage: 1000 })
      if (error) throw error
      return data.users.map((u) => (u.email ?? '').toLowerCase())
    },
    async createUser(email) {
      const { error } = await db.auth.admin.createUser({ email, email_confirm: true })
      if (error) throw error
    },
  }
}

export function tokenDeps(): TokenDeps {
  const db = admin()
  return {
    dailyCap: Number(process.env.DAILY_SESSIONS_PER_USER || 15),
    livekitUrl: env('LIVEKIT_URL'),
    async userFromJwt(jwt) {
      const { data, error } = await db.auth.getUser(jwt)
      return error || !data.user ? null : { id: data.user.id, email: data.user.email ?? '' }
    },
    async topicOwner(topicId) {
      const { data } = await db.from('topics').select('user_id').eq('id', topicId).maybeSingle()
      return data?.user_id ?? null
    },
    async sessionsSince(userId, sinceIso) {
      const { count, error } = await db.from('sessions').select('id', { count: 'exact', head: true })
        .eq('user_id', userId).gte('started_at', sinceIso)
      if (error) throw error
      return count ?? 0
    },
    async createSession(row) {
      const { data, error } = await db.from('sessions').insert(row).select('id').single()
      if (error) throw error
      return data.id as string
    },
    async sign(identity, name, room, agentMetadata) {
      const at = new AccessToken(env('LIVEKIT_API_KEY'), env('LIVEKIT_API_SECRET'), { identity, name, ttl: '1h' })
      at.addGrant({ room, roomJoin: true, canPublish: true, canSubscribe: true })
      at.roomConfig = new RoomConfiguration({
        agents: [new RoomAgentDispatch({ agentName: process.env.AGENT_NAME || 'expert', metadata: agentMetadata })],
      })
      return at.toJwt()
    },
    newId: randomUUID,
    now: () => new Date(),
  }
}
