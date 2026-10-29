"""The audio briefing: a ~3-minute narrated episode about the topic the user picked.

Made on demand, only for the topic the user opens (the morning job stays text-only to keep
costs down), then cached in Storage so replays are free:

    recordings/<user_id>/briefings/<topic_id>.mp3   the audio
    recordings/<user_id>/briefings/<topic_id>.txt   the script (shown as the transcript)

    python -m pipeline.briefing <topic_id> [--out sample.mp3]

Claude writes a script for the ear (no bullets, no [n], sources named aloud) that ends by
inviting the listener to interview the topic's expert; Cartesia reads it with the narrator
voice from config/config.yaml as mp3. Only common/ and schema/ imports: the web server runs this.
"""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field

from common.config import CONFIG, require
from common.llm import LANGUAGE, ask
from schema.models import Topic

logger = logging.getLogger("briefing")

BUCKET = "recordings"
NARRATOR = CONFIG["briefing"]["narrator"]
WORDS = CONFIG["briefing"]["words"]
CARTESIA_URL = "https://api.cartesia.ai/tts/bytes"
CARTESIA_VERSION = "2025-04-16"  # same as livekit-plugins-cartesia 1.8.8
CHUNK_CHARS = 1200  # one TTS request per chunk of paragraphs; mp3 chunks concatenate cleanly


@dataclass
class Briefing:
    audio_path: str
    script: str
    created: bool  # False when it came from the cache


class BriefingScript(BaseModel):
    script: str = Field(description="the narration, plain paragraphs separated by blank lines")


SCRIPT_SYSTEM = """\
You are the host of a daily personal news podcast. Write the narration for one short
episode about one topic, to be read aloud by a text-to-speech voice.
- About {words} words (around three minutes). Plain paragraphs separated by blank lines.
- Written for the ear: short sentences, no lists, no headings, no markdown, no emojis,
  no source tags like [3]. Numbers and dates written the way you would say them.
- Open with a hook in one or two sentences, then tell the story: what happened, why it
  matters, and where the sources disagree or what remains unproven.
- Only facts from the brief. Name sources aloud when it helps ("según Reuters", "according
  to the company") and keep apart what was shown from what was claimed.
- Warm and lively, like a host talking to one listener, not a newsreader.
- End by inviting the listener to interview today's expert about it, by name and with one
  provocative question they could ask. The expert is a fictional character played by an AI;
  you may say so lightly.
- Write in the topic's language."""


def write_script(llm, topic: Topic) -> str:
    persona, cfg = topic.persona, topic.config
    sources = "\n".join(f"[{s.n}] {s.publisher or ''}: {s.title}" for s in topic.sources)
    return ask(llm, BriefingScript, SCRIPT_SYSTEM.format(words=WORDS),
               f"Language: {LANGUAGE[cfg.language]}\nListener's level: {cfg.audience_level}\n\n"
               f"Topic: {topic.title}\nSummary: {topic.summary}\n\n"
               f"Today's expert: {persona.name}, {persona.expertise}. Their view: {cfg.stance}\n\n"
               f"Brief:\n{topic.brief}\n\nSources:\n{sources}",
               effort="medium", max_tokens=8000).script.strip()


def spoken(text: str, pronunciations: dict[str, str]) -> str:
    """The script as the voice should read it: Genie -> Yíni. One pass, longest names first,
    so a replacement is never replaced again (AI Act -> Ei Ai Akt must not touch its "Ai")."""
    if not pronunciations:
        return text
    by_lower = {k.lower(): v for k, v in pronunciations.items()}
    names = "|".join(re.escape(k) for k in sorted(pronunciations, key=len, reverse=True))
    return re.sub(rf"(?<!\w)(?:{names})(?!\w)", lambda m: by_lower[m.group(0).lower()], text, flags=re.I)


def chunks(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    """Paragraphs grouped into pieces of at most `limit` characters (a long paragraph stays whole)."""
    out: list[str] = []
    for para in (p.strip() for p in text.split("\n\n")):
        if not para:
            continue
        if out and len(out[-1]) + len(para) + 2 <= limit:
            out[-1] += "\n\n" + para
        else:
            out.append(para)
    return out


def synthesize(http: httpx.Client, text: str, language: str, voice: str | None = None) -> bytes:
    """mp3 of `text`, in the narrator's voice unless another is given."""
    audio = b""
    for piece in chunks(text):
        r = http.post(CARTESIA_URL, headers={"X-API-Key": require("CARTESIA_API_KEY"),
                                             "Cartesia-Version": CARTESIA_VERSION},
                      json={"model_id": "sonic-3", "transcript": piece, "language": language,
                            "voice": {"mode": "id", "id": voice or NARRATOR[language]},
                            "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000}},
                      timeout=120)
        r.raise_for_status()
        audio += r.content
    return audio


def get_briefing(db, llm, http, topic_id: str, user_id: str) -> Briefing:
    """The user's briefing for `topic_id`, from the cache or made now. LookupError if the topic isn't theirs."""
    rows = db.table("topics").select("*").eq("id", topic_id).eq("user_id", user_id).limit(1).execute().data
    if not rows:
        raise LookupError(f"topic {topic_id} not found")
    folder = f"{user_id}/briefings"
    store = db.storage.from_(BUCKET)
    if any(f["name"] == f"{topic_id}.mp3" for f in store.list(folder, {"search": topic_id})):
        script = store.download(f"{folder}/{topic_id}.txt").decode("utf-8")
        return Briefing(f"{folder}/{topic_id}.mp3", script, created=False)

    topic = Topic.model_validate(rows[0])
    script = write_script(llm, topic)
    audio = synthesize(http, spoken(script, topic.config.pronunciations), topic.config.language)
    # Text first: a cached mp3 always has its script next to it.
    store.upload(f"{folder}/{topic_id}.txt", script.encode("utf-8"),
                 {"content-type": "text/plain; charset=utf-8", "upsert": "true"})
    store.upload(f"{folder}/{topic_id}.mp3", audio, {"content-type": "audio/mpeg", "upsert": "true"})
    logger.info("briefing for topic %s: %d words, %d KB", topic_id, len(script.split()), len(audio) // 1024)
    return Briefing(f"{folder}/{topic_id}.mp3", script, created=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Make (or fetch) the audio briefing for one topic.")
    parser.add_argument("topic_id")
    parser.add_argument("--out", help="also save the mp3 here, e.g. sample.mp3")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "httpx2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    import anthropic

    from common.db import client

    db = client()
    owner = db.table("topics").select("user_id").eq("id", args.topic_id).execute().data
    if not owner:
        raise SystemExit(f"no topic {args.topic_id}")
    with httpx.Client() as http:
        briefing = get_briefing(db, anthropic.Anthropic(), http, args.topic_id, owner[0]["user_id"])
    print(briefing.script)
    if args.out:
        with open(args.out, "wb") as f:
            f.write(db.storage.from_(BUCKET).download(briefing.audio_path))
        print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
