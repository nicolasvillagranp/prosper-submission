import { useState } from 'react'

import { supabase } from '../lib/supabase'
import type { Depth, Language, Profile, Tone } from '../lib/types'

// The preferences, shared by onboarding and Settings.

const CHIPS = ['AI', 'Robotics', 'EU policy', 'Climate', 'Economy', 'Startups', 'Science', 'Health', 'Sports', 'Culture']

const GROUPS: {
  key: 'language' | 'depth' | 'tone'
  title: string
  hint: string
  options: [Language | Depth | Tone, string, string][]
}[] = [
  { key: 'language', title: 'Podcast language', hint: 'news, briefing and expert; the app stays in English',
    options: [['en', 'English', 'English voices'], ['es', 'Español', 'Voices from Spain and Mexico']] },
  { key: 'depth', title: 'Level', hint: 'how technical it gets',
    options: [['beginner', 'Beginner', 'No jargon, with analogies'], ['intermediate', 'Intermediate', 'You follow the news'], ['expert', 'Expert', 'Straight to the point']] },
  { key: 'tone', title: "Expert's tone", hint: 'how they answer in the interview',
    options: [['explainer', 'Explainer', 'Patient, step by step'], ['balanced', 'Balanced', 'Clear, with opinions'], ['sparring', 'Sparring', 'Pushes back on you']] },
]

const has = (text: string, word: string) => new RegExp(`(^|[\\s,.;:])${word}($|[\\s,.;:])`, 'i').test(text)

export default function ProfileForm({ userId, initial, submitLabel, onSaved }: {
  userId: string
  initial?: Profile
  submitLabel: string
  onSaved: (p: Profile) => void
}) {
  const [p, setP] = useState<Profile>(initial ?? { user_id: userId, interests: '', language: 'en', depth: 'intermediate', tone: 'balanced' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  const set = (patch: Partial<Profile>) => {
    setP({ ...p, ...patch })
    setSaved(false)
  }

  function toggleChip(word: string) {
    if (has(p.interests, word)) {
      set({ interests: p.interests.replace(new RegExp(`(,\\s*)?\\b${word}\\b`, 'i'), '').replace(/^[\s,]+/, '') })
    } else {
      set({ interests: p.interests.trim() ? `${p.interests.trim().replace(/[.,]$/, '')}, ${word}` : word })
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault()
    if (p.interests.trim().length < 3) return setError('Tell us at least one interest.')
    setBusy(true)
    setError('')
    const { data, error } = await supabase.from('profiles')
      .upsert({ user_id: userId, interests: p.interests.trim(), language: p.language, depth: p.depth, tone: p.tone })
      .select().single()
    setBusy(false)
    if (error) return setError("Couldn't save. Try again.")
    setSaved(true)
    onSaved(data as Profile)
  }

  return (
    <form onSubmit={save} className="stack" style={{ gap: 22 }}>
      <section className="card">
        <h2>Interests</h2>
        <label htmlFor="interests">What should we talk about every morning? Write it the way you'd tell a friend.</label>
        <textarea id="interests" rows={3} value={p.interests} onChange={(e) => set({ interests: e.target.value })}
          placeholder="e.g. AI and robotics, how they change work, and European tech policy" />
        <div className="chips" aria-label="Add with one tap">
          {CHIPS.map((c) => {
            const on = has(p.interests, c)
            return (
              <button type="button" key={c} className={`chip ${on ? 'on' : ''}`} aria-pressed={on} onClick={() => toggleChip(c)}>
                {on ? '✓' : '+'} {c}
              </button>
            )
          })}
        </div>
      </section>
      <section className="card">
        <h2>Your podcast</h2>
        {GROUPS.map((g) => (
          <fieldset key={g.key} className="stack" style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="row" style={{ gap: 10, marginBottom: 10 }}>
              <strong style={{ fontSize: 15 }}>{g.title}</strong>
              <span className="muted">{g.hint}</span>
            </legend>
            <div className="options">
              {g.options.map(([id, label, sub]) => (
                <button type="button" key={id} className={`option ${p[g.key] === id ? 'on' : ''}`}
                  aria-pressed={p[g.key] === id} onClick={() => set({ [g.key]: id } as Partial<Profile>)}>
                  <strong>{label}</strong>
                  <small>{sub}</small>
                </button>
              ))}
            </div>
          </fieldset>
        ))}
      </section>
      <div className="row between">
        <span className={saved ? 'success' : 'muted'} role="status">
          {saved ? "Saved. Tomorrow's topics will use these settings." : 'You can change this any time in Settings.'}
        </span>
        {error && <span className="error" role="alert">{error}</span>}
        <button className="btn primary" disabled={busy}>{busy ? 'Saving…' : submitLabel}</button>
      </div>
    </form>
  )
}
