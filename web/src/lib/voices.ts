import listing from '../voices.json'
import type { Topic, VoiceOption } from './types'

// voices.json and public/voices/*.mp3 are written by `python -m pipeline.voice_samples`
// from config/voices.yaml, the one list of allowed voices.

export interface Voice {
  id: string
  name: string
  gender: string
  accent: string
  language: string
}

const VOICES = listing as Record<string, Omit<Voice, 'id'>>

export function voice(id: string): Voice {
  const v = VOICES[id]
  return v ? { id, ...v } : { id, name: 'Voice', gender: '', accent: '', language: '' }
}

export const sampleUrl = (id: string) => `/voices/${id}.mp3`

const ACCENT: Record<string, string> = { 'es-ES': 'Spain', 'es-MX': 'Mexico', en: 'English' }
export const accentLabel = (accent: string) => ACCENT[accent] ?? accent

/** The voices to offer for this expert: Claude's top 3, or just the topic's voice for older topics. */
export function voiceOptions(topic: Topic): VoiceOption[] {
  const scored = topic.config.voice_options ?? []
  return scored.length ? scored : [{ voice_id: topic.config.tts.voice_id, score: 0, why: '' }]
}
