import { createClient } from '@supabase/supabase-js'

// The publishable key: everything the page reads or writes goes through RLS (supabase/migrations).
export const supabase = createClient(import.meta.env.VITE_SUPABASE_URL, import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY)

export const ADMIN_EMAILS = String(import.meta.env.VITE_ADMIN_EMAILS || '')
  .split(',')
  .map((e) => e.trim().toLowerCase())
  .filter(Boolean)

export const MAX_SESSION_MIN = Number(import.meta.env.VITE_MAX_SESSION_MIN || 20)

/** POST to one of our /api functions, signed in when there's a session. */
export async function api<T>(path: string, body: unknown): Promise<T & { ok: boolean; error?: string }> {
  const { data } = await supabase.auth.getSession()
  const headers: Record<string, string> = { 'content-type': 'application/json' }
  if (data.session) headers.authorization = `Bearer ${data.session.access_token}`
  const res = await fetch(path, { method: 'POST', headers, body: JSON.stringify(body) })
  return res.json().catch(() => ({ ok: false, error: 'Something went wrong. Try again.' }))
}
