"""
Generic RSS / Atom feed ingestion for recruiter sites.

Reed and the big boards don't need this — the RSS lane is for agency
feeds and niche aggregators (CVLibrary, Jobserve, individual recruiters
that publish feeds). Add feed URLs in criteria.RSS_FEEDS.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .. import criteria as C


def fetch() -> list[dict]:
    if not C.RSS_FEEDS:
        return []
    try:
        import feedparser  # lazy — optional dependency
    except ImportError:
        print("[rss] feedparser not installed; skipping RSS sources")
        return []

    results: list[dict] = []
    for url in C.RSS_FEEDS:
        results.extend(_fetch_feed(feedparser, url))
    return results


def _fetch_feed(feedparser, url: str) -> list[dict]:
    try:
        parsed = feedparser.parse(url)
    except Exception as exc:
        print(f"[rss] failed to parse {url}: {exc}")
        return []

    feed_title = (parsed.feed or {}).get("title", url)
    out: list[dict] = []
    for entry in parsed.entries or []:
        link = entry.get("link") or ""
        if not link:
            continue
        eid = entry.get("id") or link
        out.append(
            {
                "source": f"rss:{feed_title}",
                "external_id": f"rss:{_hash(eid)}",
                "title": entry.get("title") or "",
                "company": entry.get("author") or "",
                "location": _tag_value(entry, "location"),
                "description": entry.get("summary") or entry.get("description") or "",
                "url": link,
                "salary_min": None,
                "salary_max": None,
                "salary_is_day_rate": False,
                "contract_type": "unknown",
                "posted_at": _parse_date(entry),
            }
        )
    return out


def _tag_value(entry, key: str) -> str:
    tags = entry.get("tags") or []
    for t in tags:
        if (t.get("scheme") or "").endswith(key):
            return t.get("term") or ""
    return ""


def _hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def _parse_date(entry) -> str | None:
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
            except (TypeError, ValueError):
                continue
    return None
