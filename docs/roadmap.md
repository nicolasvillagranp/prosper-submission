# Roadmap to the demo (from 2026-10-27)

## How it runs (Orbio-style, decided 2026-10-27)

```
Vercel (root: web/)                       Laptop, Docker Compose (always on)
 ├─ static page (Vite)                     ├─ agent  → live expert interviews
 ├─ /api/signup  (invite code)             └─ worker → audio briefings on request
 └─ /api/token   (LiveKit token)                       + morning job at 06:00
        │                                          │
        └──────────── Supabase (auth, data, audio) ─┘
```

- No Python on Vercel: the page talks to Supabase directly under RLS; only the invite-code
  check and the LiveKit token need secret keys, so they are two small TypeScript functions.
- The slow work (audio briefing ~1 min, morning job minutes per user, 20-minute interviews)
  runs in Docker on the laptop: `docker compose up -d --build`, `restart: unless-stopped`.
  Moving it to a small server later is the same file and the same command.
- Isolated from Orbio where it matters: own Supabase, own Docker project (`name: podcast`), own
  repo. LiveKit and the API keys are shared on purpose; the agents use different names.

## The user's part (once, early)

1. GitHub: create an empty **private** repo, no README. Nothing is pushed until the user says so.
2. Vercel: sign up with GitHub (free Hobby plan). Nothing else until the first push.
3. Supabase → Authentication → URL Configuration: Site URL `http://localhost:5173`, and add
   `http://localhost:5173/**` to Redirect URLs. The Vercel URL is added at deploy.
4. Supabase SQL Editor: run `supabase/migrations/002_briefings.sql`.
5. Docker Desktop: Settings → General → "Start Docker Desktop when you sign in".
6. At deploy: paste the env vars into Vercel (list given then) and add the Vercel URL to Supabase.

## Build order and what the user tests

| Step | What gets built | How the user tests it |
|---|---|---|
| T4 | Docker (agent + worker), briefing queue, Vercel functions (sign-up with invite code, interview token with daily limit) | **Test 0:** Docker Desktop running, `docker compose ps` shows both services up |
| T5 | Web page: sign-in, onboarding, Today, Topic (briefing player, voice picker, start interview), Live interview, Settings | **Test 1 (laptop):** sign in with a magic link, onboard, open today's topics, play a briefing, change Settings, then an interview with the laptop agent running |
| T6 | Transcripts + optional recording, My episodes | **Test 2:** record a 3–5 min interview, find it in My episodes, download the mp3 |
| D1 | Engagement dashboard, mocked data | **Test 3:** open /admin |
| T7 | Deploy to Vercel | **Test 4:** the same flow from the Vercel URL, on the phone or by a second person, with the laptop agent running |
| T8 | `solution.md`, `sample.mp3`, README | **Test 5:** read `solution.md`, pick the best episode for `sample.mp3`, approve the push |
