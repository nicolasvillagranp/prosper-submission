import { ParticipantKind, Room, RoomEvent, Track, type RemoteParticipant } from 'livekit-client'
import { useEffect, useRef, useState } from 'react'

import { navigate } from '../lib/router'
import { MAX_SESSION_MIN } from '../lib/supabase'
import type { LiveState } from './TopicPage'

// The live interview: joins the LiveKit room the token opens (the agent is dispatched with it),
// publishes the microphone, plays the expert, and shows the transcript the agent streams.

interface Line {
  id: string
  me: boolean
  text: string
}

type Phase = 'connecting' | 'waiting' | 'live' | 'ended' | 'error'

const clock = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

export default function Live() {
  const state = window.history.state as LiveState | null
  const [phase, setPhase] = useState<Phase>('connecting')
  const [agentState, setAgentState] = useState('')
  const [lines, setLines] = useState<Line[]>([])
  const [muted, setMuted] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState('')
  const room = useRef<Room | null>(null)
  const audioBox = useRef<HTMLDivElement | null>(null)
  const bottom = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!state) return navigate('/')
    const r = new Room()
    room.current = r
    let started = 0
    const tick = window.setInterval(() => started && setSeconds(Math.floor((Date.now() - started) / 1000)), 1000)

    const watchAgent = (p: RemoteParticipant) => {
      if (p.kind !== ParticipantKind.AGENT) return
      setPhase('live')
      started ||= Date.now()
      setAgentState(p.attributes['lk.agent.state'] ?? '')
    }
    r.on(RoomEvent.ParticipantConnected, watchAgent)
    r.on(RoomEvent.ParticipantAttributesChanged, (_changed, p) => {
      if (p.kind === ParticipantKind.AGENT) setAgentState(p.attributes['lk.agent.state'] ?? '')
    })
    r.on(RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === Track.Kind.Audio) audioBox.current?.appendChild(track.attach())
    })
    // The agent ends the call at the time limit (after saying goodbye) by deleting the room.
    r.on(RoomEvent.Disconnected, () => setPhase((p) => (p === 'error' ? p : 'ended')))
    r.registerTextStreamHandler('lk.transcription', async (reader, participant) => {
      const id = reader.info.attributes?.['lk.segment_id'] ?? reader.info.id
      const me = participant.identity === r.localParticipant.identity
      let text = ''
      for await (const delta of reader) {
        text += delta
        // Interim transcripts arrive as new streams for the same segment: the latest one wins.
        setLines((all) => {
          const i = all.findIndex((l) => l.id === id)
          const line = { id, me, text }
          return i < 0 ? [...all, line] : all.map((l, j) => (j === i ? line : l))
        })
      }
    })

    ;(async () => {
      try {
        await r.connect(state.url, state.token)
        await r.localParticipant.setMicrophoneEnabled(true)
        setPhase((p) => (p === 'connecting' ? 'waiting' : p))
        r.remoteParticipants.forEach(watchAgent)
      } catch (e) {
        setPhase('error')
        setError((e as Error).name === 'NotAllowedError' ? 'The microphone is blocked. Allow it in the browser and try again.' : 'Could not connect. Try again.')
        r.disconnect()
      }
    })()

    return () => {
      window.clearInterval(tick)
      r.disconnect()
    }
  }, [])

  // Braces matter: recent Chrome returns a Promise from scrollIntoView, and React would call it as a clean-up.
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' })
  }, [lines])

  if (!state) return null
  const back = () => navigate(`/topic/${state.topicId}`)
  const toggleMute = async () => {
    await room.current?.localParticipant.setMicrophoneEnabled(muted)
    setMuted(!muted)
  }
  const expertFirst = state.expert.split(' ')[0]
  const status =
    phase === 'connecting' ? 'Connecting…'
      : phase === 'waiting' ? `Waiting for ${expertFirst}…`
        : phase === 'ended' ? 'The interview has ended'
          : phase === 'error' ? error
            : agentState === 'speaking' ? `${expertFirst} is speaking`
              : agentState === 'thinking' ? `${expertFirst} is thinking…`
                : 'Listening to you'

  return (
    <div className="live">
      <div className="page">
        <header className="header">
          <div className="stack" style={{ gap: 4 }}>
            <span className="muted">Live interview · AI expert</span>
            <h2>With {state.expert}</h2>
          </div>
          <div className="row" style={{ gap: 12 }}>
          {state.record && phase !== 'ended' && <span className="rec"><span className="dot" />Recording</span>}
          <span style={{ fontSize: 22, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
            {clock(seconds)} <span className="muted" style={{ fontSize: 16 }}>/ {clock(MAX_SESSION_MIN * 60)}</span>
          </span>
          </div>
        </header>

        <div className="row" style={{ alignItems: 'stretch', gap: 22 }}>
          <section className="card" style={{ flex: '1 1 280px', alignItems: 'center', textAlign: 'center' }} aria-live="polite">
            <div className={`speaker ${agentState === 'speaking' ? 'speaking' : ''}`} aria-hidden="true">
              {state.expert.split(' ').slice(0, 2).map((w) => w[0]).join('')}
            </div>
            <div>
              <p style={{ fontSize: 18, fontWeight: 600 }} role="status">{status}</p>
              <p className="muted">Voice: {state.voiceName}</p>
            </div>
          </section>

          <section className="card" style={{ flex: '999 1 480px', minWidth: 0, maxHeight: '60vh', overflowY: 'auto' }} aria-label="Live transcript">
            <h3 className="muted">Live transcript</h3>
            {!lines.length && <p className="muted">The conversation will appear here.</p>}
            {lines.map((l) => (
              <div key={l.id} className={`bubble ${l.me ? 'me' : ''}`}>
                <b>{l.me ? 'You' : expertFirst}</b>
                <span>{l.text}</span>
              </div>
            ))}
            <div ref={bottom} />
          </section>
        </div>

        <div className="row" style={{ justifyContent: 'center', gap: 14 }}>
          {phase === 'ended' || phase === 'error' ? (
            <>
              <button type="button" className="btn" onClick={() => navigate('/episodes')}>Go to My episodes</button>
              <button type="button" className="btn" onClick={back}>Back to the topic</button>
            </>
          ) : (
            <>
              <button type="button" className="btn" onClick={toggleMute} aria-pressed={muted}>{muted ? 'Unmute' : 'Mute'}</button>
              <button type="button" className="btn danger" onClick={() => room.current?.disconnect()}>End interview</button>
            </>
          )}
        </div>
        <div ref={audioBox} hidden />
      </div>
    </div>
  )
}
