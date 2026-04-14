import base64
import json
import time
from pathlib import Path
from typing import Optional, List

import httpx

from rental_lookup.models import Listing

NOBROKER_API = "https://www.nobroker.in/api/v3/multi/property/RENT/filter"
CITY = "bangalore"
RENT_RANGE = "0,70000"
BHK_TYPES = "BHK2,BHK3"

NEIGHBORHOODS = {
    "Indiranagar": {"lat": 12.9716, "lon": 77.6412, "placeId": "ChIJbTDDCWAXujYRZyFs0FD4KFI"},
    "Jayanagar": {"lat": 12.9250, "lon": 77.5938, "placeId": ""},
    "Malleshwaram": {"lat": 12.9963, "lon": 77.5713, "placeId": ""},
    "Basavanagudi": {"lat": 12.9416, "lon": 77.5713, "placeId": ""},
    "Ulsoor": {"lat": 12.9812, "lon": 77.6200, "placeId": ""},
    "Rajajinagar": {"lat": 12.9900, "lon": 77.5525, "placeId": ""},
    "Koramangala": {"lat": 12.9352, "lon": 77.6245, "placeId": ""},
    "HSR Layout": {"lat": 12.9116, "lon": 77.6389, "placeId": ""},
    "BTM Layout": {"lat": 12.9166, "lon": 77.6101, "placeId": ""},
    "Sadashivanagar": {"lat": 13.0070, "lon": 77.5760, "placeId": ""},
    "Frazer Town": {"lat": 12.9980, "lon": 77.6150, "placeId": ""},
    "Shivajinagar": {"lat": 12.9857, "lon": 77.6050, "placeId": ""},
    "JP Nagar": {"lat": 12.9063, "lon": 77.5857, "placeId": ""},
    "Banashankari": {"lat": 12.9255, "lon": 77.5468, "placeId": ""},
    "KR Puram": {"lat": 13.0098, "lon": 77.6960, "placeId": ""},
    "MG Road": {"lat": 12.9756, "lon": 77.6066, "placeId": ""},
    "Whitefield": {"lat": 12.9698, "lon": 77.7500, "placeId": ""},
    "Marathahalli": {"lat": 12.9591, "lon": 77.6974, "placeId": ""},
    "CV Raman Nagar": {"lat": 12.9860, "lon": 77.6680, "placeId": ""},
    "Richmond Town": {"lat": 12.9630, "lon": 77.5980, "placeId": ""},
    "Vasanth Nagar": {"lat": 12.9900, "lon": 77.5920, "placeId": ""},
    "Wilson Garden": {"lat": 12.9430, "lon": 77.5980, "placeId": ""},
    "Domlur": {"lat": 12.9610, "lon": 77.6387, "placeId": ""},
    "Cunningham Road": {"lat": 12.9870, "lon": 77.5920, "placeId": ""},
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
            safe_name = name.lower().replace(' ', '_')
            path = raw_dir / f"{safe_name}_page{page}.json"
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


def load_from_raw(raw_dir: Path) -> List[Listing]:
    """Load listings from previously saved raw JSON files (no network needed)."""
    all_listings = []
    json_files = sorted(raw_dir.glob("*.json"))
    print(f"  Loading {len(json_files)} cached JSON files from {raw_dir}")
    for path in json_files:
        with open(path) as f:
            data = json.load(f)
        all_listings.extend(parse_listings(data))
    deduped = deduplicate(all_listings)
    print(f"  {len(all_listings)} raw, {len(deduped)} after dedup")
    return deduped


def _neighborhood_already_fetched(name: str, raw_dir: Optional[Path]) -> bool:
    """Check if we already have cached JSON for this neighborhood."""
    if not raw_dir or not raw_dir.exists():
        return False
    return any(raw_dir.glob(f"{name.lower().replace(' ', '_')}_page*.json"))


def fetch_all(cookie: str = "", raw_dir: Optional[Path] = None) -> List[Listing]:
    from tqdm import tqdm

    all_listings = []
    to_fetch = {}
    already_cached = {}

    for name, coords in NEIGHBORHOODS.items():
        if _neighborhood_already_fetched(name, raw_dir):
            already_cached[name] = coords
        else:
            to_fetch[name] = coords

    # Load already-cached neighborhoods from disk
    if already_cached and raw_dir:
        print(f"  {len(already_cached)} neighborhoods already cached: {', '.join(already_cached.keys())}")
        cached = load_from_raw(raw_dir)
        all_listings.extend(cached)

    # Fetch only new neighborhoods
    if to_fetch:
        print(f"  Fetching {len(to_fetch)} new neighborhoods: {', '.join(to_fetch.keys())}")
        for name, coords in tqdm(to_fetch.items(), desc="Fetching"):
            print(f"\n  Fetching {name}...")
            listings = fetch_neighborhood(
                name, coords["lat"], coords["lon"], coords.get("placeId", ""),
                cookie=cookie, raw_dir=raw_dir,
            )
            print(f"  Got {len(listings)} listings from {name}")
            all_listings.extend(listings)
    else:
        print("  All neighborhoods cached, nothing to fetch.")

    deduped = deduplicate(all_listings)
    print(f"\nTotal: {len(all_listings)} raw, {len(deduped)} after dedup")
    return deduped
