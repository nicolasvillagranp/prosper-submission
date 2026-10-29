// POST /api/signup {email, code?}: creates the account for an invited person, if there's room.
//
// Who is invited: when ALLOWED_EMAILS lists anyone, exactly those emails (no code needed, and the
// code alone isn't enough); otherwise whoever has INVITE_CODE. Admins are always invited.
// Public sign-ups are off in Supabase, so this (with the secret key) is the only way in. The page
// then sends the magic link itself (signInWithOtp with shouldCreateUser: false).

import { timingSafeEqual } from 'node:crypto'

import { fail, ok, type Result } from './http.js'

export interface SignupDeps {
  inviteCode: string
  allowedEmails: string[] // lower case; empty = use the invite code
  adminEmails: string[]
  maxUsers: number
  listEmails(): Promise<string[]>
  createUser(email: string): Promise<void>
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function sameCode(given: string, expected: string): boolean {
  const a = Buffer.from(given.trim())
  const b = Buffer.from(expected)
  return a.length === b.length && timingSafeEqual(a, b)
}

export async function signup(body: Record<string, unknown>, deps: SignupDeps): Promise<Result> {
  const email = String(body.email ?? '').trim().toLowerCase()
  const code = String(body.code ?? '')
  if (!EMAIL.test(email)) return fail(400, 'Enter a valid email address.')
  // Checked before anything else, so this endpoint never tells strangers who has an account.
  if (!deps.adminEmails.includes(email)) {
    if (deps.allowedEmails.length) {
      if (!deps.allowedEmails.includes(email)) return fail(403, "This email isn't on the invite list.")
    } else if (!sameCode(code, deps.inviteCode)) {
      return { status: 403, body: { ok: false, needs_code: true, error: code ? "That invite code isn't right." : 'Enter your invite code.' } }
    }
  }

  const emails = await deps.listEmails()
  if (emails.includes(email)) return ok({ existing: true })
  if (emails.length >= deps.maxUsers) return fail(403, 'All invitations are taken for now.')
  await deps.createUser(email)
  return ok({ existing: false })
}
