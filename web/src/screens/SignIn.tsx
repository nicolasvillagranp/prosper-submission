import { useState } from 'react'

import { Brand } from '../components/Header'
import { api, supabase } from '../lib/supabase'

// Email magic link. Public sign-ups are off in Supabase: an unknown email is asked for the invite
// code, /api/signup creates the account, and then the link is sent.

type Step = 'email' | 'code' | 'sent'

export default function SignIn() {
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function sendLink(): Promise<boolean> {
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { shouldCreateUser: false, emailRedirectTo: window.location.origin },
    })
    if (!error) return true
    if (/signups? not allowed|not found|user not found/i.test(error.message)) return false
    throw new Error(error.message.includes('rate') ? 'Too many emails sent. Wait a few minutes and try again.' : error.message)
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (step === 'email' && (await sendLink())) return setStep('sent') // already has an account
      // New here: invited emails get an account straight away; otherwise the invite code is asked for.
      const res = await api<{ needs_code?: boolean }>('/api/signup', step === 'code' ? { email, code } : { email })
      if (!res.ok) {
        if (res.needs_code && step === 'email') return setStep('code')
        throw new Error(res.error)
      }
      if (await sendLink()) setStep('sent')
      else throw new Error('Something went wrong. Try again.')
    } catch (err) {
      setError((err as Error).message || 'Something went wrong. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page" style={{ maxWidth: 520 }}>
      <Brand />
      <form className="card" onSubmit={submit}>
        {step === 'sent' ? (
          <>
            <h1>Check your inbox</h1>
            <p>We sent a sign-in link to <strong>{email}</strong>. Open it on this device.</p>
            <button type="button" className="btn" onClick={() => setStep('email')}>Use another email</button>
          </>
        ) : (
          <>
            <h1>{step === 'code' ? 'You need an invitation' : 'Sign in'}</h1>
            <p className="muted">
              {step === 'code'
                ? "This podcast is invite-only for now. Enter the code you were given."
                : 'Every morning, five stories from the news you care about. Listen to a short briefing, then interview an AI expert about it.'}
            </p>
            <div className="stack">
              <label htmlFor="email">Email</label>
              <input id="email" type="email" required autoComplete="email" value={email}
                onChange={(e) => setEmail(e.target.value)} disabled={step === 'code'} />
            </div>
            {step === 'code' && (
              <div className="stack">
                <label htmlFor="code">Invite code</label>
                <input id="code" type="text" required autoFocus value={code} onChange={(e) => setCode(e.target.value)} />
              </div>
            )}
            {error && <p className="error" role="alert">{error}</p>}
            <button className="btn primary" disabled={busy}>
              {busy ? 'Sending…' : step === 'code' ? 'Join and send my link' : 'Send me a sign-in link'}
            </button>
            {step === 'code' && <button type="button" className="btn" onClick={() => setStep('email')}>Back</button>}
          </>
        )}
      </form>
    </div>
  )
}
