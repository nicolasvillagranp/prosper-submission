# Design research

Notes on alternatives and product decisions, kept as we go. They feed `solution.md`.

## Existing podcast generators: why we built something different

Open-source projects already turn articles or text into podcast audio. The best known is
probably **Podcastfy**, a NotebookLM-style generator (content in, an AI-hosted conversation
out). We haven't evaluated it in depth.

We chose not to build on one, because we wanted a different product, not a different engine:

- **Those tools generate a finished episode to listen to.** Ours generates a short narrated
  briefing, and then the user records the real episode by interviewing a fictional expert
  live, by voice. The listener becomes the host.
- **They cover the script-and-voice step, not the news step.** Our news gathering (Tavily
  search + trafilatura for article text, deduplication, topic picking, cited briefs) is
  already built, tested and under a few hundred lines, and does exactly what we need.
- **The assignment values understanding the trade-offs.** A small pipeline we can explain
  line by line serves that better than a borrowed dependency.

## Language: the UI is English, the content can be any language

- The app's interface (buttons, screens, onboarding) is in English.
- The content follows the user's profile: the news searches, the brief, the audio briefing,
  the expert's voice and the live interview are all in the language the user picks.
- Today that is Spanish or English (`config/voices.yaml` lists stock voices for both). Adding
  a language means adding its voices to that list and its name to the prompts; nothing else
  in the pipeline is language-specific.
- Possible enhancement: "follow the news" mode, where each topic is in the language its
  sources are published in.

## Voice provider

- Cartesia for everything for now: it was already integrated and wins on latency for the
  live interview.
- ElevenLabs is usually more natural for long narration (the briefing). A provider setting
  per use (briefing vs interview) is a contained change, kept as an enhancement.

## Audio only for the topic you pick

- The 06:00 job prepares 5 topics as text only. Audio is generated when the user opens a
  topic, then cached, so replays are free and nobody pays for audio nobody hears.
- Trade-off: the first listen waits about a minute while the script and audio are made.

## Internal dashboard: engagement first, cost later

- **The question it answers:** are users engaging, and where do they drop off? So we can
  spot a problem and fix it fast.
- **Cost is out of scope for now (decision 2026-10-27).** We assume the unit economics have
  been worked out beforehand; with a capped number of invited users, spend is bounded.
  Cost tracking becomes a dashboard section when usage grows (by part: topics, audio
  briefing, live interview minutes; and cost per active user).
- **What it shows:** weekly active users, daily habit (% of users who open a topic each
  day), a step-by-step funnel (open topic, listen to the briefing, start an interview, record
  an episode), each step measured against the previous one so the weakest step stands out,
  a daily trend, a "needs attention" list, and per-topic engagement.
- **All dashboard data is mocked** (decision 2026-10-27; the assignment allows it), clearly labelled. Several metrics (topic opens, % of briefing played, grouping by theme) aren't recorded by the app today; making them real needs an `events` table written by the page (topic opened, briefing 50%/100%). Kept as a next step.

## Look and feel: "paper magazine" (2026-10-28)

- Three directions were drawn on the sketch with real covers (dark "night edition", "paper
  magazine", "soft studio"); the user chose **paper magazine**: warm paper ground, ink text, one
  terracotta accent, Fraunces serif headlines, a newspaper masthead ("The Daily Interview"), the
  day's lead story big with the expert's pull quote, the other four as a list with covers.
- The live interview keeps the same palette inverted (ink ground, paper text).

## Topic covers

- One paper-collage illustration per topic, generated right after the topics are saved: Claude
  turns each topic into a visual metaphor (objects only: no people, text, logos or flags), then
  OpenAI `gpt-image-1-mini` draws it at **low quality** (~400 output tokens, ~11 s, roughly a third
  of a cent per image), stored in Storage next to the user's other files.
- Cost decision: the medium-quality `gpt-image-2` was rejected as unsustainable per user per day;
  the mini model at low quality looked good enough for 1536x1024 covers. A failed cover never
  blocks the topics: the page shows a plain paper block instead.
