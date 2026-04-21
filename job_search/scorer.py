"""
Score a listing 0..100 against the criteria in job_search.criteria.

The scorer is deliberately simple: each dimension is scored 0..1 and
multiplied by its weight. A hard exclude (e.g. junior title keyword,
blocked industry) returns a score of 0 and a reason.
"""
from __future__ import annotations

from . import criteria as C


def score(listing: dict) -> tuple[float, list[str]]:
    reasons: list[str] = []

    # Hard excludes first.
    excl = _title_excluded(listing)
    if excl:
        return 0.0, [f"excluded by title keyword: {excl}"]

    excl_ind = _industry_excluded(listing)
    if excl_ind:
        return 0.0, [f"excluded industry: {excl_ind}"]

    weights = C.WEIGHTS
    total_weight = sum(weights.values()) or 1

    title_s, title_r = _title_score(listing)
    loc_s, loc_r = _location_score(listing)
    sal_s, sal_r = _salary_score(listing)
    role_s, role_r = _role_type_score(listing)
    ind_s, ind_r = _industry_score(listing)

    weighted = (
        title_s * weights["title"]
        + loc_s * weights["location"]
        + sal_s * weights["salary"]
        + role_s * weights["role_type"]
        + ind_s * weights["industry"]
    )
    score_0_100 = round(100 * weighted / total_weight, 1)

    for r in (title_r, loc_r, sal_r, role_r, ind_r):
        if r:
            reasons.append(r)

    return score_0_100, reasons


# ---------------------------------------------------------------------------
# Individual dimensions
# ---------------------------------------------------------------------------
def _title_excluded(li: dict) -> str | None:
    title = (li.get("title") or "").lower()
    for kw in C.TITLE_EXCLUDE:
        if kw in title:
            return kw
    return None


def _title_score(li: dict) -> tuple[float, str]:
    title = (li.get("title") or "").lower()
    hits = [kw for kw in C.TITLE_INCLUDE if kw in title]
    if not hits:
        return 0.0, ""
    # Reward more specific matches over short ones like "fd".
    best = max(hits, key=len)
    strength = min(1.0, len(best) / 18)  # "finance director" ~= 0.88, "fd" = 0.11
    return strength, f"title match: {best}"


def _location_score(li: dict) -> tuple[float, str]:
    loc = (li.get("location") or "").lower()
    if not loc:
        return 0.5, "location unknown"
    for kw in C.REGION_KEYWORDS:
        if kw in loc:
            return 1.0, f"location match: {kw}"
    return 0.0, f"location out of scope: {loc}"


def _salary_score(li: dict) -> tuple[float, str]:
    mn = li.get("salary_min")
    mx = li.get("salary_max")
    day_rate = bool(li.get("salary_is_day_rate"))
    floor = C.DAY_RATE_MIN if day_rate else C.SALARY_MIN

    headline = mx or mn
    if headline is None:
        # No salary disclosed — neutral score, not a fail.
        return 0.5, "salary not disclosed"
    if headline >= floor * 1.25:
        return 1.0, f"salary {headline:,.0f} ≫ floor"
    if headline >= floor:
        return 0.8, f"salary {headline:,.0f} ≥ floor"
    if headline >= floor * 0.9:
        return 0.4, f"salary {headline:,.0f} below floor"
    return 0.0, f"salary {headline:,.0f} well below floor"


def _role_type_score(li: dict) -> tuple[float, str]:
    ct = (li.get("contract_type") or "").lower()
    is_perm = "perm" in ct
    is_contract = any(k in ct for k in ("contract", "interim", "temp", "fixed"))

    if is_perm and C.INCLUDE_PERMANENT:
        return 1.0, "permanent"
    if is_contract and C.INCLUDE_CONTRACT:
        return 1.0, "contract/interim"
    if not ct or ct == "unknown":
        return 0.7, "role type unknown"
    if (is_perm and not C.INCLUDE_PERMANENT) or (is_contract and not C.INCLUDE_CONTRACT):
        return 0.0, f"role type excluded: {ct}"
    return 0.5, f"role type: {ct}"


def _industry_excluded(li: dict) -> str | None:
    blob = f"{li.get('title') or ''} {li.get('company') or ''} {li.get('description') or ''}".lower()
    for kw in C.INDUSTRY_EXCLUDED:
        if kw.lower() in blob:
            return kw
    return None


def _industry_score(li: dict) -> tuple[float, str]:
    if not C.INDUSTRY_PREFERRED:
        return 1.0, ""  # no preference expressed
    blob = f"{li.get('title') or ''} {li.get('company') or ''} {li.get('description') or ''}".lower()
    for kw in C.INDUSTRY_PREFERRED:
        if kw.lower() in blob:
            return 1.0, f"preferred industry: {kw}"
    return 0.5, "industry neutral"
