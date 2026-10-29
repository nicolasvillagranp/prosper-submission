"""Entry point of the Docker worker (see worker/__init__.py)."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic
import httpx
from tavily import TavilyClient

from common.config import CONFIG, require
from common.db import client, connect
from pipeline.covers import make_covers
from pipeline.run_daily import run as run_morning
from worker.jobs import morning_due, process_briefings, reset_stuck, users_without_topics

logger = logging.getLogger("worker")
SETTINGS = CONFIG["worker"]
TZ = ZoneInfo(SETTINGS["timezone"])


def run_with_covers(day, user_id=None) -> None:
    """The morning job for everyone (or one new user), with covers. Own clients: runs in a thread."""
    db, llm = connect(), anthropic.Anthropic()
    with httpx.Client() as http:
        run_morning(db, llm, TavilyClient(api_key=require("TAVILY_API_KEY")), day, user_id=user_id,
                    covers=lambda rows: make_covers(db, llm, http, rows))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for noisy in ("httpx", "httpx2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    db, llm, http = client(), anthropic.Anthropic(), httpx.Client()
    try:
        reset_stuck(db)
    except Exception:
        logger.exception("can't read the briefings table: has supabase/migrations/002_briefings.sql been run?")
    last_morning = None
    morning: threading.Thread | None = None
    last_new_user_check = 0.0
    started_for: dict[str, float] = {}  # new user -> when their first topics were started
    logger.info("worker up: briefings every %ss, morning job from %02d:00 %s",
                SETTINGS["poll_seconds"], SETTINGS["morning_hour"], SETTINGS["timezone"])

    while True:
        now = datetime.now(TZ)
        if morning_due(now, last_morning, SETTINGS["morning_hour"]) and not (morning and morning.is_alive()):
            last_morning = now.date()
            morning = threading.Thread(target=run_with_covers, name="morning", daemon=True, args=(now.date(),))
            morning.start()
            logger.info("morning job started for %s", now.date())
        if time.monotonic() - last_new_user_check > SETTINGS["new_user_check_seconds"]:
            last_new_user_check = time.monotonic()
            try:
                for uid in users_without_topics(db):
                    if time.monotonic() - started_for.get(uid, -1e9) < 1800:  # running, or failed recently
                        continue
                    started_for[uid] = time.monotonic()
                    threading.Thread(target=run_with_covers, name=f"first-{uid[:8]}", daemon=True,
                                     args=(now.date(), uid)).start()
                    logger.info("first topics started for new user %s", uid)
            except Exception:
                logger.exception("new-user check failed")
        try:
            if process_briefings(db, llm, http) == 0:
                time.sleep(SETTINGS["poll_seconds"])
        except Exception:
            logger.exception("briefing loop error (missing table? run 002_briefings.sql); retrying in a minute")
            time.sleep(60)


if __name__ == "__main__":
    main()
