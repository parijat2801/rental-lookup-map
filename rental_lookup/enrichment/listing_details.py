"""Fetch NoBroker detail pages (maintenance, description, ...) for the top listings.

Results are cached in data/cache/detail_enrichment.json and merged into the map
by the webmap builder. Run: python -m rental_lookup.enrichment.listing_details [TOP_N]
"""
from __future__ import annotations

import json
import sys
import time

import httpx

from rental_lookup.paths import LISTING_DETAILS_PATH, NOBROKER_PAGES_DIR
from rental_lookup.sources.nobroker import REQUEST_HEADERS, follow_up_priority, iter_saved_listings

DETAIL_API = "https://www.nobroker.in/api/v3/property/{id}?hopId=public"
RENT_RANGE = (25000, 80000)
MIN_SQFT = 500


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
        "latitude": detail.get("latitude"),
        "longitude": detail.get("longitude"),
    }


def _load_saved_details() -> dict:
    try:
        return json.loads(LISTING_DETAILS_PATH.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _save_details(details: dict) -> None:
    LISTING_DETAILS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LISTING_DETAILS_PATH.write_text(json.dumps(details, indent=2))


def fetch_details_for_top_listings(top_n: int = 300) -> None:
    candidates = [raw for raw in iter_saved_listings(NOBROKER_PAGES_DIR) if _worth_fetching(raw)]
    candidates.sort(key=lambda raw: -follow_up_priority(raw))
    details = _load_saved_details()
    ids_to_fetch = [raw["id"] for raw in candidates[:top_n] if raw["id"] not in details]
    print(f"Top {top_n}: {len(ids_to_fetch)} need enrichment ({len(details)} already cached)")

    with httpx.Client(headers=REQUEST_HEADERS, timeout=10) as client:
        for fetched_count, listing_id in enumerate(ids_to_fetch, 1):
            try:
                response = client.get(DETAIL_API.format(id=listing_id)).json()
                if response.get("status") == "success":
                    details[listing_id] = _fields_used_by_map(response["data"])
            except (httpx.HTTPError, ValueError, KeyError, AttributeError):
                pass  # best effort: a missing detail just means no extras on the map
            if fetched_count % 50 == 0:
                print(f"  {fetched_count}/{len(ids_to_fetch)}")
                _save_details(details)  # checkpoint so an interrupted run isn't lost
            time.sleep(1)

    _save_details(details)
    print(f"Enrichment cache: {len(details)} listings")


if __name__ == "__main__":
    fetch_details_for_top_listings(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
