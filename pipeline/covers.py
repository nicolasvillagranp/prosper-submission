"""Topic covers: one paper-collage illustration per topic, for the magazine-style page.

Claude turns each topic into a visual metaphor (objects only: no text, people or logos); OpenAI's
gpt-image-1-mini draws it at low quality (about $0.003 an image); the jpeg goes to Storage:

    recordings/<user_id>/covers/<topic_id>.jpg     (the page asks for a signed URL)

A cover that fails is skipped: the page shows a plain paper block instead.

    python -m pipeline.covers --user <uuid> [--date 2026-10-28]    # covers for topics without one
"""

from __future__ import annotations

import argparse
import base64
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx
from pydantic import BaseModel, Field

from common.config import require
from common.llm import ask

logger = logging.getLogger("covers")

BUCKET = "recordings"
IMAGE_URL = "https://api.openai.com/v1/images/generations"
STYLE = ("Warm paper-cut collage illustration, layered torn paper textures, palette of terracotta, ochre, "
         "olive green and off-white, handmade tactile feel, soft shadows between layers.")
RULES = "Magazine cover art. No text, no letters, no logos, no real people, no flags."


class Subjects(BaseModel):
    subjects: list[str] = Field(description="one visual metaphor per topic, in the same order")


SUBJECT_SYSTEM = """\
You art-direct a news magazine. For each topic, describe in one English sentence a simple, striking
visual metaphor for its central question, using objects only: no people, no text, no logos, no
flags, no real brands. Example: "a chatbot speech bubble inside an old wooden confessional booth"."""


def cover_path(user_id: str, topic_id: str) -> str:
    return f"{user_id}/covers/{topic_id}.jpg"


def subjects_for(llm, topics: list[dict]) -> list[str]:
    listing = "\n".join(f"{i + 1}. {t['title']}: {t['summary']}" for i, t in enumerate(topics))
    out = ask(llm, Subjects, SUBJECT_SYSTEM, f"Topics:\n{listing}", effort="low", max_tokens=2000).subjects
    # One per topic: a topic Claude left out is drawn from its own title.
    return out[: len(topics)] + [t["title"] for t in topics[len(out):]]


def draw(http: httpx.Client, subject: str) -> bytes:
    r = http.post(IMAGE_URL, timeout=120, headers={"Authorization": f"Bearer {require('OPENAI_API_KEY')}"},
                  json={"model": "gpt-image-1-mini", "prompt": f"{subject}. {STYLE} {RULES}", "size": "1536x1024",
                        "quality": "low", "output_format": "jpeg", "output_compression": 80})
    r.raise_for_status()
    return base64.b64decode(r.json()["data"][0]["b64_json"])


def make_covers(db, llm, http, topics: list[dict]) -> int:
    """Covers for `topics` (rows with id, user_id, title, summary). Returns how many were made."""
    if not topics:
        return 0
    subjects = subjects_for(llm, topics)
    store = db.storage.from_(BUCKET)

    def one(pair) -> bool:
        topic, subject = pair
        try:
            store.upload(cover_path(topic["user_id"], topic["id"]), draw(http, subject),
                         {"content-type": "image/jpeg", "upsert": "true"})
            return True
        except Exception:
            logger.exception("cover failed for topic %s", topic["id"])
            return False

    with ThreadPoolExecutor(max_workers=5) as pool:
        made = sum(pool.map(one, zip(topics, subjects)))
    logger.info("%d/%d covers made", made, len(topics))
    return made


def main() -> None:
    parser = argparse.ArgumentParser(description="Covers for a user's topics that don't have one yet.")
    parser.add_argument("--user", required=True)
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "httpx2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    import anthropic

    from common.db import client

    db = client()
    topics = (db.table("topics").select("id,user_id,title,summary").eq("user_id", args.user)
              .eq("date", args.date.isoformat()).order("rank").execute().data)
    existing = {f["name"] for f in db.storage.from_(BUCKET).list(f"{args.user}/covers")}
    missing = [t for t in topics if f"{t['id']}.jpg" not in existing]
    with httpx.Client() as http:
        make_covers(db, anthropic.Anthropic(), http, missing)


if __name__ == "__main__":
    main()
