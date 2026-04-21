"""
SQLite storage for job listings. Small, single-user, file-based — no
daemon or server needed. The poller calls upsert_listings() and the
Streamlit dashboard reads via load_listings().
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, Iterator

DB_PATH = os.environ.get("JOB_DB_PATH", "data/jobs.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    external_id        TEXT PRIMARY KEY,
    source             TEXT NOT NULL,
    title              TEXT NOT NULL,
    company            TEXT,
    location           TEXT,
    description        TEXT,
    url                TEXT,
    salary_min         REAL,
    salary_max         REAL,
    salary_is_day_rate INTEGER DEFAULT 0,
    contract_type      TEXT,
    posted_at          TEXT,
    first_seen_at      TEXT NOT NULL,
    last_seen_at       TEXT NOT NULL,
    score              REAL DEFAULT 0,
    match_reasons      TEXT,
    status             TEXT DEFAULT 'new',      -- new | seen | shortlist | hidden
    notes              TEXT
);

CREATE INDEX IF NOT EXISTS idx_listings_first_seen ON listings(first_seen_at);
CREATE INDEX IF NOT EXISTS idx_listings_score      ON listings(score);
CREATE INDEX IF NOT EXISTS idx_listings_status     ON listings(status);
"""


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript(SCHEMA)


def upsert_listings(listings: Iterable[dict]) -> tuple[int, int]:
    """Insert new listings, update last_seen_at for known ones. Returns (new, updated)."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0
    updated_count = 0
    with _conn() as con:
        for li in listings:
            row = con.execute(
                "SELECT external_id FROM listings WHERE external_id = ?",
                (li["external_id"],),
            ).fetchone()
            if row is None:
                con.execute(
                    """
                    INSERT INTO listings (
                        external_id, source, title, company, location, description,
                        url, salary_min, salary_max, salary_is_day_rate, contract_type,
                        posted_at, first_seen_at, last_seen_at, score, match_reasons
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        li["external_id"], li["source"], li["title"], li.get("company"),
                        li.get("location"), li.get("description"), li.get("url"),
                        li.get("salary_min"), li.get("salary_max"),
                        1 if li.get("salary_is_day_rate") else 0,
                        li.get("contract_type"), li.get("posted_at"),
                        now, now,
                        li.get("score", 0), li.get("match_reasons", ""),
                    ),
                )
                new_count += 1
            else:
                con.execute(
                    """
                    UPDATE listings
                       SET last_seen_at = ?,
                           score = ?,
                           match_reasons = ?
                     WHERE external_id = ?
                    """,
                    (now, li.get("score", 0), li.get("match_reasons", ""), li["external_id"]),
                )
                updated_count += 1
    return new_count, updated_count


def load_listings(
    min_score: float | None = None,
    status: str | None = None,
    limit: int = 500,
) -> list[dict]:
    init_db()
    sql = "SELECT * FROM listings WHERE 1=1"
    args: list = []
    if min_score is not None:
        sql += " AND score >= ?"
        args.append(min_score)
    if status is not None:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY COALESCE(posted_at, first_seen_at) DESC LIMIT ?"
    args.append(limit)
    with _conn() as con:
        rows = con.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def set_status(external_id: str, status: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE listings SET status = ? WHERE external_id = ?",
            (status, external_id),
        )


def set_notes(external_id: str, notes: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE listings SET notes = ? WHERE external_id = ?",
            (notes, external_id),
        )
