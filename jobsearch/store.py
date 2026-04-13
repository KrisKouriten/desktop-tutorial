"""SQLite-backed store: remembers every job UID we've seen so we only email new ones."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import Job


SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    uid         TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    title       TEXT,
    company     TEXT,
    url         TEXT,
    first_seen  TEXT NOT NULL,
    payload     TEXT
);
CREATE INDEX IF NOT EXISTS idx_seen_source ON seen_jobs(source);
"""


class JobStore:
    def __init__(self, path: str | Path = "jobs.db"):
        self.path = Path(path)
        with closing(sqlite3.connect(self.path)) as c:
            c.executescript(SCHEMA)
            c.commit()

    def filter_new(self, jobs: Iterable[Job]) -> list[Job]:
        """Return only jobs whose UID we haven't stored before."""
        jobs = list(jobs)
        if not jobs:
            return []
        uids = [j.uid for j in jobs]
        with closing(sqlite3.connect(self.path)) as c:
            placeholders = ",".join("?" * len(uids))
            rows = c.execute(
                f"SELECT uid FROM seen_jobs WHERE uid IN ({placeholders})", uids
            ).fetchall()
        seen = {r[0] for r in rows}
        return [j for j in jobs if j.uid not in seen]

    def mark_seen(self, jobs: Iterable[Job]) -> None:
        now = datetime.utcnow().isoformat()
        rows = [
            (
                j.uid,
                j.source,
                j.title,
                j.company or "",
                j.url,
                now,
                json.dumps(
                    {
                        "location": j.location,
                        "salary_raw": j.salary_raw,
                        "salary_min": j.salary_min,
                        "salary_max": j.salary_max,
                        "tags": j.tags,
                    }
                ),
            )
            for j in jobs
        ]
        with closing(sqlite3.connect(self.path)) as c:
            c.executemany(
                "INSERT OR IGNORE INTO seen_jobs "
                "(uid, source, title, company, url, first_seen, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            c.commit()
