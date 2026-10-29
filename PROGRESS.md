# Progress

| Task | Status | Notes |
|---|---|---|
| T0 Scaffold | ✅ done | Repo, pinned deps, config, `.env.example`. Checkpoint 0 done: all keys in `.env` and tested. |
| T1 Data model | ✅ done | Models, voice allowlist, Spanish sample topic (world models, 7 real sources), migration applied. Verified: 3 tables, RLS rejects anon writes (42501), private `recordings` bucket, public sign-ups off. |
| T2 Expert agent | ✅ done | `python -m agent.expert` (console, sample topic). Prompt cached after turn 1 (~3.6k tokens). Text test: LLM first token 0.5–1.1 s from the laptop; Cartesia + Deepgram round-trip hears Genie/DeepMind/lidar right. Checkpoint 1 (2026-10-25): user talked to it in console; latency OK for them, voice sounded robotic (6 voice samples compared). Polish later: voice choice, answer length, turn-taking; the console log only lives in the terminal, so save session logs to a file. |
| T3 Morning job | ✅ done | `python -m pipeline.run_daily`. 32 tests. Two real runs (no DB) for a Spanish AI/robotics/EU-regulation profile: 5 valid topics each, 3–5 sources, briefs cited, 5 distinct experts with gender-matched voices, 2–6 min. Saving run (2026-10-27) for test user nicolasvillagranprieto@gmail.com (`ad1e2187-…`): 5 topics in Supabase, the agent loads them. |
| E1 Audio briefing (on demand, selected topic only) | 🟡 code done | `pipeline/briefing.py` (`python -m pipeline.briefing <topic_id> --out x.mp3`). Claude Sonnet writes a script for the ear, Cartesia sonic-3 reads it as mp3 with a narrator voice (Luis es / Marian en, never given to experts), cached in Storage `recordings/<user_id>/briefings/<topic_id>.mp3` + `.txt`. 40 tests. Real run: 531 words, ~2:40 min, 59 s to make the first time. Waiting: user listens. |
| D1 Internal dashboard | — | |
| T4 Docker + worker + Vercel functions | ✅ done | Docker `podcast` (agent `expert` + worker). Migration 002 (briefings queue) applied; briefing request → worker → ready in 47 s. `web/api/signup.ts` (invite code, user cap) and `web/api/token.ts` (JWT, topic ownership, daily cap, session row, LiveKit token dispatching the agent with topic/session/record/voice). Real test: signed-in test user → token → agent joined the room in 1.2 s. 45 Python + 11 TS tests. |
| T5 Web page | 🟡 code done | React app in `web/src`: sign-in (magic link + invite code), onboarding, Today, Topic (briefing request/player + transcript, Claude-scored voice picker with samples, start interview), Live (LiveKit room, mic, agent audio, live transcript, agent state, timer, mute/end), Settings, Admin (mocked). `npm run build` OK; 13 TS + 47 Python tests. **Waiting: Test 1 by the user.** |
| T6 Sessions + recording + My episodes | ✅ done | Agent saves the transcript on hang-up and, if "Record this episode" is ticked, LiveKit's recorder audio (stereo ogg) as a mono mp3 in `recordings/<user_id>/sessions/<session_id>.mp3` (`agent/episodes.py`). Recording is explicit: `record={"audio": <choice>, traces/logs/transcript off}` (1.8.8 otherwise follows the LiveKit Cloud project setting). Page: record checkbox + "Recording" badge, `/episodes` (cover, date, minutes, player, transcript, Download mp3). Real test: 24 s mono mp3 + transcript saved. 57 Python + 18 TS tests. Test 2 passed (user, 2026-10-28). |
| T7 Deploy (Vercel + laptop agent) | 🟡 deployed | https://prosper-submission.vercel.app (root `web`, 12 env vars). Functions fixed with `.js` import extensions; Vercel Hobby blocked deploys of commits authored by `nvquantrue`, so history was rewritten to `nicolasvillagranp`. Sign-in works on Vercel. **Waiting: Test 4** (full flow from the Vercel URL with Docker running). |
| T8 Submission (`solution.md` + demo video) + runbook | ✅ done | The demo video replaces `sample.mp3` (user's choice). |

## Decisions

- T5 decisions (2026-10-28): React for the page; a new user's first topics are generated right after onboarding (then daily at 06:00); Claude scores the voices for each expert (best 3 shown, with a fixed sample per voice); sign-in by email magic link only (Supabase's free plan sends only a few emails per hour: a mail provider if the demo needs more); `/admin` only for `ADMIN_EMAILS`.

- Web tooling pinned to Node-20-compatible versions (Vite 6, Vitest 3, TypeScript 5); `npm run dev` turns on Node 20's WebSocket flag (supabase-js needs it); Vercel runs Node 22. New npm dependency vs the plan: `livekit-server-sdk` (the TS twin of `livekit-api`, for the token function); Vitest for the TS tests.

- Separate repo from the Orbio assignment; no remote until deploy (T7), and then a private one.
- LiveKit only carries the audio (rooms, tokens, agent dispatch). STT and TTS call Deepgram and Cartesia directly with their own keys, as backend-layer's agent does.
- LLM: Anthropic. Haiku for the live expert, Sonnet for the morning job (`config/config.yaml`).
- No turn-detector model to start with (VAD + endpointing only, as in the screening agent), to fit Render's 512 MB worker. Revisit after checkpoint 1. LiveKit 1.8.8 turns one on by default, so the agent sets `turn_detection: "vad"`.
- No `temperature` in the topic config: the Claude 5 models reject the parameter.
- Morning job: the code numbers the sources, so the LLM never writes a URL. The editor step invents all 5 expert names at once (distinct, mixed genders); the writer only sees voices of that gender. Voice emotion off, speed 1.0 (emotion sounded forced at checkpoint 1).
- Sonnet calls use the server-side refusal fallback (`fallbacks: "default"`).
- PyAV 19.0.2 comes with livekit-agents, so recordings (T6) can be OGG without a new dependency.
- Supabase for auth, data and storage. Hosting (2026-10-27, replaces Render): Vercel for page + `/token`, agent and morning job on the user's laptop.

- Profile fields: interests, language (es/en), depth, tone. The spec's `register` is `audience_level` (pydantic models already have a `register` method).
- Voices: only Cartesia stock voices listed in `config/voices.yaml`; the schema rejects anything else, so no cloned or imitated voices.
- Sign-up: public sign-ups off in Supabase; the web server creates accounts after checking the invite code and `MAX_USERS` (T4), so the code can't be bypassed through the Supabase API.
- Sample topic lives in `samples/world-models.json` so the agent (T2) can be tested before the morning job exists.

## Possible enhancements (for solution.md)

- Voice provider per use (2026-10-27): Cartesia for everything for now. ElevenLabs is usually more natural for long narration (the briefing); Cartesia wins on latency for the live interview. A provider setting per use (briefing vs interview) is a contained change: `pipeline/briefing.py` makes one HTTP call per chunk; the agent would need `livekit-plugins-elevenlabs` and an ElevenLabs voice allowlist.

## Open issues


- Latency: if checkpoint 1 misses 1 s, options in order: lower `min_endpointing_ms`, `preemptive_tts`, a smaller prompt, a faster model.

- The agent only works while the laptop runs `python -m agent.expert dev`.
