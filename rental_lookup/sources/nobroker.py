"""NoBroker: fetch rental search results and work with the saved raw pages."""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Iterator, Optional

import httpx

from rental_lookup.models import CAR_PARKING_TYPES, Listing, mentions_branded_builder, nobroker_platform_scores

SEARCH_API = "https://www.nobroker.in/api/v3/multi/property/RENT/filter"
PHOTO_CDN = "https://assets.nobroker.in/images"
CITY = "bangalore"
RENT_RANGE = "0,150000"
BHK_TYPES = "BHK1,BHK2,BHK3"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Search anchors. NoBroker returns listings within a radius of each point, so
# neighbouring anchors overlap; results are de-duplicated by listing id.
NEIGHBORHOODS = {
    "Indiranagar": {"lat": 12.9716, "lon": 77.6412, "placeId": "ChIJbTDDCWAXujYRZyFs0FD4KFI"},
    "Jayanagar": {"lat": 12.9250, "lon": 77.5938},
    "Malleshwaram": {"lat": 12.9963, "lon": 77.5713},
    "Basavanagudi": {"lat": 12.9416, "lon": 77.5713},
    "Ulsoor": {"lat": 12.9812, "lon": 77.6200},
    "Rajajinagar": {"lat": 12.9900, "lon": 77.5525},
    "Koramangala": {"lat": 12.9352, "lon": 77.6245},
    "HSR Layout": {"lat": 12.9116, "lon": 77.6389},
    "BTM Layout": {"lat": 12.9166, "lon": 77.6101},
    "Sadashivanagar": {"lat": 13.0070, "lon": 77.5760},
    "Frazer Town": {"lat": 12.9980, "lon": 77.6150},
    "Shivajinagar": {"lat": 12.9857, "lon": 77.6050},
    "JP Nagar": {"lat": 12.9063, "lon": 77.5857},
    "Banashankari": {"lat": 12.9255, "lon": 77.5468},
    "KR Puram": {"lat": 13.0098, "lon": 77.6960},
    "MG Road": {"lat": 12.9756, "lon": 77.6066},
    "Whitefield": {"lat": 12.9698, "lon": 77.7500},
    "Marathahalli": {"lat": 12.9591, "lon": 77.6974},
    "CV Raman Nagar": {"lat": 12.9860, "lon": 77.6680},
    "Richmond Town": {"lat": 12.9630, "lon": 77.5980},
    "Vasanth Nagar": {"lat": 12.9900, "lon": 77.5920},
    "Wilson Garden": {"lat": 12.9430, "lon": 77.5980},
    "Domlur": {"lat": 12.9610, "lon": 77.6387},
    "Cunningham Road": {"lat": 12.9870, "lon": 77.5920},
    "Jayamahal": {"lat": 13.0000, "lon": 77.5920},
    "Langford Town": {"lat": 12.9550, "lon": 77.5950},
    "Lalbagh": {"lat": 12.9507, "lon": 77.5848},
    "Hombegowda Nagar": {"lat": 12.9400, "lon": 77.6050},
    # Purple Line corridor east of Indiranagar (Baiyappanahalli -> Kadugodi).
    # Anchors sit on locality centroids, not stations, so each covers 2-3 stops.
    "Baiyappanahalli": {"lat": 12.9908, "lon": 77.6524},
    "Hoodi": {"lat": 12.9925, "lon": 77.7130},
    "Kundalahalli": {"lat": 12.9790, "lon": 77.7160},
    "Brookefield": {"lat": 12.9660, "lon": 77.7170},
    "Nallurhalli": {"lat": 12.9760, "lon": 77.7280},
    "Kadugodi": {"lat": 12.9955, "lon": 77.7690},
}


# --- Working with raw listings (dicts exactly as the API returns them) ----------

def encode_search_anchor(name: str, lat: float, lon: float, place_id: str = "") -> str:
    """NoBroker's `searchParam` is base64-encoded JSON describing the search anchor."""
    payload = [{"lat": lat, "lon": lon, "placeId": place_id, "placeName": name}]
    return base64.b64encode(json.dumps(payload).encode()).decode()


def iter_saved_listings(pages_dir: Path) -> Iterator[dict]:
    """Yield each raw listing from saved result pages, once per listing id."""
    seen_ids = set()
    for page_path in sorted(Path(pages_dir).glob("*.json")):
        with open(page_path) as f:
            page = json.load(f)
        for raw in page.get("data") or []:
            if raw.get("id") and raw["id"] not in seen_ids:
                seen_ids.add(raw["id"])
                yield raw


def photo_urls(raw: dict, max_photos: int = 5) -> list[str]:
    """CDN URLs (medium size, ~18KB each) for a raw listing's photos."""
    urls = []
    for photo in (raw.get("photos") or [])[:max_photos]:
        if isinstance(photo, dict):
            sizes = photo.get("imagesMap") or {}
            filename = sizes.get("medium") or sizes.get("large")
            if filename:
                urls.append(f"{PHOTO_CDN}/{raw['id']}/{filename}")
    return urls


def has_real_photo(raw: dict) -> bool:
    """NoBroker substitutes a placeholder from /static/img/ when there are no photos."""
    image_url = raw.get("originalImageUrl") or ""
    return bool(image_url) and "static/img" not in image_url


