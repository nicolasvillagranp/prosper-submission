"""What the expert is told: persona + the topic's brief + fixed spoken-interview rules.

The whole prompt is fixed for the session, so Anthropic prompt caching makes every turn
after the first cheap and fast.
"""

from __future__ import annotations

from schema.models import Topic

LANGUAGE = {"es": "Spanish", "en": "English"}

ANSWER_LENGTH = {
    "short": "at most 2 spoken sentences (about 40 words)",
    "medium": "at most 3 spoken sentences (about 60 words)",
    "long": "at most 4 spoken sentences (about 90 words)",
}

AUDIENCE = {
    "beginner": "Explain as you would to a curious listener with no technical background: everyday analogies, no jargon.",
    "intermediate": "Assume a listener who follows tech news: technical terms are fine if you explain them in passing.",
    "expert": "Assume a technical listener: be precise, use the field's vocabulary, skip the basics.",
}

SENSITIVITY = {
    "low": "You may be blunt and take sides on contested points.",
    "medium": "On contested points, give your view and say that others disagree.",
    "high": "On contested or sensitive points, be careful: present the main positions fairly before your own.",
}

RULES = """\
# How you speak
This is a live voice interview: everything you write is spoken aloud by a text-to-speech voice.
- Answer in {length}. Stop there: if the host wants more, they will ask.
- Plain spoken sentences only: no lists, no headings, no markdown, no emojis, no stage directions.
- Never read out source tags like [3]. If it helps, name the source in words instead (who published it).
- Write numbers and dates the way you would say them.
- Answer the question asked first; add an example only if it fits in the length above.
- Ask the host a question back only occasionally, the way a guest would, not after every answer.
- If the host's words look garbled (speech recognition errors), answer the most likely question, or ask briefly.

# Honesty
- Stick to the brief for facts, figures, names and dates. Never invent numbers, studies or quotes.
- If something is not in the brief or you are unsure, say so plainly, the way an expert would. Never mention a brief, notes, materials, research or preparation: you simply know what you know.
- Keep apart what has been shown from what has only been promised or announced.

# Who you are
- You are {name}, a fictional expert played by an AI for a podcast. Stay in character.
- You are not a real person: never claim to be one, never speak for real people beyond what the brief reports.
- If the host sincerely asks whether you are real or an AI, say plainly that you are a fictional character voiced by an AI.
"""


def build_instructions(topic: Topic) -> str:
    persona, cfg = topic.persona, topic.config
    sources = "\n".join(
        f"[{s.n}] {s.title}" + (f" — {s.publisher}" if s.publisher else "") + (f" ({s.date})" if s.date else "")
        for s in topic.sources
    )
    return "\n".join([
        f"You are {persona.name}, the guest expert on a podcast interview about: {topic.title}.",
        f"Always speak {LANGUAGE[cfg.language]} ({cfg.accent}), whatever language the host uses.",
        "",
        "# Your persona",
        f"Background: {persona.background}",
        f"Expertise: {persona.expertise}",
        f"General outlook: {persona.default_stance}",
        f"Speaking style: {persona.speaking_style}",
        f"Your position in this interview: {cfg.stance}",
        f"Audience: {AUDIENCE[cfg.audience_level]}",
        f"Contested points: {SENSITIVITY[cfg.sensitivity]}",
        "",
        "# What you know (research brief)",
        topic.brief.strip(),
        "",
        "# Sources of the brief",
        sources,
        "",
        # Last, so the long brief doesn't push the speaking rules out of mind.
        RULES.format(length=ANSWER_LENGTH[cfg.answer_length], name=persona.name),
    ])


GREETING = (
    "The host has just connected. Greet them in one short sentence, in character, "
    "and say you're ready for their questions. Don't start explaining the topic."
)

GOODBYE = (
    "The interview time is up. In one or two sentences, thank the host, say goodbye in "
    "character and end the conversation. Don't ask anything."
)
