"""Jooble - free API key, aggregates many UK boards.
Docs: https://jooble.org/api/about
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from ..config import Config, env
from ..models import Job
from .base import SourceError, http_post


log = logging.getLogger(__name__)


def fetch(cfg: Config) -> list[Job]:
    key = env("JOOBLE_API_KEY")
    if not key:
        log.info("Jooble: JOOBLE_API_KEY not set, skipping.")
        return []

    url = f"https://jooble.org/api/{key}"
    jobs: list[Job] = []

    for loc in cfg.locations:
        for kw in cfg.titles_any:
            body = {
                "keywords": kw,
                "location": loc.adzuna_where,
                "page": "1",
                "ResultOnPage": "50",
            }
            try:
                r = http_post(url, json=body)
            except SourceError as e:
                log.warning("Jooble failed: %s", e)
                continue
            if r.status_code != 200:
                log.warning("Jooble HTTP %s", r.status_code)
                continue
            for item in r.json().get("jobs", []):
                jobs.append(_to_job(item))
    return jobs


_SALARY_RE = re.compile(r"\u00a3\s*([\d,]+)(?:\s*[-\u2013to]+\s*\u00a3?\s*([\d,]+))?", re.I)


def _parse_salary(raw: str | None) -> tuple[float | None, float | None]:
    if not raw:
        return None, None
    m = _SALARY_RE.search(raw)
    if not m:
        return None, None
    mn = float(m.group(1).replace(",", ""))
    mx = float(m.group(2).replace(",", "")) if m.group(2) else None
    return mn, mx


def _to_job(item: dict) -> Job:
    posted = None
    if item.get("updated"):
        try:
            posted = datetime.fromisoformat(item["updated"])
        except ValueError:
            posted = None
    mn, mx = _parse_salary(item.get("salary"))
    return Job(
        source="jooble",
        source_id=str(item.get("id", "") or item.get("link", "")),
        title=(item.get("title") or "").strip(),
        company=(item.get("company") or "").strip() or None,
        location=item.get("location"),
        url=item.get("link", ""),
        description=item.get("snippet", "") or "",
        salary_min=mn,
        salary_max=mx,
        salary_raw=item.get("salary") or None,
        posted_at=posted,
    )
