"""Adzuna - free official API aggregating hundreds of UK boards incl. recruiters.
Docs: https://developer.adzuna.com/docs/search
"""
from __future__ import annotations

import logging
from datetime import datetime

from ..config import Config, env
from ..models import Job
from .base import SourceError, http_get


log = logging.getLogger(__name__)
BASE = "https://api.adzuna.com/v1/api/jobs/gb/search/1"


def fetch(cfg: Config) -> list[Job]:
    app_id = env("ADZUNA_APP_ID")
    app_key = env("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        log.info("Adzuna: credentials not set, skipping.")
        return []

    jobs: list[Job] = []
    for loc in cfg.locations:
        for kw in cfg.titles_any:
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": 50,
                "what": kw,
                "where": loc.adzuna_where,
                "sort_by": "date",
                "max_days_old": 14,
                "content-type": "application/json",
            }
            if cfg.strict_salary:
                params["salary_min"] = int(cfg.min_salary_gbp)
            try:
                r = http_get(BASE, params=params)
            except SourceError as e:
                log.warning("Adzuna failed: %s", e)
                continue
            if r.status_code != 200:
                log.warning("Adzuna HTTP %s for %s/%s", r.status_code, loc.name, kw)
                continue
            data = r.json()
            for item in data.get("results", []):
                jobs.append(_to_job(item))
    return jobs


def _to_job(item: dict) -> Job:
    posted = None
    if item.get("created"):
        try:
            posted = datetime.fromisoformat(item["created"].replace("Z", "+00:00"))
        except ValueError:
            posted = None
    company = (item.get("company") or {}).get("display_name")
    loc = (item.get("location") or {}).get("display_name")
    return Job(
        source="adzuna",
        source_id=str(item.get("id", "")),
        title=item.get("title", "").strip(),
        company=company,
        location=loc,
        url=item.get("redirect_url", ""),
        description=item.get("description", "") or "",
        salary_min=item.get("salary_min"),
        salary_max=item.get("salary_max"),
        salary_raw=_fmt(item.get("salary_min"), item.get("salary_max")),
        posted_at=posted,
    )


def _fmt(mn, mx):
    if mn and mx:
        return f"\u00a3{int(mn):,} - \u00a3{int(mx):,}"
    if mn:
        return f"\u00a3{int(mn):,}+"
    return None
