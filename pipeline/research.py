"""News for the morning job: Tavily search per query, full article text for the writer."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import trafilatura

logger = logging.getLogger("pipeline")

MAX_TEXT_CHARS = 8000  # per article, enough for a brief; keeps each topic call ~10k tokens


@dataclass
class Article:
    id: str  # "a1", "a2"...: how the picking step refers to it
    title: str
    url: str
    snippet: str
    text: str
    date: str | None = None

    @property
    def publisher(self) -> str:
        return urlparse(self.url).netloc.removeprefix("www.")


def search_news(tavily, queries: list[str], per_query: int) -> list[Article]:
    """Recent news for every query, deduplicated by URL, numbered a1, a2...

    Queries run in parallel: a slow site (missing text, fetched with trafilatura) can take
    a minute, and one user has up to 6 queries."""
    with ThreadPoolExecutor(max_workers=len(queries) or 1) as pool:
        per_query_results = list(pool.map(lambda q: search_one(tavily, q, per_query), queries))

    articles: dict[str, Article] = {}
    for results in per_query_results:
        for r in results:
            if r["url"] in articles:
                continue
            articles[r["url"]] = Article(
                id=f"a{len(articles) + 1}", title=r["title"], url=r["url"],
                snippet=(r.get("content") or "")[:400], text=r["text"][:MAX_TEXT_CHARS],
                date=iso_date(r.get("published_date")),
            )
    return list(articles.values())


def search_one(tavily, query: str, per_query: int) -> list[dict]:
    """Tavily results for one query that have enough text to brief from (in r["text"])."""
    try:
        results = tavily.search(query, topic="news", time_range="week", max_results=per_query,
                                include_raw_content="text")["results"]
    except Exception:
        logger.exception("search failed: %s", query)
        return []
    usable = []
    for r in results:
        r["text"] = (r.get("raw_content") or "").strip() or fetch_text(r["url"])
        if len(r["text"]) >= 300:  # else paywall, video page or a list of links
            usable.append(r)
    return usable


def iso_date(value: str | None) -> str | None:
    """'2026-10-19T08:00:00Z' or 'Mon, 19 Oct 2026 08:00:00 GMT' -> '2026-10-19'."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return None


def fetch_text(url: str) -> str:
    """Main text of a page, when Tavily didn't bring it."""
    try:
        html = trafilatura.fetch_url(url)
        return (trafilatura.extract(html) or "") if html else ""
    except Exception:
        logger.warning("could not fetch %s", url)
        return ""
