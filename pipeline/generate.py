"""The three LLM steps of the morning job: search queries, picking 5 topics, writing each topic.

Every step uses structured output (a pydantic model). The writer fills a TopicDraft; the code
adds what the LLM must not decide (sources and their URLs, language, depth, voice settings)
and validates the result as a Topic, retrying once with the validation error.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from common.config import CONFIG, ROOT
from common.llm import LANGUAGE, LLMError, ask
from pipeline.research import Article
from schema.models import VOICES, Persona, Profile, Source, Topic

logger = logging.getLogger("pipeline")

TONE = {
    "explainer": "a friendly, patient explainer who builds understanding step by step",
    "balanced": "a candid expert who explains clearly and gives an opinion when asked",
    "sparring": "a sparring partner with strong, argued opinions who pushes back on the host",
}
NARRATORS = set(CONFIG["briefing"]["narrator"].values())  # the briefing's voice is the host, not a guest
SAMPLE = json.loads((ROOT / "samples" / "world-models.json").read_text(encoding="utf-8"))


# 1. Search queries -----------------------------------------------------------------------

class SearchPlan(BaseModel):
    queries: list[str] = Field(description="3 to 6 news search queries")


PLAN_SYSTEM = """\
You turn a listener's interests into news search queries for a daily podcast.
Write 3 to 6 short queries (2 to 6 words each) that will find this week's news on those
interests. Cover the different interests; prefer concrete subjects over vague ones.
Write each query in the language the news is most likely published in."""


def plan_queries(client, profile: Profile) -> list[str]:
    plan = ask(client, SearchPlan, PLAN_SYSTEM,
               f"Interests:\n{profile.interests}\n\nListener's language: {LANGUAGE[profile.language]}",
               effort="low", max_tokens=2000)
    return [q.strip() for q in plan.queries if q.strip()][:6]


# 2. Pick the day's topics ----------------------------------------------------------------

class Pick(BaseModel):
    title: str = Field(description="working title of the interview")
    angle: str = Field(description="the question or tension the interview explores, one sentence")
    article_ids: list[str] = Field(description="2 to 5 article ids, e.g. ['a3', 'a7']")
    expert_name: str = Field(description="invented full name of the fictional expert")
    expert_gender: Literal["feminine", "masculine"]


class Picks(BaseModel):
    topics: list[Pick]


PICK_SYSTEM = """\
You are the editor of a daily podcast where the host interviews an expert about one topic.
From today's articles, choose the requested number of interview topics for this listener.
- Each topic must be distinct: a different story or question, not two angles on one story.
- Match the listener's interests. Prefer stories with substance to discuss (a tension,
  a disagreement, a consequence) over announcements with nothing to argue about.
- Each topic needs 2 to 5 articles that actually cover it, so the brief can cross-check them.
- Avoid topics the listener already got in recent days (listed below, if any).
- Invent one fictional expert per topic: a full name that sounds natural in the listener's
  language, never a real or famous person, nor anyone in the articles. All names clearly
  different from each other (no shared first or last names), and mix women and men."""


def pick_topics(client, profile: Profile, articles: list[Article], count: int,
                recent_titles: list[str]) -> list[Pick]:
    listing = "\n".join(f"{a.id} | {a.date or 'no date'} | {a.publisher} | {a.title} | {a.snippet}"
                        for a in articles)
    recent = "\n".join(f"- {t}" for t in recent_titles) or "(none)"
    picks = ask(client, Picks, PICK_SYSTEM,
                f"Listener's interests:\n{profile.interests}\n\nDepth: {profile.depth}\n\n"
                f"Recent topics to avoid:\n{recent}\n\nArticles (id | date | publisher | title | snippet):\n"
                f"{listing}\n\nChoose {count} topics.",
                effort="medium", max_tokens=8000)
    known = {a.id for a in articles}
    valid = []
    for pick in picks.topics:
        pick.article_ids = [i for i in dict.fromkeys(pick.article_ids) if i in known][:5]
        if pick.article_ids:
            valid.append(pick)
    return valid[:count]


# 3. Write one topic ----------------------------------------------------------------------

class Pronunciation(BaseModel):
    written: str = Field(description="a name as written, e.g. 'DeepMind'")
    spoken: str = Field(description="how a native speaker of the topic language says it, spelled for TTS")


class VoiceScore(BaseModel):
    voice_id: str = Field(description="id of a voice from the allowed list")
    score: int = Field(description="0-100: how well this voice fits the persona")
    why: str = Field(description="one short phrase, e.g. 'calm and precise, like a researcher'")


class DraftConfig(BaseModel):
    stance: str = Field(description="the expert's position in this interview, one or two sentences")
    answer_length: Literal["short", "medium", "long"]
    sensitivity: Literal["low", "medium", "high"]
    voices: list[VoiceScore] = Field(description="every allowed voice, scored")
    pronunciations: list[Pronunciation] = Field(description="foreign names and acronyms the voice may mispronounce, at most 10")


class TopicDraft(BaseModel):
    title: str
    summary: str
    persona: Persona
    config: DraftConfig
    brief: str
    study_dialogue: str


WRITE_SYSTEM = f"""\
You prepare one episode of a podcast where the host interviews a fictional AI expert, live,
by voice. From the articles given, write everything the episode needs. Everything you write
is in the listener's language.

## title, summary
A catchy title (under 100 characters) and a 1-2 sentence summary that says what happened and
what the open question is.