def follow_up_priority(raw: dict, reward_many_photos: bool = True) -> int:
    """Cheap desirability score used to choose which listings get the expensive
    follow-ups (detail-page fetch, AI photo rating). Higher = sooner.

    `reward_many_photos` adds +5 for 10+ photos (instead of +3 for 5+).
    """
    amenities = raw.get("amenitiesMap") or {}
    points = 0
    if (raw.get("facing") or "") in ("E", "SE", "S", "NE"):
        points += 10
    points += min((raw.get("balconies") or 0) * 4, 12)
    age_years = raw.get("propertyAge")
    age_years = 99 if age_years is None else age_years
    points += 10 if age_years <= 3 else 7 if age_years <= 7 else 3 if age_years <= 15 else 0
    for amenity, amenity_points in (("PB", 5), ("SECURITY", 5), ("GP", 4), ("POOL", 8), ("GYM", 5), ("CLUB", 5)):
        if amenities.get(amenity):
            points += amenity_points
    if raw.get("parking") in CAR_PARKING_TYPES:
        points += 5
    transit_score, lifestyle_score = nobroker_platform_scores(raw)
    points += 5 if transit_score >= 8 else 3 if transit_score >= 7 else 0
    points += 8 if lifestyle_score >= 8 else 4 if lifestyle_score >= 6 else 0
    if raw.get("negotiable"):
        points += 3
    photo_count = len(raw.get("photos") or [])
    if reward_many_photos and photo_count >= 10:
        points += 5
    elif photo_count >= 5:
        points += 3
    if mentions_branded_builder(f"{raw.get('society') or ''} {raw.get('propertyTitle') or ''}"):
        points += 8
    return points


# --- Parsing ----------------------------------------------------------------

def parse_listings(page: dict) -> list[Listing]:
    """Convert one API results page into Listings, skipping items without coordinates."""
    if page.get("status") != "success":
        return []
    listings = (Listing.from_nobroker(raw) for raw in page.get("data") or [])
    return [listing for listing in listings if listing is not None]


def dedupe_by_id(listings: list[Listing]) -> list[Listing]:
    """Keep the first occurrence of each listing id, preserving order."""
    seen_ids, unique = set(), []
    for listing in listings:
        if listing.id not in seen_ids:
            seen_ids.add(listing.id)
            unique.append(listing)
    return unique


# --- Fetching ---------------------------------------------------------------

def _page_file_prefix(neighborhood: str) -> str:
    return neighborhood.lower().replace(" ", "_")


def fetch_neighborhood(
    name: str, lat: float, lon: float, place_id: str = "",
    cookie: str = "",
    pages_dir: Optional[Path] = None,
) -> list[Listing]:
    """Page through all results around one anchor, optionally saving each raw page."""
    params = {
        "city": CITY,
        "searchParam": encode_search_anchor(name, lat, lon, place_id),
        "rent": RENT_RANGE,
        "type": BHK_TYPES,
    }
    headers = {**REQUEST_HEADERS, **({"Cookie": cookie} if cookie else {})}
    listings: list[Listing] = []

    with httpx.Client(headers=headers, timeout=15) as client:
        page_number = 1
        while True:
            try:
                response = client.get(SEARCH_API, params={**params, "pageNo": str(page_number)})
                response.raise_for_status()
                page = response.json()
            except (httpx.HTTPError, ValueError) as e:
                print(f"  [!] Error fetching {name} page {page_number}: {e}")
                break

            if pages_dir:
                pages_dir.mkdir(parents=True, exist_ok=True)
                page_path = pages_dir / f"{_page_file_prefix(name)}_page{page_number}.json"
                page_path.write_text(json.dumps(page, indent=2))

            # Stop on an empty raw page (not an empty parsed page: items may lack coords).
            if not page.get("data"):
                break

            listings.extend(parse_listings(page))
            page_number += 1
            time.sleep(1)

    return listings


def load_saved_listings(pages_dir: Path) -> list[Listing]:
    """Parse previously saved result pages (no network needed)."""
    page_paths = sorted(pages_dir.glob("*.json"))
    print(f"  Loading {len(page_paths)} cached JSON files from {pages_dir}")
    listings = []
    for page_path in page_paths:
        with open(page_path) as f:
            listings.extend(parse_listings(json.load(f)))
    unique = dedupe_by_id(listings)
    print(f"  {len(listings)} raw, {len(unique)} after dedup")
    return unique


def _already_fetched(neighborhood: str, pages_dir: Optional[Path]) -> bool:
    return (bool(pages_dir) and pages_dir.exists()
            and any(pages_dir.glob(f"{_page_file_prefix(neighborhood)}_page*.json")))


def fetch_all(cookie: str = "", pages_dir: Optional[Path] = None) -> list[Listing]:
    """Fetch every neighbourhood, reusing any already saved under `pages_dir`.

    To force a fresh fetch, empty `pages_dir` first (refresh_map.sh and CI do this).
    """
    from tqdm import tqdm

    already_saved = [name for name in NEIGHBORHOODS if _already_fetched(name, pages_dir)]
    to_fetch = [name for name in NEIGHBORHOODS if name not in already_saved]
    listings: list[Listing] = []

    if already_saved:
        print(f"  {len(already_saved)} neighborhoods already cached: {', '.join(already_saved)}")
        listings.extend(load_saved_listings(pages_dir))

    if to_fetch:
        print(f"  Fetching {len(to_fetch)} new neighborhoods: {', '.join(to_fetch)}")
        for name in tqdm(to_fetch, desc="Fetching"):
            anchor = NEIGHBORHOODS[name]
            print(f"\n  Fetching {name}...")
            found = fetch_neighborhood(name, anchor["lat"], anchor["lon"], anchor.get("placeId", ""),
                                       cookie=cookie, pages_dir=pages_dir)
            print(f"  Got {len(found)} listings from {name}")
            listings.extend(found)
    else:
        print("  All neighborhoods cached, nothing to fetch.")

    unique = dedupe_by_id(listings)
    print(f"\nTotal: {len(listings)} raw, {len(unique)} after dedup")
    return unique
