"""SerpApi - paid. Used to reach LinkedIn Jobs and Indeed via Google Jobs results.
Docs: https://serpapi.com/google-jobs-api
"""
from __future__ import annotations

import logging
import re

from ..config import Config, env
from ..models import Job
from .base import SourceError, http_get


log = logging.getLogger(__name__)
ENDPOINT = "https://serpapi.com/search.json"


def fetch(cfg: Config) -> list[Job]:
    key = env("SERPAPI_KEY")
    if not key:
        log.info("SerpApi: SERPAPI_KEY not set, skipping.")
        return []

    jobs: list[Job] = []
    for loc in cfg.locations:
        for kw in cfg.titles_any:
            params = {
                "engine": "google_jobs",
                "q": f"{kw} {loc.adzuna_where}",
                "hl": "en",
                "gl": "uk",
                "api_key": key,
                "chips": "date_posted:week",
            }
            try:
                r = http_get(ENDPOINT, params=params)
            except SourceError as e:
                log.warning("SerpApi failed: %s", e)
                continue
            if r.status_code != 200:
                log.warning("SerpApi HTTP %s", r.status_code)
                continue
            for item in r.json().get("jobs_results", []):
                jobs.append(_to_job(item))
    return jobs


_SALARY_RE = re.compile(r"\u00a3\s*([\d,]+)(?:\s*[-\u2013to]+\s*\u00a3?\s*([\d,]+))?", re.I)


def _to_job(item: dict) -> Job:
    # Prefer the apply-link that points to Indeed/LinkedIn if present.
    url = ""
    for a in item.get("apply_options", []) or []:
        if a.get("link"):
            url = a["link"]
            break
    if not url:
        url = item.get("share_link") or item.get("related_links", [{}])[0].get("link", "")

    salary_raw = None
    for ext in item.get("detected_extensions", {}).values() or []:
        pass  # not used directly
    # salary sometimes in extensions list as plain text
    for ext in item.get("extensions", []) or []:
        if "\u00a3" in ext or "GBP" in ext:
            salary_raw = ext
            break
    mn = mx = None
    if salary_raw:
        m = _SALARY_RE.search(salary_raw)
        if m:
            mn = float(m.group(1).replace(",", ""))
            mx = float(m.group(2).replace(",", "")) if m.group(2) else None

    return Job(
        source="serpapi",
        source_id=item.get("job_id", "") or url,
        title=(item.get("title") or "").strip(),
        company=(item.get("company_name") or "").strip() or None,
        location=item.get("location"),
        url=url,
        description=item.get("description", "") or "",
        salary_min=mn,
        salary_max=mx,
        salary_raw=salary_raw,
    )
