// The shapes stored in Supabase (mirrors schema/models.py).

export type Language = 'es' | 'en'
export type Depth = 'beginner' | 'intermediate' | 'expert'
export type Tone = 'explainer' | 'balanced' | 'sparring'

export interface Profile {
  user_id: string
  interests: string
  language: Language
  depth: Depth
  tone: Tone
}

export interface VoiceOption {
  voice_id: string
  score: number
  why: string
}

export interface Topic {
  id: string
  user_id: string
  date: string
  rank: number
  title: string
  summary: string
  persona: { name: string; background: string; expertise: string; default_stance: string; speaking_style: string }
  config: { language: Language; stance: string; tts: { voice_id: string }; voice_options?: VoiceOption[] }
  brief: string
  study_dialogue: string
  sources: { n: number; title: string; url: string; date?: string | null; publisher?: string | null }[]
}

export interface Briefing {
  topic_id: string
  status: 'requested' | 'working' | 'ready' | 'failed'
  audio_path: string | null
  script: string | null
  error: string | null
}
