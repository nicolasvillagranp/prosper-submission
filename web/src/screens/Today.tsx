import { useEffect, useState } from 'react'

import { useCovers } from '../lib/covers'
import { goTo, navigate } from '../lib/router'
import { supabase } from '../lib/supabase'
import type { Profile, Topic } from '../lib/types'

/** The expert's take, cut to its first sentence: the pull quote. */
const firstSentence = (text: string) => (text.match(/^.*?[.!?](\s|$)/)?.[0] ?? text).trim()

function Cover({ url, rank, alt, ratio }: { url?: string; rank: number; alt: string; ratio: string }) {
  return url
    ? <img className="cover" src={url} alt={alt} style={{ aspectRatio: ratio }} />
    : <div className="cover-blank" style={{ aspectRatio: ratio }} aria-hidden="true">{rank}</div>
}

export default function Today({ profile }: { profile: Profile }) {
  const [topics, setTopics] = useState<Topic[] | null>(null)
  const [ready, setReady] = useState<Set<string>>(new Set())
  const covers = useCovers(topics ?? [], profile.user_id)

  useEffect(() => {
    let alive = true
    let timer: number | undefined
    async function load() {
      // The latest day that has topics (today after 6:00, or the first batch right after onboarding).
      const { data } = await supabase.from('topics').select('*').order('date', { ascending: false }).order('rank').limit(10)
      const rows = (data ?? []) as Topic[]
      const latest = rows.filter((t) => t.date === rows[0]?.date)
      if (!alive) return
      setTopics(latest)
      if (latest.length) {
        const { data: b } = await supabase.from('briefings').select('topic_id').eq('status', 'ready').in('topic_id', latest.map((t) => t.id))
        if (alive) setReady(new Set((b ?? []).map((r) => r.topic_id as string)))
      } else {
        timer = window.setTimeout(load, 15000) // first topics still being prepared
      }
    }
    load()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [profile.user_id])

  if (topics === null) return <p className="muted">Loading…</p>

  if (!topics.length) {
    return (
      <section className="card" role="status">
        <h1>Your first edition is on the press…</h1>
        <p>We're reading this week's news on your interests, picking five stories and inventing an expert for each. It takes about 3 to 5 minutes; this page updates by itself.</p>
        <p className="muted">After today, a new edition is ready every morning at 6:00.</p>
      </section>
    )
  }

  const [lead, ...rest] = topics
  const leadFirst = lead.persona.name.split(' ')[0]
  return (
    <>
      <article className="lead">
        <a href={`/topic/${lead.id}`} onClick={goTo} aria-label={lead.title}>
          <Cover url={covers[lead.id]} rank={lead.rank} alt="" ratio="21 / 9" />
        </a>
        <div className="lead-body">
          <div className="lead-text">
            <span className="kicker">Story of the day · {lead.sources.length} sources</span>
            <h1 style={{ fontSize: 'clamp(30px, 4.4vw, 44px)' }}>
              <a href={`/topic/${lead.id}`} onClick={goTo} style={{ color: 'inherit', textDecoration: 'none' }}>{lead.title}</a>
            </h1>
            <p style={{ fontSize: 17, lineHeight: 1.6, color: 'var(--ink-2)' }}>{lead.summary}</p>
          </div>
          <aside className="lead-aside">
            <p className="quote">“{firstSentence(lead.config.stance)}”</p>
            <span className="muted">— {lead.persona.name}, your expert today</span>
            <div className="row" style={{ gap: 10 }}>
              <button type="button" className="btn primary" onClick={() => navigate(`/topic/${lead.id}`)}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 4v16l13-8z" /></svg>
                {ready.has(lead.id) ? 'Listen' : 'Make the briefing'}
              </button>
              <a className="btn" href={`/topic/${lead.id}#interview`} onClick={goTo}>Interview {leadFirst}</a>
            </div>
          </aside>
        </div>
      </article>

      <div className="stories">
        {rest.map((t) => (
          <a key={t.id} className="story" href={`/topic/${t.id}`} onClick={goTo}>
            <Cover url={covers[t.id]} rank={t.rank} alt="" ratio="3 / 2" />
            <div className="stack" style={{ gap: 8, minWidth: 0 }}>
              <span className="kicker">No. {t.rank} · {t.sources.length} sources</span>
              <h2>{t.title}</h2>
              <span className="muted">with {t.persona.name}{ready.has(t.id) ? ' · briefing ready' : ''}</span>
            </div>
          </a>
        ))}
      </div>
    </>
  )
}
