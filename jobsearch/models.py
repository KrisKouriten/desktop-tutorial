"""Shared data model for job listings across sources."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Job:
    source: str                 # "reed", "adzuna", ...
    source_id: str              # source-native id where available
    title: str
    company: Optional[str]
    location: Optional[str]
    url: str
    description: str = ""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_raw: Optional[str] = None
    posted_at: Optional[datetime] = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    tags: list[str] = field(default_factory=list)

    @property
    def uid(self) -> str:
        """Stable unique id used for dedup across runs."""
        if self.source_id:
            basis = f"{self.source}:{self.source_id}"
        else:
            # fall back to URL hash when the source has no id
            basis = f"{self.source}:{self.url}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

    def salary_top(self) -> Optional[float]:
        """Best available salary figure for filtering."""
        return self.salary_max or self.salary_min
