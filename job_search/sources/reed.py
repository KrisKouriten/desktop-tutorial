"""
Reed.co.uk job search API client.

Docs: https://www.reed.co.uk/developers/jobseeker
Auth: HTTP Basic, username = your API key, password = empty.
Get a free key at https://www.reed.co.uk/developers.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Iterable

import requests

from .. import criteria as C

API_URL = "https://www.reed.co.uk/api/1.0/search"
PAGE_SIZE = 100


def _auth() -> tuple[str, str] | None:
    key = os.environ.get("REED_API_KEY")
    if not key:
        return None
    return (key, "")


def fetch() -> list[dict]:
    """Search Reed for each location in criteria and return normalised listings."""
    auth = _auth()
    if auth is None:
        return []

    results: list[dict] = []
    for location in C.LOCATIONS:
        for title in _title_queries():
            results.extend(_fetch_one(auth, title, location))
    return results


def _title_queries() -> Iterable[str]:
    # Reed's keyword search is pretty forgiving — keep queries short so we
    # don't over-filter at the API layer. The scorer does the precise match.
    yield "finance director"
    yield "chief financial officer"
    yield "head of finance"


def _fetch_one(auth: tuple[str, str], keywords: str, location: str) -> list[dict]:
    params = {
        "keywords": keywords,
        "locationName": location,
        "distanceFromLocation": C.MILES_RADIUS,
        "minimumSalary": C.SALARY_MIN,
        "permanent": "true" if C.INCLUDE_PERMANENT else "false",
        "contract": "true" if C.INCLUDE_CONTRACT else "false",
        "resultsToTake": PAGE_SIZE,
    }
    try:
        r = requests.get(API_URL, params=params, auth=auth, timeout=20)
        r.raise_for_status()
    except requests.RequestException as exc:
        print(f"[reed] request failed for {keywords!r} @ {location}: {exc}")
        return []

    payload = r.json() or {}
    raw = payload.get("results", [])
    return [_normalise(item) for item in raw]


def _normalise(item: dict) -> dict:
    return {
        "source": "reed",
        "external_id": f"reed:{item.get('jobId')}",
        "title": item.get("jobTitle") or "",
        "company": item.get("employerName") or "",
        "location": item.get("locationName") or "",
        "description": item.get("jobDescription") or "",
        "url": item.get("jobUrl") or "",
        "salary_min": _num(item.get("minimumSalary")),
        "salary_max": _num(item.get("maximumSalary")),
        "salary_is_day_rate": False,
        "contract_type": _contract_type(item),
        "posted_at": _parse_date(item.get("date")),
    }


def _num(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _contract_type(item: dict) -> str:
    if item.get("contractType"):
        return str(item["contractType"]).lower()
    if item.get("contract"):
        return "contract"
    if item.get("permanent"):
        return "permanent"
    return "unknown"


def _parse_date(s: str | None) -> str | None:
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return None
