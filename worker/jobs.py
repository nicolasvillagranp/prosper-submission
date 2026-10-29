"""What the worker does each tick: briefing requests, and deciding when the morning job is due."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from pipeline.briefing import get_briefing

logger = logging.getLogger("worker")


def reset_stuck(db) -> None:
    """Requests left "working" by a worker that stopped mid-way go back in the queue."""
    db.table("briefings").update({"status": "requested"}).eq("status", "working").execute()


def process_briefings(db, llm, http, limit: int = 3) -> int:
    """Make the oldest requested briefings. Returns how many were handled."""
    pending = (db.table("briefings").select("topic_id,user_id").eq("status", "requested")
               .order("requested_at").limit(limit).execute().data)
    for row in pending:
        claimed = (db.table("briefings").update({"status": "working", "error": None})
                   .eq("topic_id", row["topic_id"]).eq("status", "requested").execute().data)
        if not claimed:  # someone else took it
            continue
        try:
            b = get_briefing(db, llm, http, row["topic_id"], row["user_id"])
            db.table("briefings").update({
                "status": "ready", "audio_path": b.audio_path, "script": b.script,
                "ready_at": datetime.now(timezone.utc).isoformat(),
            }).eq("topic_id", row["topic_id"]).execute()
            logger.info("briefing ready for topic %s (%s)", row["topic_id"], "new" if b.created else "cached")
        except Exception as e:
            logger.exception("briefing failed for topic %s", row["topic_id"])
            db.table("briefings").update({"status": "failed", "error": str(e)[:500]}) \
              .eq("topic_id", row["topic_id"]).execute()
    return len(pending)


def users_without_topics(db) -> list[str]:
    """New users: a profile (they finished onboarding) but no topics yet, ever."""
    users = [r["user_id"] for r in db.table("profiles").select("user_id").execute().data]
    return [u for u in users
            if not db.table("topics").select("id").eq("user_id", u).limit(1).execute().data]


def morning_due(now: datetime, last_run: date | None, hour: int) -> bool:
    """True once per day, from `hour` on (local time)."""
    return now.hour >= hour and last_run != now.date()
