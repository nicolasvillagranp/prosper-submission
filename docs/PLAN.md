# Action plan — Daily AI-expert interviews

## Context

A web app where each user sets their interests once, and **every morning gets ~5 ready-to-record interview topics**. Each topic comes with a fictional AI expert persona made for it, a research brief, and a study dialogue the user reads before asking their own questions. The user picks one and talks to the expert live in the browser.

The live agent is the simple part: it's the root project's [voice/agent.py](voice/agent.py) pattern (LiveKit Agents on the existing LiveKit Cloud project, STT/TTS via LiveKit Inference) with an LLM and a prompt full of facts. The real work is the loop around it: onboarding, user profiles, the morning job, and picking a topic.

**Decisions made with the user**
- New separate repo `…\Escritorio\personal\podcast`; private GitHub remote only when deploying (push is a HUMAN step).
- LLM: Anthropic (`claude-haiku-5-5` live, `claude-sonnet-5-5` in the morning job).
- No Docker, no Android/PWA, no phone calls. Web page only.
- **Many users, capped** (invite code at sign-up, `MAX_USERS` e.g. 20).
- **Profile fields** (all editable later in Settings): interests (free-text prompt), language, depth (beginner ↔ expert), expert tone (friendly explainer ↔ sparring partner). Changes apply from the next morning's run.
- **Supabase** for auth (email magic link), Postgres (profiles, topics, sessions) and Storage (optional recordings). Free tier covers this.
- **Hosting (changed 2026-10-27, Orbio-style):** Vercel serves the static page and two small TypeScript functions (`/api/signup`, `/api/token`); the browser talks to Supabase directly under RLS. Docker Compose on the laptop runs the agent and a worker (audio briefings on request + the 06:00 morning job). Render was the original plan and is dropped. Isolated from Orbio where it matters: own Supabase, Docker project and repo. LiveKit and API keys are shared on purpose (different agent names).

## Architecture

```
Browser ──login, profile, topics (supabase-js, RLS)──► Supabase (Auth · Postgres · Storage)
   │                                                     ▲            ▲
   └──POST /token (Supabase JWT)──► Render web ──dispatch topic_id──► LiveKit Cloud room ◄──WebRTC── Browser
                                                                        │
                                              Render worker (expert agent) ── reads topic, writes transcript ──► Supabase
Render cron 06:00 ── per user: news → 5 topics (persona + brief + study dialogue) ──► Supabase
```

## Data model (Supabase, `supabase/migrations/001_init.sql`, RLS on every table)
- `profiles` (user_id PK → auth.users, interests text, language, depth, tone, updated_at). User can read/update own row.
- `topics` (id, user_id, date, rank 1–5, title, summary, persona jsonb, config jsonb, brief md, study_dialogue md, sources jsonb). User reads own; only the cron (service role) writes.
- `sessions` (id, user_id, topic_id, room, started_at, ended_at, transcript jsonb, recording_path). User reads own; worker writes.
- Storage bucket `recordings` (private, path `<user_id>/<session_id>/host.ogg|agent.ogg`).
- pydantic models mirror `config` and `persona` (spec T1 fields: stance, register, answer_length, language, tts voice/speed/emotion, llm model, endpointing…); `voice_id` limited to an allowlist of Cartesia stock voices per language; personas always fictional.

## Tasks

Each task: build → check → PROGRESS.md → commit `T<n>: <summary>`.

**T0 Scaffold.** Repo layout (`agent/ pipeline/ web_server/ web/ schema/ supabase/ tests/`), pinned `requirements.txt` (`livekit-agents[silero,turn-detector,anthropic]==1.8.8`, `livekit-api==1.2.2`, `supabase`, `anthropic`, `tavily-python`, `trafilatura`, `feedparser`, `fastapi`), `.env.example`, README, PROGRESS.md. **HUMAN 0:** create the Supabase project, fill `.env` (LiveKit keys from the root project, Anthropic, Tavily, Supabase URL/anon/service keys).

**T1 Data model.** Migration + RLS policies, pydantic models, one hand-written sample topic seeded for a test user. **Check:** `pytest tests/test_schema.py` (sample validates; voice not in allowlist fails; out-of-range speed fails); migration applies with `supabase db push`.

**T2 Expert agent.** Copy the voice/agent.py skeleton; add `anthropic.LLM` with prompt caching; on job start read `topic_id` from dispatch metadata, load the topic from Supabase, build instructions = persona + fixed rules (2–4 spoken sentences, no lists, admit uncertainty, no invented numbers, stay fictional) + brief. Session cap timer → goodbye → shutdown. Latency metrics → log. **Check:** `console` mode answers in persona on the sample topic. **HUMAN 1 (gate):** two 10-min talks via the Agents Playground; median < 1 s, else a faster LLM.

