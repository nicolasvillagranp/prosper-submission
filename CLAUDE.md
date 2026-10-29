# CLAUDE.md

Context for Claude Code. Read this first, then [docs/PLAN.md](docs/PLAN.md) (the approved plan) and [PROGRESS.md](PROGRESS.md) (status per task).

## What this is

**It answers a take-home assignment:** "personal podcast generator": UI for interests + podcast customization, news from APIs/scraping on a schedule, an engaging audio, an internal usage dashboard (mocked data OK), submitted as a repo + `solution.md` (decisions and trade-offs) + `sample.mp3`. Our take (agreed 2026-10-27): the schedule prepares 5 topics; picking one generates a narrated audio briefing **for that topic only** (cost); the live interview with the expert is the enhancement.

A web app: each user sets their interests once; every morning at 06:00 a job prepares ~5 interview topics for them (fictional AI expert persona + research brief + study dialogue). The user picks one and interviews the expert live by voice in the browser. Transcript saved; audio too if they tick "record".

The live agent is deliberately simple: the LiveKit Agents pattern from the Orbio project's `backend-layer/voice/agent.py` (Deepgram STT, Cartesia TTS, Silero VAD) plus Claude with a prompt built from the topic. The real work is the loop around it.

## Decisions already made with the user (don't re-ask)

- Separate repo from the Orbio interview assignment. Remote `origin` = https://github.com/nicolasvillagranp/prosper-submission (private, empty until the first push); **the user approves every push**.
- Vercel: the user's existing account. The local page runs on port 3000 (Supabase's default Site URL), so no Supabase URL setting is needed locally; the Vercel URL is added at deploy.
- Web page only. No Android/PWA, no phone calls.
- **Fully isolated from the Orbio project** (2026-10-27): own Supabase, own Docker project (`name: podcast`), own repo; LiveKit project and Anthropic/Cartesia/Deepgram keys are deliberately shared with Orbio (user's choice); the agents can't clash because they register under different names (`expert` vs `zadarma-agent`). Orbio code was only read as a reference.
- LiveKit Cloud (same project as Orbio, different agent name) is only the room/audio transport.
- STT/TTS: Deepgram and Cartesia **plugins called directly** with their own keys (not LiveKit Inference).
- LLM: Anthropic. `claude-haiku-5-5` live, `claude-sonnet-5-5` for the morning job (`config/config.yaml`).
- Many users, capped: invite code + `MAX_USERS`. Public sign-ups are off in Supabase; the web server creates accounts after checking the code.
- Profile fields (editable any time in Settings): interests (free text), language (es/en), depth, tone. Changes apply from the next morning.
- **UI in English; content in the user's language** (news, brief, audio briefing, expert voice, interview follow the profile's language, es/en today). Design notes for `solution.md` live in `docs/design-research.md`; UI sketch: https://claude.ai/artifact/Az36ZiDjjRkPEzpQafDe7F.
- Supabase: auth (magic link), Postgres (profiles, topics, sessions), Storage (recordings). New key names: `SUPABASE_PUBLISHABLE_KEY` (browser), `SUPABASE_SECRET_KEY` (server only).
- Hosting (2026-10-27, Orbio-style, replaces Render): **Vercel** serves the static page (`web/`, Vite) plus two small TypeScript functions (`/api/signup` invite code, `/api/token` LiveKit token); the page reads/writes Supabase directly under RLS. **Docker Compose on the laptop** (`docker-compose.yml`, `restart: unless-stopped`) runs `agent` (live expert) and `worker` (audio briefings requested via the `briefings` table + the 06:00 morning job). No Python on Vercel, no Render.
- No turn-detector model at first (originally for a 512 MB worker; keeps the agent light); add it only if checkpoint 1 says turn-taking feels bad.
- Personas are fictional; voices only from `config/voices.yaml` (Cartesia stock voices).
- Sample topic for testing: `samples/world-models.json`, in Spanish ("Modelos del mundo"), expert "Lucía Arenas", voice Nuria (es-ES).

## How to work here

- Tasks T0–T8 in order (docs/PLAN.md). After each: run its check, update PROGRESS.md, commit `T<n>: <summary>`.
- Commits and pushes go as **nicolasvillagranp** (repo-local git config; pushes use `gh auth git-credential`). **No `Co-Authored-By` lines** in commit messages; `.githooks/commit-msg` strips them anyway (`git config core.hooksPath .githooks`).
- Stop at HUMAN checkpoints and tell the user exactly what to do.
- Never print or commit values from `.env`. Check keys with read-only calls only.
- Pin versions in `requirements.txt`. Ask before adding a dependency not in the plan.
- LiveKit Agents is pinned at 1.8.8: read the installed source under `.venv/Lib/site-packages/livekit/` before writing agent code.
- Tests mock all LLM and network calls. Run from the repo root: `.venv\Scripts\python -m pytest -q`.
- The user writes in English or Spanish and prefers short, plain answers and visual diagrams (HTML artifacts; Mermaid doesn't render for them).

## Where we are (2026-10-25)

- T0 done: repo, venv (`.venv`, Python 3.12), pinned deps, `.env` filled and every key tested (LiveKit, Anthropic, Deepgram, Cartesia, Supabase, Tavily).
- T1 done: `schema/models.py`, `config/voices.yaml`, sample topic, migration applied and verified (tables, RLS, private bucket, sign-ups off).
- T2 code done: `agent/expert.py` (entrypoint), `agent/prompt.py` (persona + brief + rules), `common/db.py`. Console boots and greets in persona; 18 tests passing. No `temperature` anywhere: Claude 5 models reject it. Turn detection explicitly `"vad"` (1.8.8 enables a turn detector by default).
- Checkpoint 1 passed (user: "good for a first test, we'll polish later"). Polish list in PROGRESS.md T2 row.
- T3 done: `pipeline/` (research, generate, run_daily), 32 tests. Test user nicolasvillagranprieto@gmail.com (user_id `ad1e2187-9813-4f41-bf95-5c21d738b153`) has a profile and 5 topics for 2026-10-27.
- E1 code done: `pipeline/briefing.py`, Cartesia for the narrator (user chose Cartesia over ElevenLabs on 2026-10-27). Claude helper moved to `common/llm.py`. Briefings are now made by the Docker worker on request (`briefings` table).
- T4 done: Docker (`docker compose up -d --build`) runs agent + worker; `web/` has the Vercel functions (`api/signup.ts`, `api/token.ts`, logic in `web/server/`, tests `npx vitest run`). Local page + API: `cd web && npm run dev` → http://localhost:3000. Real test passed: signed-in user → token → agent joined in 1.2 s.
- T5 code done: React app in `web/src` (screens in `src/screens`). Voice options scored by Claude (`config.voice_options`), samples in `web/public/voices` (`python -m pipeline.voice_samples`). New users get topics right after onboarding (worker). **Waiting on the user: Test 1** at http://localhost:3000.
