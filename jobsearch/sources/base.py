"""Shared helpers for source adapters."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests


log = logging.getLogger(__name__)


class SourceError(RuntimeError):
    """A source couldn't complete. Logged but doesn't abort the whole run."""


def http_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    auth: tuple[str, str] | None = None,
    timeout: int = 20,
    retries: int = 2,
) -> requests.Response:
    """GET with small retry loop for transient failures."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=headers,
                             auth=auth, timeout=timeout)
            if r.status_code >= 500:
                raise SourceError(f"{url} -> HTTP {r.status_code}")
            return r
        except (requests.RequestException, SourceError) as e:
            last = e
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise SourceError(f"GET failed for {url}: {last}")


def http_post(
    url: str,
    *,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
    retries: int = 2,
) -> requests.Response:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, json=json, headers=headers, timeout=timeout)
            if r.status_code >= 500:
                raise SourceError(f"{url} -> HTTP {r.status_code}")
            return r
        except (requests.RequestException, SourceError) as e:
            last = e
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise SourceError(f"POST failed for {url}: {last}")