**T3 Morning job.** `python -m pipeline.run_daily [--user] [--date]`: for each profile → Tavily search per interest (+ trafilatura text) → one LLM call picks 5 distinct topics → per topic: brief with `[n]` source tags, persona + config (structured output, validated, one retry), study dialogue (sample Q&A to study + 8–10 suggested questions) → upsert into `topics`. Per-user failures are logged and skipped. **Check:** `pytest tests/test_pipeline.py` (mocked HTTP + LLM); one real run for the test user gives 5 valid topics.

**E1 Audio briefing (added 2026-10-27, from the assignment).** The assignment (personal podcast generator) needs the product itself to create audio. When the user picks one of the day's topics, generate a narrated briefing for **that topic only** (cost control): a script written for listening (~2–3 min, no bullets or [n], sources named aloud, ends inviting the interview with the expert), one fixed narrator voice per language, mp3 cached in Storage (`briefings/<user_id>/<topic_id>.mp3`) so replays are free. Runs in the web server if Vercel's time limit allows, else on the laptop. The live interview is the enhancement on top. **Check:** tests with mocked LLM/TTS; one real briefing for the test user.

**D1 Internal dashboard (added 2026-10-27).** `/admin` page answering one question: are users engaging, and where do they drop off? Active users, daily habit, step-by-step funnel, trend, needs-attention list, per-topic engagement. Cost is deliberately left out for now (see `docs/design-research.md`). All data mocked (user decision 2026-10-27); real metrics need an `events` table, kept as a next step.

**T4 Vercel functions + worker (replaces the Python web server, 2026-10-27).** Docker image + compose (`agent`, `worker`); `worker/` processes `briefings` requests (migration `002_briefings.sql`) and runs the morning job daily; `web/api/signup.ts` (invite code, `MAX_USERS`, creates the user with the secret key) and `web/api/token.ts` (verifies the Supabase JWT, topic ownership, daily session cap, creates the session row, returns a LiveKit token that dispatches the agent with `{topic_id, session_id, record}`).

*(Original T4, kept for reference:)* **T4 Web server.** FastAPI `POST /token {topic_id}`: verify the Supabase JWT, topic must belong to the user, daily session cap → 429, create room, dispatch agent with `{topic_id, session_id, record}`, return `{url, token}`. Serves the built page. **Check:** `pytest tests/test_web_server.py` (bad JWT 401, someone else's topic 404, cap 429, token grants).

**T5 Web page.** Vite + TS + `livekit-client` + `supabase-js`, no framework. Screens: sign-in (magic link + invite code), onboarding (interests prompt, language, depth, tone), **Today** (5 topic cards), topic page (summary, study dialogue, sources, "Start interview"), live session (transcript, speaking indicator, mute, end, countdown), Settings (same profile fields). **Check:** `npm run build`; Playwright against mocked Supabase + `/token`. **HUMAN 2:** onboard as a new user, wait for/trigger the morning job, do a 20-min interview.

**T6 Sessions + recording.** Worker writes transcript to `sessions`; if the user ticked "record", it saves both sides as OGG (PyAV, already a livekit-agents dependency; check this in T0) and uploads them to Storage. The session page lists past interviews with transcript and download links. **Check:** a 2-min recorded session → row with transcript + two files in Storage.

**T7 Deploy (Vercel + laptop agent).** `vercel.json` for the built page + `/token` as a Python function; env vars in Vercel. Agent stays on the laptop (`python -m agent.expert dev`). Morning job by hand or a GitHub Actions cron. **HUMAN 4:** create the GitHub repo, approve the push, import it in Vercel, set Supabase redirect URL. **Check:** a second person signs up with the invite code, onboards, gets 5 topics, and does an interview while the laptop agent runs.

*(Original T7 was Render: web + worker + cron from `render.yaml`. Replaced on 2026-10-27 at the user's request.)*

**Memory risk (T2/T7):** Render Starter has 512 MB. Start like voice/agent.py with VAD + endpointing only (no turn-detector model); add the turn detector only if H1 says turn-taking feels bad. Measure worker memory in T7; if it exceeds Starter, move to Standard (2 GB, about $25/mo) and record it in PROGRESS.md.

**T8 Submission + runbook.** `solution.md` (overview, architecture, decisions and trade-offs) and `sample.mp3` (best briefing or recorded interview) in the repo, plus README: try it, run locally, run your own copy, troubleshooting. **HUMAN 3:** record and publish episode 1.

## Reuse
- [voice/agent.py](voice/agent.py): AgentServer / rtc_session / AgentSession with Inference STT/TTS, Silero, endpointing, `shutdown(drain=True)` after the goodbye.
- [config/config.yaml](config/config.yaml) `voice:` endpointing defaults; [src/config.py](src/config.py) settings loading; [tests/test_pipeline.py](tests/test_pipeline.py) injected-fake style.

## Verification
1. `pytest` green; `npm run build` + Playwright green.
2. New user: sign up → onboarding → `run_daily --user` → 5 topics on Today.
3. Pick a topic → live interview → median latency < 1 s → transcript (and recording if ticked) saved.
4. Change tone/depth in Settings → next run's personas reflect it.
5. Hosted on Render: works for a second person; cap and invite code enforced.
