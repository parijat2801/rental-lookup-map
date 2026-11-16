"""HTTP helper shared by the listing sources."""
from __future__ import annotations

import time

import httpx

RETRY_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 2.0


def get_json(client: httpx.Client, url: str, params: dict,
             attempts: int = RETRY_ATTEMPTS, backoff: float = RETRY_BACKOFF_SECONDS) -> dict:
    """GET `url` and parse JSON, retrying with exponential backoff.

    Pagination stops at the first page that can't be fetched, so a single
    transient error would otherwise silently truncate a whole search.
    Raises the last error once every attempt has failed.
    """
    for attempt in range(1, attempts + 1):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            if attempt == attempts:
                raise
            time.sleep(backoff * 2 ** (attempt - 1))
    raise AssertionError("unreachable")
