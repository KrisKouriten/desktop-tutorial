"""Reed.co.uk - free official API.
Docs: https://www.reed.co.uk/developers/jobseeker
Auth: HTTP Basic, username = API key, password = empty.
"""
from __future__ import annotations

import logging
from datetime import datetime

from ..config import Config, env
from ..models import Job
from .base import SourceError, http_get


log = logging.getLogger(__name__)
ENDPOINT = "https://www.reed.co.uk/api/1.0/search"


def fetch(cfg: Config) -> list[Job]:
    api_key = env("REED_API_KEY")
    if not api_key:
        log.info("Reed: REED_API_KEY not set, skipping.")
        return []

    jobs: list[Job] = []
    for loc in cfg.locations:
        for kw in cfg.titles_any:
            params = {
                "keywords": kw,
                "locationName": loc.reed_location,
                "distanceFromLocation": loc.reed_distance,
                "minimumSalary": int(cfg.min_salary_gbp) if cfg.strict_salary else 0,
                "resultsToTake": 100,
            }
            try:
                r = http_get(ENDPOINT, params=params, auth=(api_key, ""))
            except SourceError as e:
                log.warning("Reed query failed: %s", e)
                continue
            if r.status_code != 200:
                log.warning("Reed HTTP %s for %s/%s", r.status_code, loc.name, kw)
                continue
            data = r.json()
            for item in data.get("results", []):
                jobs.append(_to_job(item))
    return jobs


def _to_job(item: dict) -> Job:
    posted = None
    if item.get("date"):
        try:
            posted = datetime.strptime(item["date"], "%d/%m/%Y")
        except ValueError:
            posted = None
    return Job(
        source="reed",
        source_id=str(item["jobId"]),
        title=item.get("jobTitle", "").strip(),
        company=(item.get("employerName") or "").strip() or None,
        location=item.get("locationName"),
        url=item.get("jobUrl", ""),
        description=item.get("jobDescription", "") or "",
        salary_min=item.get("minimumSalary"),
        salary_max=item.get("maximumSalary"),
        salary_raw=_salary_raw(item),
        posted_at=posted,
    )


def _salary_raw(item: dict) -> str | None:
    mn, mx = item.get("minimumSalary"), item.get("maximumSalary")
    if mn and mx:
        return f"\u00a3{int(mn):,} - \u00a3{int(mx):,}"
    if mn:
        return f"\u00a3{int(mn):,}+"
    return None
