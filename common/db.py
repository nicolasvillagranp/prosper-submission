"""Supabase access for server code (agent, morning job, web server).

Uses the secret key, which bypasses RLS: every query here must filter by user or id itself.
Never import this from anything that runs in the browser.
"""

from __future__ import annotations

from functools import cache

from supabase import Client, create_client

from common.config import require
from schema.models import Topic


def connect() -> Client:
    """A new client. Use one per thread: the Supabase client isn't shared across threads."""
    return create_client(require("SUPABASE_URL"), require("SUPABASE_SECRET_KEY"))


@cache
def client() -> Client:
    """The process-wide client, for single-threaded code."""
    return connect()


def load_topic(topic_id: str, db: Client | None = None) -> Topic:
    """The topic row `topic_id`, validated. Raises LookupError if it doesn't exist."""
    rows = (db or client()).table("topics").select("*").eq("id", topic_id).limit(1).execute().data
    if not rows:
        raise LookupError(f"topic {topic_id} not found")
    return Topic.model_validate(rows[0])
