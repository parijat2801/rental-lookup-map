import base64
import json
import time
from pathlib import Path
from typing import Optional, List

import httpx

from rental_lookup.models import Listing

NOBROKER_API = "https://www.nobroker.in/api/v3/multi/property/RENT/filter"
CITY = "bangalore"
RENT_RANGE = "0,60000"
BHK_TYPES = "BHK2,BHK3"

NEIGHBORHOODS = {
    "Indiranagar": {"lat": 12.9716, "lon": 77.6412, "placeId": "ChIJbTDDCWAXujYRZyFs0FD4KFI"},
    "Jayanagar": {"lat": 12.9250, "lon": 77.5938, "placeId": ""},
    "Malleshwaram": {"lat": 12.9963, "lon": 77.5713, "placeId": ""},
    "Basavanagudi": {"lat": 12.9416, "lon": 77.5713, "placeId": ""},
    "Ulsoor": {"lat": 12.9812, "lon": 77.6200, "placeId": ""},
    "Rajajinagar": {"lat": 12.9900, "lon": 77.5525, "placeId": ""},
}


def make_search_param(name: str, lat: float, lon: float, place_id: str = "") -> str:
    payload = [{"lat": lat, "lon": lon, "placeId": place_id, "placeName": name}]
    return base64.b64encode(json.dumps(payload).encode()).decode()


def parse_listings(response: dict) -> List[Listing]:
    if response.get("status") != "success":
        return []
    listings = []
    for raw in response.get("data", []):
        listing = Listing.from_nobroker(raw)
        if listing is not None:
            listings.append(listing)
    return listings


def deduplicate(listings: List[Listing]) -> List[Listing]:
    seen = set()
    result = []
    for listing in listings:
        if listing.id not in seen:
            seen.add(listing.id)
            result.append(listing)
    return result


def fetch_neighborhood(
    name: str, lat: float, lon: float, place_id: str = "",
    cookie: str = "",
    raw_dir: Optional[Path] = None,
) -> List[Listing]:
    search_param = make_search_param(name, lat, lon, place_id)
    all_listings = []
    page = 1

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    if cookie:
        headers["Cookie"] = cookie

    while True:
        params = {
            "city": CITY,
            "pageNo": str(page),
            "searchParam": search_param,
            "rent": RENT_RANGE,
            "type": BHK_TYPES,
        }
        try:
            resp = httpx.get(NOBROKER_API, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [!] Error fetching {name} page {page}: {e}")
            break

        if raw_dir:
            raw_dir.mkdir(parents=True, exist_ok=True)
            path = raw_dir / f"{name.lower()}_page{page}.json"
            path.write_text(json.dumps(data, indent=2))

        # Stop when raw data is empty (not when parsed is empty)
        raw_data = data.get("data", [])
        if not raw_data:
            break

        page_listings = parse_listings(data)
        all_listings.extend(page_listings)
        page += 1
        time.sleep(1)

    return all_listings


def fetch_all(cookie: str = "", raw_dir: Optional[Path] = None) -> List[Listing]:
    from tqdm import tqdm

    all_listings = []
    for name, coords in tqdm(NEIGHBORHOODS.items(), desc="Fetching neighborhoods"):
        print(f"\n  Fetching {name}...")
        listings = fetch_neighborhood(
            name, coords["lat"], coords["lon"], coords.get("placeId", ""),
            cookie=cookie, raw_dir=raw_dir,
        )
        print(f"  Got {len(listings)} listings from {name}")
        all_listings.extend(listings)

    deduped = deduplicate(all_listings)
    print(f"\nTotal: {len(all_listings)} raw, {len(deduped)} after dedup")
    return deduped
