"""Fetch headlines from Google News RSS, normalise and de-duplicate them."""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import quote

import feedparser

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:{lang}"


@dataclass
class Article:
    title: str
    link: str = ""
    source: str = ""
    published: datetime | None = None
    query: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def age_hours(self) -> float | None:
        if self.published is None:
            return None
        return max(0.0, (datetime.now(timezone.utc) - self.published).total_seconds() / 3600)


def build_url(query: str, region: str = "IN", lang: str = "en", window: str | None = "2d") -> str:
    """Google News RSS URL. `window` uses Google's `when:` operator (e.g. 1d, 7d)."""
    q = f"{query} when:{window}" if window else query
    return GOOGLE_NEWS_RSS.format(q=quote(q), hl=f"{lang}-{region}", gl=region, lang=lang)


def _parse_time(entry) -> datetime | None:
    st = entry.get("published_parsed") or entry.get("updated_parsed")
    if not st:
        return None
    return datetime.fromtimestamp(time.mktime(st), tz=timezone.utc)


def _split_source(title: str, entry) -> tuple[str, str]:
    """Google News titles look like 'Headline - Publisher'. Split the publisher off."""
    src = ""
    if entry.get("source") and getattr(entry.source, "title", None):
        src = entry.source.title
    if src and title.endswith(f" - {src}"):
        title = title[: -len(src) - 3]
    elif " - " in title and not src:
        title, src = title.rsplit(" - ", 1)
    return title.strip(), src.strip()


def parse_feed(feed, query: str = "", limit: int | None = None) -> list[Article]:
    out = []
    for entry in feed.entries[:limit]:
        title, src = _split_source(entry.get("title", ""), entry)
        if not title:
            continue
        out.append(Article(title=title, link=entry.get("link", ""), source=src,
                           published=_parse_time(entry), query=query))
    return out


def fetch_news(query: str, limit: int = 15, region: str = "IN", window: str | None = "2d") -> list[Article]:
    feed = feedparser.parse(build_url(query, region=region, window=window))
    if not feed.entries and feed.get("bozo"):
        print(f"warning: could not fetch news for '{query}': {feed.get('bozo_exception')}", file=sys.stderr)
    return parse_feed(feed, query=query, limit=limit)


_norm_re = re.compile(r"[^a-z0-9 ]+")


def _key(title: str) -> str:
    words = _norm_re.sub(" ", title.lower()).split()
    return " ".join(words[:12])


def dedupe(articles: Iterable[Article]) -> list[Article]:
    """Drop near-identical headlines (same first 12 normalised words), keep the newest."""
    best: dict[str, Article] = {}
    for a in articles:
        k = _key(a.title)
        cur = best.get(k)
        if cur is None or (a.published and (cur.published is None or a.published > cur.published)):
            best[k] = a
    return sorted(best.values(), key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
                  reverse=True)
