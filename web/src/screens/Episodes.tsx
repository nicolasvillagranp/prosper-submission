import { useEffect, useState } from 'react'

import { useCovers } from '../lib/covers'
import { goTo } from '../lib/router'
import { supabase } from '../lib/supabase'

// My episodes: every finished interview, newest first. Recorded ones play and download as mp3
// (recordings/<user_id>/sessions/<session_id>.mp3, written by the agent when the call ends).

interface Episode {
  id: string
  started_at: string
  ended_at: string
  recording_path: string | null
  transcript: { speaker: 'host' | 'expert'; text: string }[] | null
  topic_id: string
  topics: { title: string; persona: { name: string } } | null
}

const minutes = (e: Episode) => Math.max(1, Math.round((Date.parse(e.ended_at) - Date.parse(e.started_at)) / 60000))
const day = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })

function Recording({ path, title }: { path: string; title: string }) {
  const [play, setPlay] = useState('')
  const [download, setDownload] = useState('')
  useEffect(() => {
    const bucket = supabase.storage.from('recordings')
    const file = `${title.replace(/[^\p{L}\p{N} ]+/gu, '').trim().slice(0, 60) || 'episode'}.mp3`
    bucket.createSignedUrl(path, 3600).then(({ data }) => data && setPlay(data.signedUrl))
    bucket.createSignedUrl(path, 3600, { download: file }).then(({ data }) => data && setDownload(data.signedUrl))
  }, [path, title])
  return (
    <div className="row" style={{ gap: 14, marginTop: 6 }}>
      {play && <audio controls preload="none" src={play} style={{ flex: '1 1 260px', minWidth: 0 }} />}
      {download && (
        <a className="btn small" href={download} style={{ borderColor: 'var(--ink)' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 4v12" /><path d="m6 10 6 6 6-6" /><path d="M4 20h16" />
          </svg>
          Download mp3
        </a>
      )}
    </div>
  )
}

export default function Episodes({ userId }: { userId: string }) {
  const [episodes, setEpisodes] = useState<Episode[] | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const covers = useCovers((episodes ?? []).map((e) => ({ id: e.topic_id })), userId)

  useEffect(() => {
    supabase.from('sessions')
      .select('id, started_at, ended_at, recording_path, transcript, topic_id, topics(title, persona)')
      .not('ended_at', 'is', null)
      .order('started_at', { ascending: false })
      .then(({ data }) => setEpisodes((data ?? []) as unknown as Episode[]))
  }, [userId])

  if (episodes === null) return <p className="muted">Loading…</p>

  const total = episodes.reduce((sum, e) => sum + minutes(e), 0)
  return (
    <>
      <div className="row between" style={{ alignItems: 'flex-end' }}>
        <div className="stack" style={{ gap: 6 }}>
          <span className="kicker">Your archive · {episodes.length} episode{episodes.length === 1 ? '' : 's'} · {total} minutes on air</span>
          <h1 style={{ fontSize: 'clamp(32px, 4.4vw, 44px)' }}>My episodes</h1>
        </div>
        <p className="muted" style={{ maxWidth: 360 }}>Every interview you've done. Recorded ones can be played and downloaded as mp3.</p>
      </div>

      {!episodes.length ? (
        <section className="card">
          <h2>No episodes yet</h2>
          <p>Pick a story from <a href="/" onClick={goTo}>today's edition</a>, tick "Record this episode" and interview the expert. It will show up here when you hang up.</p>
        </section>
      ) : (
        <div className="stack" style={{ gap: 0, borderTop: '2px solid var(--ink)' }}>
          {episodes.map((e) => {
            const title = e.topics?.title ?? 'Interview'
            const isOpen = open === e.id
            return (
              <article key={e.id} className="stack" style={{ gap: 16, padding: '24px 0', borderBottom: '1px solid var(--line-strong)' }}>
                <div className="row" style={{ gap: 22, alignItems: 'flex-start' }}>
                  {covers[e.topic_id]
                    ? <img className="cover" src={covers[e.topic_id]} alt="" style={{ width: 200, aspectRatio: '3 / 2', flex: '0 0 auto' }} />
                    : <div className="cover-blank" aria-hidden="true" style={{ width: 200, aspectRatio: '3 / 2', flex: '0 0 auto', fontSize: 28 }}>♪</div>}
                  <div className="stack" style={{ gap: 8, flex: '999 1 360px', minWidth: 0 }}>
                    <span className="kicker">{day(e.started_at)} · {minutes(e)} min{e.recording_path ? ' · recorded' : ''}</span>
                    <h2 style={{ fontSize: 24 }}>{title}</h2>
                    <span className="muted">with {e.topics?.persona.name ?? 'the expert'}</span>
                    {e.recording_path
                      ? <Recording path={e.recording_path} title={title} />
                      : <span className="muted" style={{ fontStyle: 'italic' }}>Not recorded · transcript only</span>}
                  </div>
                </div>
                {!!e.transcript?.length && (
                  <button type="button" onClick={() => setOpen(isOpen ? null : e.id)} aria-expanded={isOpen}
                    style={{ alignSelf: 'flex-start', minHeight: 40, padding: 0, border: 0, background: 'transparent', color: 'var(--accent)', fontWeight: 600, cursor: 'pointer' }}>
                    {isOpen ? 'Hide transcript' : 'Read transcript'}
                  </button>
                )}
                {isOpen && (
                  <div className="card" style={{ maxWidth: 760, gap: 14 }}>
                    {e.transcript!.map((l, i) => (
                      <p key={i} style={{ fontSize: 15, lineHeight: 1.6 }}>
                        <strong style={{ fontFamily: 'var(--display)', color: l.speaker === 'expert' ? 'var(--accent)' : 'var(--ink)' }}>
                          {l.speaker === 'expert' ? (e.topics?.persona.name.split(' ')[0] ?? 'Expert') : 'You'}
                        </strong>{' '}
                        {l.text}
                      </p>
                    ))}
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
    </>
  )
}
