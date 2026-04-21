"""
Adzuna UK job search API client.

Docs: https://developer.adzuna.com/docs/search
Free tier allows ~250 calls/day. Register at https://developer.adzuna.com/.

Adzuna aggregates from many UK sources (including a lot of agency feeds and
some Indeed-syndicated listings), so it's the best "covers everything else"
lane alongside Reed.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

from .. import criteria as C

API_URL = "https://api.adzuna.com/v1/api/jobs/gb/search/{page}"
PAGE_SIZE = 50
MAX_PAGES = 3


def _credentials() -> tuple[str, str] | None:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return None
    return app_id, app_key


def fetch() -> list[dict]:
    creds = _credentials()
    if creds is None:
        return []

    results: list[dict] = []
    for location in C.LOCATIONS:
        results.extend(_fetch_location(creds, location))
    return results


def _fetch_location(creds: tuple[str, str], location: str) -> list[dict]:
    app_id, app_key = creds
    out: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": "finance director",
            "where": location,
            "distance": C.MILES_RADIUS,
            "salary_min": C.SALARY_MIN,
            "results_per_page": PAGE_SIZE,
            "content-type": "application/json",
            "sort_by": "date",
        }
        try:
            r = requests.get(API_URL.format(page=page), params=params, timeout=20)
            r.raise_for_status()
        except requests.RequestException as exc:
            print(f"[adzuna] request failed for {location} p{page}: {exc}")
            break

        payload = r.json() or {}
        batch = payload.get("results", [])
        if not batch:
            break
        out.extend(_normalise(item) for item in batch)
        if len(batch) < PAGE_SIZE:
            break
    return out


def _normalise(item: dict) -> dict:
    company = (item.get("company") or {}).get("display_name", "")
    location = (item.get("location") or {}).get("display_name", "")
    category = (item.get("category") or {}).get("label", "")
    contract_time = item.get("contract_time") or ""
    contract_type = item.get("contract_type") or ""
    return {
        "source": "adzuna",
        "external_id": f"adzuna:{item.get('id')}",
        "title": item.get("title") or "",
        "company": company,
        "location": location,
        "description": item.get("description") or "",
        "url": item.get("redirect_url") or "",
        "salary_min": _num(item.get("salary_min")),
        "salary_max": _num(item.get("salary_max")),
        "salary_is_day_rate": False,
        "contract_type": (contract_type or contract_time or category or "unknown").lower(),
        "posted_at": _parse_date(item.get("created")),
    }


def _num(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _parse_date(s: str | None) -> str | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None
