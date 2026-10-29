import { useEffect, useRef, useState } from 'react'

import { useCovers } from '../lib/covers'
import { Markdown } from '../lib/markdown'
import { goTo, navigate } from '../lib/router'
import { api, MAX_SESSION_MIN, supabase } from '../lib/supabase'
import type { Briefing, Topic } from '../lib/types'
import { accentLabel, sampleUrl, voice, voiceOptions } from '../lib/voices'

const initials = (name: string) => name.split(' ').slice(0, 2).map((w) => w[0]).join('')

export interface LiveState {
  url: string
  token: string
  topicId: string
  expert: string
  voiceName: string
  record: boolean
}

/** The audio briefing: asked for on first open, made by the Docker worker, then cached. */
function BriefingPlayer({ topic }: { topic: Topic }) {
  const [briefing, setBriefing] = useState<Briefing | null | undefined>(undefined)
  const [audioUrl, setAudioUrl] = useState('')
  const [showScript, setShowScript] = useState(false)

  useEffect(() => {
    let alive = true
    let timer: number | undefined
    async function poll() {
      const { data } = await supabase.from('briefings').select('*').eq('topic_id', topic.id).maybeSingle()
      if (!alive) return
      const b = data as Briefing | null
      setBriefing(b)
      if (b?.status === 'ready' && b.audio_path) {
        const { data: signed } = await supabase.storage.from('recordings').createSignedUrl(b.audio_path, 3600)
        if (alive && signed) setAudioUrl(signed.signedUrl)
      } else if (b && (b.status === 'requested' || b.status === 'working')) {
        timer = window.setTimeout(poll, 3000)
      }
    }
    poll()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [topic.id, briefing?.status === 'requested'])

  async function request() {
    const row = { topic_id: topic.id, user_id: (await supabase.auth.getUser()).data.user!.id, status: 'requested' }
    const { error } = briefing ? await supabase.from('briefings').update({ status: 'requested' }).eq('topic_id', topic.id)
      : await supabase.from('briefings').insert(row)
    if (!error) setBriefing({ topic_id: topic.id, status: 'requested', audio_path: null, script: null, error: null })
  }

  const making = briefing?.status === 'requested' || briefing?.status === 'working'
  return (
    <section className="card dark" aria-label="Audio briefing">
      {briefing === undefined ? (
        <p className="muted">Loading…</p>
      ) : briefing?.status === 'ready' ? (
        <>
          <div className="row between">
            <strong>Today's briefing · about 3 minutes</strong>
            <button type="button" className="btn small" style={{ background: 'transparent', color: '#fff', borderColor: '#3a3f48' }}
              onClick={() => setShowScript(!showScript)} aria-expanded={showScript}>
              {showScript ? 'Hide transcript' : 'Transcript'}
            </button>
          </div>
          {audioUrl && <audio controls src={audioUrl} style={{ width: '100%' }} />}
          {showScript && briefing.script && (
            <div className="stack" style={{ color: '#d4d8df', fontSize: 15 }}>
              {briefing.script.split('\n\n').map((p, i) => <p key={i}>{p}</p>)}
            </div>
          )}
        </>
      ) : making ? (
        <div className="stack" role="status">
          <strong>Preparing your briefing…</strong>
          <p className="muted">Writing the script and recording the narration. It takes about a minute, the first time only.</p>
        </div>
      ) : (
        <div className="row between">
          <div className="stack" style={{ gap: 4 }}>
            <strong>{briefing?.status === 'failed' ? "The briefing couldn't be made." : 'Listen to a 3-minute briefing first'}</strong>
            <p className="muted">{briefing?.status === 'failed' ? 'Try again in a moment.' : 'A narrated summary of the story, made just for you.'}</p>
          </div>
          <button type="button" className="btn primary" onClick={request}>
            {briefing?.status === 'failed' ? 'Try again' : 'Make the audio briefing'}
          </button>
        </div>
      )}
    </section>
  )
}

export default function TopicPage({ topicId }: { topicId: string }) {
  const [topic, setTopic] = useState<Topic | null | undefined>(undefined)
  const [voiceId, setVoiceId] = useState('')
  const [starting, setStarting] = useState(false)
  const [record, setRecord] = useState(true)
  const [error, setError] = useState('')
  const sample = useRef<HTMLAudioElement | null>(null)
  const interviewRef = useRef<HTMLElement | null>(null)
  const covers = useCovers(topic ? [topic] : [], topic?.user_id ?? '')

  useEffect(() => {
    supabase.from('topics').select('*').eq('id', topicId).maybeSingle().then(({ data }) => {
      const t = data as Topic | null
      setTopic(t)
      if (t) setVoiceId(voiceOptions(t)[0].voice_id)
    })
  }, [topicId])

  useEffect(() => {
    if (topic && window.location.hash === '#interview') interviewRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [topic])

  function playSample(id: string) {
    sample.current?.pause()
    sample.current = new Audio(sampleUrl(id))
    sample.current.play()
  }

  async function start() {
    if (!topic) return
    setStarting(true)
    setError('')
    const res = await api<{ url: string; token: string }>('/api/token', { topic_id: topic.id, voice_id: voiceId, record })
    setStarting(false)
    if (!res.ok) return setError(res.error ?? 'Could not start the interview.')
    const state: LiveState = { url: res.url, token: res.token, topicId: topic.id, expert: topic.persona.name, voiceName: voice(voiceId).name, record }
    navigate('/live', state)
  }

  if (topic === undefined) return <p className="muted">Loading…</p>
  if (topic === null) return <p>Topic not found. <a href="/" onClick={goTo}>Back to today</a></p>

  const first = topic.persona.name.split(' ')[0]
  return (
    <>
      <a href="/" onClick={goTo} style={{ fontWeight: 600, textDecoration: 'none' }}>← Today's edition</a>
      {covers[topic.id] && <img className="cover" src={covers[topic.id]} alt="" style={{ aspectRatio: '21 / 9' }} />}
      <div className="stack" style={{ gap: 10 }}>
        <span className="kicker">No. {topic.rank} · {topic.sources.length} sources from the past week</span>
        <h1 style={{ fontSize: 'clamp(30px, 4.4vw, 44px)' }}>{topic.title}</h1>
        <p style={{ color: 'var(--ink-2)', fontSize: 17, lineHeight: 1.6 }}>{topic.summary}</p>
      </div>

      <BriefingPlayer topic={topic} />

      <div className="row" style={{ alignItems: 'flex-start', gap: 22 }}>
        <section ref={interviewRef} id="interview" className="card" aria-label="Interview the expert" style={{ flex: '999 1 520px', minWidth: 0 }}>
          <div className="row" style={{ gap: 14, flexWrap: 'nowrap' }}>
            <span className="avatar big" aria-hidden="true">{initials(topic.persona.name)}</span>
            <div>
              <h2>Interview {topic.persona.name}</h2>
              <p className="muted">Fictional expert (AI) · {topic.persona.expertise}</p>
            </div>
          </div>
          <p style={{ background: 'var(--ground)', borderRadius: 12, padding: '14px 16px', color: 'var(--ink-2)', fontSize: 15 }}>
            <strong>{first}'s take:</strong> {topic.config.stance}
          </p>

          <div className="stack" style={{ gap: 10 }}>
            <div className="row between">
              <h3>Pick {first}'s voice</h3>
              <span className="muted small">Scored by AI for this persona</span>
            </div>
            {voiceOptions(topic).map((o, i) => {
              const v = voice(o.voice_id)
              const on = o.voice_id === voiceId
              return (
                <div key={o.voice_id} className={`voice ${on ? 'on' : ''}`}>
                  <button type="button" className="voice-pick" aria-pressed={on} onClick={() => setVoiceId(o.voice_id)}>
                    <span className="radio" aria-hidden="true" />
                    <span className="stack" style={{ gap: 2 }}>
                      <span><strong>{v.name}</strong> <span className="muted">· {accentLabel(v.accent)}</span></span>
                      {o.why && <span className="muted small">{o.why}</span>}
                    </span>
                  </button>
                  {o.score > 0 && <span className="score">{i === 0 ? 'Best match · ' : ''}{o.score}/100</span>}
                  <button type="button" className="btn small" onClick={() => playSample(o.voice_id)} aria-label={`Play a sample of ${v.name}`}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 4v16l13-8z" /></svg>
                    Sample
                  </button>
                </div>
              )
            })}
          </div>

          <label className="row" style={{ gap: 10, padding: '12px 14px', border: '1px solid var(--line)', borderRadius: 2, cursor: 'pointer', fontWeight: 500 }}>
            <input type="checkbox" checked={record} onChange={(e) => setRecord(e.target.checked)} style={{ width: 20, height: 20, accentColor: 'var(--ink)' }} />
            Record this episode <span className="muted small">· you'll find the mp3 in My episodes</span>
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <button type="button" className="btn record" onClick={start} disabled={starting}>
            <span className="dot" style={{ background: '#fff' }} />
            {starting ? 'Starting…' : `Start the interview with ${voice(voiceId).name} · up to ${MAX_SESSION_MIN} min`}
          </button>
          <p className="muted small" style={{ textAlign: 'center' }}>Allow the microphone when asked. Headphones help.</p>
        </section>

        <aside className="stack" style={{ flex: '1 1 300px', gap: 16 }}>
          <section className="card">
            <h3>Your study guide</h3>
            <Markdown text={topic.study_dialogue} />
          </section>
          <section className="card">
            <h3>Sources</h3>
            {topic.sources.map((s) => (
              <a key={s.n} href={s.url} target="_blank" rel="noreferrer" style={{ fontSize: 14, textDecoration: 'none', color: 'var(--ink)' }}>
                <span style={{ color: 'var(--accent)', fontWeight: 600 }}>[{s.n}]</span> {s.title}{' '}
                <span className="muted">· {s.publisher}</span>
              </a>
            ))}
          </section>
        </aside>
      </div>
    </>
  )
}
