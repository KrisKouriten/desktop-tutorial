"""Apply the user's criteria to a raw list of jobs."""
from __future__ import annotations

from typing import Iterable

from .config import Config
from .models import Job


def _text(job: Job) -> str:
    return f"{job.title}\n{job.description}".lower()


def _title_matches(job: Job, cfg: Config) -> bool:
    t = job.title.lower()
    if any(excl in t for excl in cfg.titles_exclude):
        return False
    return any(want in t for want in cfg.titles_any)


def _salary_ok(job: Job, cfg: Config) -> bool:
    top = job.salary_top()
    if top is None:
        # no advertised salary: keep unless strict_salary is on
        return not cfg.strict_salary
    return top >= cfg.min_salary_gbp


def _hybrid_ok(job: Job, cfg: Config) -> tuple[bool, list[str]]:
    blob = _text(job)
    hits = [term.upper() for term in cfg.hybrid_remote_terms if term in blob]
    if cfg.require_hybrid_or_remote and not hits:
        return False, []
    return True, hits


def apply(jobs: Iterable[Job], cfg: Config) -> list[Job]:
    out: list[Job] = []
    for j in jobs:
        if not _title_matches(j, cfg):
            continue
        if not _salary_ok(j, cfg):
            continue
        hybrid_ok, hybrid_hits = _hybrid_ok(j, cfg)
        if not hybrid_ok:
            continue
        # annotate
        if hybrid_hits:
            for h in hybrid_hits:
                if h not in j.tags:
                    j.tags.append(h)
        if j.salary_top() is None:
            j.tags.append("SALARY-UNSTATED")
        out.append(j)
    return out
