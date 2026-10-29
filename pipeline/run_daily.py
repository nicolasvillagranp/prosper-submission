"""The morning job: for every user, today's news on their interests -> 5 interview topics.

    python -m pipeline.run_daily                      # every user (Render cron, 06:00)
    python -m pipeline.run_daily --user <uuid>        # one user
    python -m pipeline.run_daily --date 2026-10-26 --force

A user who already has a full set for the date is skipped unless --force. A failure for one
user (or one topic) is logged and the run goes on with the rest.
"""

from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from datetime import date, timedelta

import httpx

from common.config import CONFIG, require
from pipeline.covers import make_covers
from pipeline.generate import pick_topics, plan_queries, write_topic
from pipeline.research import search_news
from schema.models import Profile, Topic

logger = logging.getLogger("pipeline")

TOPICS_PER_DAY = CONFIG["morning"]["topics_per_day"]
RESULTS_PER_QUERY = CONFIG["morning"]["results_per_interest"]


def topics_for(profile: Profile, llm, tavily, recent_titles: list[str]) -> list[Topic]:
    queries = plan_queries(llm, profile)
    logger.info("queries: %s", queries)
    articles = search_news(tavily, queries, RESULTS_PER_QUERY)
    logger.info("%d articles with text", len(articles))
    if not articles:
        raise RuntimeError("no articles found")
    picks = pick_topics(llm, profile, articles, TOPICS_PER_DAY, recent_titles)
    logger.info("picked: %s", [p.title for p in picks])

    def write(pick):
        try:
            return write_topic(llm, profile, pick, articles)
        except Exception:
            logger.exception("topic '%s' skipped", pick.title)
            return None

    with ThreadPoolExecutor(max_workers=TOPICS_PER_DAY) as pool:
        return [t for t in pool.map(write, picks) if t]


def recent_titles(db, user_id: str, day: date, days: int = 7) -> list[str]:
    rows = (db.table("topics").select("title").eq("user_id", user_id)
            .gte("date", (day - timedelta(days=days)).isoformat()).lt("date", day.isoformat())
            .execute().data)
    return [r["title"] for r in rows]


def save(db, user_id: str, day: date, topics: list[Topic]) -> list[dict]:
    """The day's topics, ranks 1..n. A re-run replaces the day's topics outright (new ids), so an
    audio briefing made for an old topic can never be served for a new one (its row cascades)."""
    rows = [{"user_id": user_id, "date": day.isoformat(), "rank": rank, **t.model_dump(mode="json")}
            for rank, t in enumerate(topics, start=1)]
    db.table("topics").delete().eq("user_id", user_id).eq("date", day.isoformat()).execute()
    return db.table("topics").insert(rows).execute().data


def run(db, llm, tavily, day: date, user_id: str | None = None, force: bool = False,
        covers: Callable[[list[dict]], object] | None = None) -> dict[str, int]:
    """Topics for every profile (or one). Returns {user_id: topics saved}.
    `covers(rows)` illustrates the saved topics; its failures never undo the topics."""
    query = db.table("profiles").select("*")
    if user_id:
        query = query.eq("user_id", user_id)
    profiles = query.execute().data
    if user_id and not profiles:
        raise SystemExit(f"no profile for user {user_id}")

    saved: dict[str, int] = {}
    for row in profiles:
        uid = row["user_id"]
        existing = (db.table("topics").select("rank").eq("user_id", uid).eq("date", day.isoformat())
                    .execute().data)
        if len(existing) >= TOPICS_PER_DAY and not force:
            logger.info("user %s already has %d topics for %s", uid, len(existing), day)
            continue
        try:
            profile = Profile.model_validate(row)
            topics = topics_for(profile, llm, tavily, recent_titles(db, uid, day))
            if not topics:
                raise RuntimeError("every topic failed")
            rows = save(db, uid, day, topics)
            saved[uid] = len(topics)
            if covers:
                try:
                    covers(rows)
                except Exception:
                    logger.exception("covers failed for user %s", uid)
            logger.info("user %s: %d topics saved for %s", uid, len(topics), day)
        except Exception:
            logger.exception("user %s skipped", uid)
            saved[uid] = 0
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user", help="only this user_id")
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--force", action="store_true", help="redo users who already have topics")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "httpx2"):  # one line per HTTP call otherwise
        logging.getLogger(noisy).setLevel(logging.WARNING)

    import anthropic
    from tavily import TavilyClient

    from common.db import client

    db, llm = client(), anthropic.Anthropic()
    with httpx.Client() as http:
        saved = run(db, llm, TavilyClient(api_key=require("TAVILY_API_KEY")), args.date, args.user, args.force,
                    covers=lambda rows: make_covers(db, llm, http, rows))
    failed = [u for u, n in saved.items() if n == 0]
    logger.info("done: %d users, %d topics, %d failed", len(saved), sum(saved.values()), len(failed))
    if failed:
        raise SystemExit(1)  # Render marks the cron run as failed


if __name__ == "__main__":
    main()