## persona: the fictional expert
- Use exactly the expert name you are given; it is an invented person.
- background (1-3 sentences, with years of practical experience that explain their view),
  expertise, default_stance, speaking_style. Make them a specific person with a point of view,
  not a neutral narrator.

## config
- stance: their position on this topic, consistent with the persona and defensible from the articles.
- answer_length: usually "medium"; "short" for a fast-paced news topic, "long" for a topic that needs explaining.
- sensitivity: "high" for health, politics, conflicts or tragedies; "low" for light topics; otherwise "medium".
- voices: score every allowed voice 0-100 for how well it fits this persona (age, manner,
  authority, warmth), with a short reason. The best one becomes the expert's voice; the host can
  pick among the top three.
- pronunciations: foreign names, brands and acronyms in the brief, spelled the way a native
  speaker of the topic language would say them (e.g. for Spanish: DeepMind -> Dip Maind, Waymo -> Güéimo).

## brief: what the expert knows (markdown, 400-900 words)
- Sections with short bullet points of facts. Every fact ends with its source tag [n], the
  number of the article it comes from. Only facts from the articles; no outside knowledge.
- Keep apart what was shown, what was claimed (and by whom), and what is speculation.
- Include figures, dates and names exactly as the articles give them.
- End with "risks or criticisms" and "open questions" sections.

## study_dialogue: what the host reads before recording (markdown)
- An opening hook, 2-3 angles, tensions between sources (with [n]), a short sample exchange
  between the host and the expert (by name), and 8-10 suggested questions.

## Example of the expected quality and format (Spanish listener, different topic)
title: {SAMPLE["title"]}
persona: {json.dumps(SAMPLE["persona"], ensure_ascii=False)}
brief:
{SAMPLE["brief"]}

study_dialogue:
{SAMPLE["study_dialogue"]}
"""


def write_topic(client, profile: Profile, pick: Pick, articles: list[Article]) -> Topic:
    """The full topic for one pick, validated; retried once with the validation error."""
    chosen = [a for i in pick.article_ids for a in articles if a.id == i]
    sources = [Source(n=n, title=a.title, url=a.url, date=a.date, publisher=a.publisher)
               for n, a in enumerate(chosen, start=1)]
    voices = "\n".join(f"- {v['id']}: {v['name']}, accent {v['accent']}"
                       for v in VOICES[profile.language]
                       if v["gender"] == pick.expert_gender and v["id"] not in NARRATORS)
    texts = "\n\n".join(f"### [{n}] {a.title} ({a.publisher}, {a.date or 'no date'})\n{a.text}"
                        for n, a in enumerate(chosen, start=1))
    request = (
        f"Listener's language: {LANGUAGE[profile.language]}\n"
        f"Listener's depth: {profile.depth}\n"
        f"Expert's tone: {TONE[profile.tone]}\n\n"
        f"Topic: {pick.title}\nAngle: {pick.angle}\nExpert's name: {pick.expert_name}\n\n"
        f"Allowed voices:\n{voices}\n\nArticles:\n\n{texts}"
    )
    error = None
    for attempt in (1, 2):
        user = request if not error else f"{request}\n\nYour previous answer was rejected: {error}\nFix that."
        try:
            draft = ask(client, TopicDraft, WRITE_SYSTEM, user, effort="high")
            draft.persona.name = pick.expert_name
            return assemble(draft, profile, sources, chosen)
        except (ValidationError, ValueError, LLMError) as e:
            error = str(e)[:1500]
            logger.warning("topic '%s' attempt %d rejected: %s", pick.title, attempt, error)
    raise LLMError(f"topic '{pick.title}' failed twice: {error}")


def assemble(draft: TopicDraft, profile: Profile, sources: list[Source], articles: list[Article]) -> Topic:
    """Topic = the LLM's draft + what the code decides. Raises if it isn't valid."""
    name = draft.persona.name.lower()
    if any(name in a.text.lower() or name in a.title.lower() for a in articles):
        raise ValueError(f"persona name '{draft.persona.name}' appears in the articles: invent another")
    cfg = draft.config
    allowed = {v["id"]: v for v in VOICES[profile.language]}
    ranked = sorted({s.voice_id: s for s in cfg.voices if s.voice_id in allowed}.values(),
                    key=lambda s: s.score, reverse=True)[:3]
    if not ranked:
        raise ValueError("no allowed voice was scored: score the voices in the allowed list")
    best = ranked[0].voice_id
    return Topic.model_validate({
        "title": draft.title,
        "summary": draft.summary,
        "persona": draft.persona.model_dump(),
        "config": {
            "language": profile.language,
            "accent": allowed[best]["accent"],
            "audience_level": profile.depth,
            "stance": cfg.stance,
            "answer_length": cfg.answer_length,
            "sensitivity": cfg.sensitivity,
            "pronunciations": {p.written: p.spoken for p in cfg.pronunciations[:10]},
            # Plain voice settings: the "Curious" emotion sounded forced at checkpoint 1.
            "tts": {"voice_id": best, "speed": 1.0, "emotion": []},
            "voice_options": [{"voice_id": s.voice_id, "score": max(0, min(100, s.score)), "why": s.why[:200]}
                              for s in ranked],
        },
        "brief": draft.brief,
        "study_dialogue": draft.study_dialogue,
        "sources": [s.model_dump(mode="json") for s in sources],
    })
