"""Fetch NoBroker detail pages for extras the search results lack.

Two passes, both cached in data/cache and merged into the map by the webmap builder:
  - details (maintenance, description, ...) for the top listings -> nobroker_detail_enrichment.json
  - transit / lifestyle ratings for listings whose search result had none -> nobroker_platform_scores.json

Run: python -m rental_lookup.enrichment.listing_details [TOP_N]
     python -m rental_lookup.enrichment.listing_details scores [LIMIT]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

import httpx

from rental_lookup.paths import LISTING_DETAILS_PATH, NOBROKER_PAGES_DIR, PLATFORM_SCORES_PATH
from rental_lookup.sources.nobroker import REQUEST_HEADERS, follow_up_priority, iter_saved_listings

DETAIL_API = "https://www.nobroker.in/api/v3/property/{id}?hopId=public"
RENT_RANGE = (25000, 80000)
MIN_SQFT = 500
CHECKPOINT_EVERY = 50


def _worth_fetching(raw: dict) -> bool:
    low, high = RENT_RANGE
    return (low <= (raw.get("rent") or 0) <= high
            and (raw.get("propertySize") or 0) >= MIN_SQFT
            and bool(raw.get("latitude")) and bool(raw.get("longitude")))


def _fields_used_by_map(detail: dict) -> dict:
    """The subset of the detail payload that the webmap builder uses."""
    return {
        "maintenanceAmount": detail.get("maintenanceAmount"),
        "maintenance": detail.get("maintenance"),
        "description": (detail.get("description") or "")[:500],
        "cupBoard": detail.get("cupBoard"),
        "completeStreetName": detail.get("completeStreetName", ""),
        "availableFrom": detail.get("formattedAvailableFrom", ""),
        "propertyCode": detail.get("propertyCode", ""),
        "buildingName": detail.get("buildingName") or "",
        "latitude": detail.get("latitude"),
        "longitude": detail.get("longitude"),
    }


def platform_scores_from_detail(detail: dict) -> Optional[list]:
    """[transit, lifestyle] from a detail payload, or None when NoBroker has no ratings."""
    scores = detail.get("score")
    if not isinstance(scores, dict) or scores.get("transit") is None or scores.get("lifestyle") is None:
        return None
    return [scores["transit"], scores["lifestyle"]]


def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _save_cache(path: Path, cache: dict, indent: Optional[int] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=indent))


def _fetch_details(ids: list[str], on_detail: Callable[[str, dict], None], checkpoint: Callable[[], None]) -> None:
    """Call on_detail(id, payload) for each listing's detail page, about one request per second."""
    with httpx.Client(headers=REQUEST_HEADERS, timeout=10) as client:
        for fetched_count, listing_id in enumerate(ids, 1):
            try:
                response = client.get(DETAIL_API.format(id=listing_id)).json()
                if response.get("status") == "success":
                    on_detail(listing_id, response["data"])
            except (httpx.HTTPError, ValueError, KeyError, AttributeError):
                pass  # best effort: a missing detail just means no extras on the map
            if fetched_count % CHECKPOINT_EVERY == 0:
                print(f"  {fetched_count}/{len(ids)}")
                checkpoint()  # so an interrupted run isn't lost
            time.sleep(1)
    checkpoint()


def _by_priority(listings: Iterable[dict]) -> list[dict]:
    return sorted(listings, key=lambda raw: -follow_up_priority(raw))


def fetch_details_for_top_listings(top_n: int = 300) -> None:
    candidates = _by_priority(raw for raw in iter_saved_listings(NOBROKER_PAGES_DIR) if _worth_fetching(raw))
    details = _load_cache(LISTING_DETAILS_PATH)
    scores = _load_cache(PLATFORM_SCORES_PATH)
    ids_to_fetch = [raw["id"] for raw in candidates[:top_n] if raw["id"] not in details]
    print(f"Top {top_n}: {len(ids_to_fetch)} need enrichment ({len(details)} already cached)")

    def on_detail(listing_id: str, detail: dict) -> None:
        details[listing_id] = _fields_used_by_map(detail)
        scores[listing_id] = platform_scores_from_detail(detail)

    def checkpoint() -> None:
        _save_cache(LISTING_DETAILS_PATH, details, indent=2)
        _save_cache(PLATFORM_SCORES_PATH, scores)

    _fetch_details(ids_to_fetch, on_detail, checkpoint)
    print(f"Enrichment cache: {len(details)} listings")


def fetch_missing_platform_scores(limit: Optional[int] = None) -> None:
    """Ratings for listings whose search result had none, best listings first."""
    scores = _load_cache(PLATFORM_SCORES_PATH)
    missing = _by_priority(raw for raw in iter_saved_listings(NOBROKER_PAGES_DIR)
                           if not isinstance(raw.get("score"), dict) and raw["id"] not in scores)
    ids_to_fetch = [raw["id"] for raw in missing[:limit]]
    print(f"Ratings: {len(ids_to_fetch)} listings to look up ({len(scores)} already cached)")

    def on_detail(listing_id: str, detail: dict) -> None:
        scores[listing_id] = platform_scores_from_detail(detail)

    _fetch_details(ids_to_fetch, on_detail, lambda: _save_cache(PLATFORM_SCORES_PATH, scores))
    found = sum(1 for listing_id in ids_to_fetch if scores.get(listing_id))
    print(f"Ratings found for {found}/{len(ids_to_fetch)}; cache: {len(scores)} listings")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "scores":
        fetch_missing_platform_scores(int(args[1]) if len(args) > 1 else None)
    else:
        fetch_details_for_top_listings(int(args[0]) if args else 300)
