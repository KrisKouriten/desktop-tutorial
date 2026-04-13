"""Load config.yaml + .env into typed structures."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class LocationSpec:
    name: str
    adzuna_where: str
    reed_location: str
    reed_distance: int = 15


@dataclass
class Config:
    titles_any: list[str]
    titles_exclude: list[str]
    locations: list[LocationSpec]
    min_salary_gbp: float
    strict_salary: bool
    require_hybrid_or_remote: bool
    hybrid_remote_terms: list[str]
    subject_prefix: str
    max_jobs_per_email: int
    skip_if_empty: bool
    sources: dict[str, bool]
    raw: dict[str, Any] = field(default_factory=dict)


def load_config(path: str | Path = "config.yaml") -> Config:
    path = Path(path)
    with path.open() as f:
        data = yaml.safe_load(f)

    locations = [LocationSpec(**loc) for loc in data.get("locations", [])]

    return Config(
        titles_any=[t.lower() for t in data["keywords"]["titles_any"]],
        titles_exclude=[t.lower() for t in data["keywords"].get("titles_exclude", [])],
        locations=locations,
        min_salary_gbp=float(data["filters"]["min_salary_gbp"]),
        strict_salary=bool(data["filters"].get("strict_salary", False)),
        require_hybrid_or_remote=bool(data["filters"].get("require_hybrid_or_remote", False)),
        hybrid_remote_terms=[t.lower() for t in data["filters"].get("hybrid_remote_terms", [])],
        subject_prefix=data["notify"].get("subject_prefix", "[FD Jobs]"),
        max_jobs_per_email=int(data["notify"].get("max_jobs_per_email", 50)),
        skip_if_empty=bool(data["notify"].get("skip_if_empty", True)),
        sources={k: bool(v) for k, v in data.get("sources", {}).items()},
        raw=data,
    )


def load_env(path: str | Path = ".env") -> None:
    """Load .env if present; environment variables always win."""
    p = Path(path)
    if p.exists():
        load_dotenv(p)


def env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name)
    return val if val else default
