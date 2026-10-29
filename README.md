# The Daily Interview

Each user sets their interests once. Every morning they get 5 interview topics, each with a
fictional AI expert made for it, a research brief and a study dialogue. They pick one and
interview the expert live, by voice, in the browser.

| Part | Where it runs | What it does |
|---|---|---|
| `web/` | Vercel (static page + `api/signup`, `api/token`) | Sign-in, onboarding, today's topics, briefing, live interview, My episodes, dashboard; issues LiveKit tokens |
| `agent/` | Docker `agent` | The expert: LiveKit Agents, Deepgram STT, Cartesia TTS, Claude for replies; saves transcript + mp3 |
| `pipeline/` + `worker/` | Docker `worker` | 06:00: news per interest → 5 topics per user + covers; audio briefings on request |
| `supabase/` | Supabase | Auth, profiles, topics, briefings, sessions, Storage (covers, briefings, recordings) |

Overview and design decisions: [solution.md](solution.md). Status of each step: [PROGRESS.md](PROGRESS.md).

## Setup

1. Create a Supabase project, run `supabase/migrations/*.sql` in its SQL editor, and turn public sign-ups off.
2. `cp .env.example .env` and fill in the keys (LiveKit, Anthropic, Deepgram, Cartesia, Tavily, Supabase, OpenAI).
3. `docker compose up -d --build` (agent + worker), then `cd web && npm install && npm run dev`.
4. Deploying the page: a Vercel project with root directory `web` and the same env vars.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # fill in the keys
python -m pytest -q
```

### Talk to the expert

```bash
python -m agent.expert            # console: talk with the laptop mic, sample topic (Lucía Arenas)
python -m agent.expert dev        # worker: waits for jobs dispatched with {"topic_id": ...}
```

Each reply's latency (host stops talking → expert starts) is logged as `reply latency`, and
the median is logged when the session ends (`session latency`).

### Morning job

```bash
python -m pipeline.run_daily                    # every user with a profile, for today
python -m pipeline.run_daily --user <uuid>      # one user
python -m pipeline.run_daily --date 2026-10-26 --force   # redo a day that already has topics
```

Per user: Claude turns the interests into news searches → Tavily (last week, full text) →
Claude picks 5 distinct topics and invents 5 distinct experts → one call per topic writes
persona, voice, brief and study dialogue (in parallel). Sources are numbered by the code from
the picked articles; every topic is validated and retried once. Takes 2–6 minutes per user.

### Always-on services (Docker)

```bash
docker compose up -d --build    # agent (live expert) + worker (audio briefings, 06:00 topics)
docker compose ps               # both should be "running"
docker compose logs -f worker   # follow a service's log
docker compose down             # stop
```

### Web page and API (what Vercel runs)

```bash
cd web
npm install
npm run dev        # http://localhost:3000, with /api/signup and /api/token
npx vitest run     # tests for the API functions
```
