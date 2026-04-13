"""Entry point: fetch from enabled sources, filter, dedup, email new jobs."""
from __future__ import annotations

import argparse
import logging
from typing import Callable

from . import filters
from .config import Config, load_config, load_env
from .models import Job
from .notify import send_email
from .store import JobStore
from .sources import adzuna, jooble, reed, rss, serpapi


log = logging.getLogger(__name__)


FETCHERS: dict[str, Callable[[Config], list[Job]]] = {
    "reed": reed.fetch,
    "adzuna": adzuna.fetch,
    "jooble": jooble.fetch,
    "serpapi": serpapi.fetch,
    "rss": rss.fetch,
}


def collect(cfg: Config) -> list[Job]:
    all_jobs: list[Job] = []
    for name, fetcher in FETCHERS.items():
        if not cfg.sources.get(name, False):
            continue
        try:
            batch = fetcher(cfg)
            log.info("%s: %d jobs", name, len(batch))
            all_jobs.extend(batch)
        except Exception as e:   # never let one source break the run
            log.exception("%s crashed: %s", name, e)
    return all_jobs


def run(cfg_path: str, db_path: str, dry_run: bool) -> int:
    load_env()
    cfg = load_config(cfg_path)
    store = JobStore(db_path)

    raw = collect(cfg)
    log.info("Collected %d raw jobs from all sources", len(raw))

    matched = filters.apply(raw, cfg)
    log.info("%d jobs match criteria", len(matched))

    fresh = store.filter_new(matched)
    log.info("%d are new since last run", len(fresh))

    # stable ordering: newest first where we have dates, then by title
    fresh.sort(key=lambda j: (j.posted_at or j.fetched_at, j.title), reverse=True)

    if dry_run:
        from .notify import render_text
        print(render_text(fresh))
        return len(fresh)

    if fresh:
        send_email(fresh, cfg)
        store.mark_seen(fresh)
    elif not cfg.skip_if_empty:
        send_email(fresh, cfg)
    return len(fresh)


def cli() -> None:
    parser = argparse.ArgumentParser(description="Finance Director job search.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--db", default="jobs.db")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print digest to stdout; don't email or mark seen.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run(args.config, args.db, args.dry_run)


if __name__ == "__main__":
    cli()
