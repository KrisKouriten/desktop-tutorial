"""
Polling entry point.

Runs a single scan across all configured sources or loops forever at
POLL_INTERVAL_MINUTES. Each listing is scored and upserted into SQLite.

Usage:
    python -m job_search.poller --once        # one pass, then exit
    python -m job_search.poller               # loop at configured interval
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime
from typing import Callable

from . import criteria as C
from . import storage
from .scorer import score as score_listing
from .sources import adzuna, reed, rss

Source = Callable[[], list[dict]]

SOURCES: dict[str, Source] = {
    "reed": reed.fetch,
    "adzuna": adzuna.fetch,
    "rss": rss.fetch,
}


def run_once(verbose: bool = True) -> dict:
    started = datetime.utcnow()
    all_listings: list[dict] = []
    per_source_counts: dict[str, int] = {}

    for name, fn in SOURCES.items():
        try:
            batch = fn() or []
        except Exception as exc:
            print(f"[{name}] source failed: {exc}")
            batch = []
        per_source_counts[name] = len(batch)
        all_listings.extend(batch)

    for li in all_listings:
        s, reasons = score_listing(li)
        li["score"] = s
        li["match_reasons"] = "; ".join(reasons)

    new, updated = storage.upsert_listings(all_listings)
    elapsed = (datetime.utcnow() - started).total_seconds()

    if verbose:
        print(
            f"[{started.isoformat(timespec='seconds')}Z] "
            f"scanned {len(all_listings)} listings across {len(SOURCES)} sources "
            f"→ {new} new, {updated} updated "
            f"(in {elapsed:.1f}s)"
        )
        for src, n in per_source_counts.items():
            print(f"    {src}: {n}")

    return {
        "new": new,
        "updated": updated,
        "total": len(all_listings),
        "per_source": per_source_counts,
        "elapsed_s": elapsed,
    }


def run_forever() -> None:
    interval = max(1, C.POLL_INTERVAL_MINUTES) * 60
    print(f"Polling every {C.POLL_INTERVAL_MINUTES} minute(s). Ctrl-C to stop.")
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            print("Stopping.")
            return
        except Exception as exc:
            print(f"poll iteration failed: {exc}")
        time.sleep(interval)


def main() -> None:
    ap = argparse.ArgumentParser(description="Poll job sources and update the local store.")
    ap.add_argument("--once", action="store_true", help="Run a single pass then exit.")
    args = ap.parse_args()

    if args.once:
        run_once()
    else:
        run_forever()


if __name__ == "__main__":
    main()
