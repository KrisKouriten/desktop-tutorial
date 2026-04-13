"""Public UK job-board RSS feeds: CV-Library and Totaljobs.

These feeds advertise searches in a URL with keyword + location parameters, then
expose the results as RSS. No API keys required.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import quote_plus

try:
    import feedparser
except ImportError:   # feedparser is optional; rss source disables itself.
    feedparser = None  # type: ignore[assignment]

from ..config import Config
from ..models import Job
from .base import SourceError, http_get


log = logging.getLogger(__name__)

# Public RSS endpoints. These occasionally change - if one breaks, it's skipped.
FEEDS = [
    # CV-Library RSS pattern
    ("cv-library",
     "https://www.cv-library.co.uk/search-jobs/{kw}/{loc}/rss"),
    # Totaljobs RSS pattern
    ("totaljobs",
     "https://www.totaljobs.com/jobs/rss/{kw}/in-{loc}"),
]


def fetch(cfg: Config) -> list[Job]:
    if feedparser is None:
        log.info("feedparser not installed; skipping RSS source.")
        return []
    jobs: list[Job] = []
    for loc in cfg.locations:
        for kw in cfg.titles_any:
            for source_name, template in FEEDS:
                url = template.format(
                    kw=quote_plus(kw.replace(" ", "-")),
                    loc=quote_plus(loc.adzuna_where.lower().replace(" ", "-")),
                )
                try:
                    r = http_get(url, headers={"User-Agent": "Mozilla/5.0"})
                except SourceError as e:
                    log.warning("%s RSS failed: %s", source_name, e)
                    continue
                if r.status_code != 200:
                    log.debug("%s RSS HTTP %s", source_name, r.status_code)
                    continue
                feed = feedparser.parse(r.content)
                for entry in feed.entries:
                    jobs.append(_to_job(source_name, entry))
    return jobs


_SALARY_RE = re.compile(r"\u00a3\s*([\d,]+)(?:\s*[-\u2013to]+\s*\u00a3?\s*([\d,]+))?", re.I)


def _to_job(source_name: str, entry) -> Job:
    desc = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    mn = mx = None
    raw = None
    m = _SALARY_RE.search(desc) or _SALARY_RE.search(getattr(entry, "title", ""))
    if m:
        raw = m.group(0)
        mn = float(m.group(1).replace(",", ""))
        mx = float(m.group(2).replace(",", "")) if m.group(2) else None

    posted = None
    if getattr(entry, "published_parsed", None):
        posted = datetime(*entry.published_parsed[:6])

    return Job(
        source=source_name,
        source_id=getattr(entry, "id", "") or getattr(entry, "link", ""),
        title=getattr(entry, "title", "").strip(),
        company=None,   # rarely structured in RSS
        location=None,
        url=getattr(entry, "link", ""),
        description=desc,
        salary_min=mn,
        salary_max=mx,
        salary_raw=raw,
        posted_at=posted,
    )
