"""MagicBricks: fetch rental listings and normalise them to `Listing`.

API: GET https://www.magicbricks.com/mbsrp/propertySearch.html (JSON, no auth).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Iterator, Optional

import httpx

from rental_lookup.models import CAR_PARKING_TYPES, Listing
from rental_lookup.sources.http import get_json

SEARCH_API = "https://www.magicbricks.com/mbsrp/propertySearch.html"
CITY = "Bangalore"
BHK_TYPES = "1,2,3"
# Property types: 10002=Apartment, 10003=Builder Floor, 10021=Penthouse, 10022=Studio
PROPERTY_TYPES = "10002,10003,10021,10022"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# `amenities` is a space-separated list of numeric codes (approximate mapping).
AMENITY_CODES = {
    "lift": "12201", "security": "12202", "playground": "12203", "gym": "12204",
    "pool": "12205", "club": "12206", "power_backup": "12207", "gas_pipeline": "12208",
    "park": "12209", "intercom": "12214", "ac": "12215", "fire_safety": "12218",
    "laundry": "12220",
}

FACING_CODES = {
    "East": "E", "West": "W", "North": "N", "South": "S",
    "North-East": "NE", "North-West": "NW", "South-East": "SE", "South-West": "SW",
}
GROUND_FLOOR_LABELS = ("ground", "g", "lower basement", "upper basement")
# `acD` age labels -> representative age in years. Numbers must match whole, so
# "10 to 15 years" doesn't match "0 to 1".
AGE_LABELS = tuple((re.compile(rf"(?<!\d){label}(?!\d)"), years) for label, years in (
    ("new construction", 1), ("0 to 1", 1), ("less than 5", 3), ("1 to 5", 3), ("5 to 10", 7),
))


# --- Field parsers ----------------------------------------------------------

def parse_int(value, default: int = 0) -> int:
    """Lenient int(): accepts ints, floats and numeric strings; else `default`."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _parse_float(value) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def amenity_names(raw: dict) -> set[str]:
    """Names (keys of AMENITY_CODES) of the amenities a listing advertises."""
    codes = set(re.findall(r"\d+", str(raw.get("amenities") or "")))
    return {name for name, code in AMENITY_CODES.items() if code in codes}


def parse_coords(raw: dict) -> Optional[tuple[float, float]]:
    """Property coordinates, falling back to the locality centroid (`ltcoordGeo`).

    The centroid is shared by every listing in a locality, so it causes stacking.
    """
    lat, lng = _parse_float(raw.get("pmtLat")), _parse_float(raw.get("pmtLong"))
    if not (lat and lng):
        parts = str(raw.get("ltcoordGeo") or "").split(",")
        if len(parts) >= 2:
            lat, lng = _parse_float(parts[0]), _parse_float(parts[1])
    return (lat, lng) if lat and lng else None


def _parse_bhk(raw: dict) -> str:
    # Leading digit only, so e.g. "43" -> BHK4 rather than a substring match on "3".
    match = re.search(r"\d", str(raw.get("bedroomD") or ""))
    return f"BHK{match.group()}" if match and match.group() != "0" else ""


def _parse_floor(raw: dict) -> int:
    floor = raw.get("floorNo")
    return 0 if str(floor).lower() in GROUND_FLOOR_LABELS else parse_int(floor)


def _parse_facing(raw: dict) -> str:
    # Labels arrive as both "North-East" and "North - East".
    return FACING_CODES.get(re.sub(r"\s+", "", str(raw.get("facingD") or "")), "")


def _parse_parking(raw: dict) -> str:
    """Map parking label; "" when the field is absent (unknown)."""
    if raw.get("parkingD") is None:
        return ""
    text = str(raw.get("parkingD") or "")
    if "Covered" in text or "Car" in text:
        return "FOUR_WHEELER"
    if "Bike" in text or "Two" in text:
        return "TWO_WHEELER"
    return "BOTH" if text and text != "None" else "NONE"


def _parse_balconies(raw: dict) -> int:
    """Balcony count; -1 when the field is absent (unknown)."""
    if raw.get("balconiesD") is None:
        return -1
    return parse_int(raw.get("balconiesD"))


def _parse_has_lift(raw: dict, amenities: set[str]) -> Optional[bool]:
    """True/False when amenities are listed; None when amenities are absent."""
    if raw.get("amenities") in (None, ""):
        return None
    return "lift" in amenities


def _parse_age_years(raw: dict) -> int:
    label = str(raw.get("acD") or "").lower()
    for pattern, years in AGE_LABELS:
        if pattern.search(label):
            return years
    if any(int(number) >= 10 for number in re.findall(r"\d+", label)):
        return 15
    return 99


def _parse_water_supply(raw: dict) -> str:
    text = str(raw.get("waterStatus") or "")
    if "24" in text:
        return "CORPORATION"
    return "BOREWELL" if "Borewell" in text else ""


def photo_urls(raw: dict, max_photos: int = 10) -> list[str]:
    paths = raw.get("allImgPath")
    return [p for p in paths[:max_photos] if isinstance(p, str)] if isinstance(paths, list) else []


def listing_id(raw: dict) -> str:
    """Prefixed with 'mb_' so ids never collide with NoBroker's."""
    return f"mb_{raw.get('id', '')}"


# --- Normalisation ----------------------------------------------------------

def normalize_listing(raw: dict) -> Optional[Listing]:
    """Convert a raw MagicBricks listing to a Listing; None if unusable."""
    coords = parse_coords(raw)
    rent = parse_int(raw.get("price"))
    if not coords or rent <= 0:
        return None

    lat, lng = coords
    amenities = amenity_names(raw)
    parking = _parse_parking(raw)
    photos = photo_urls(raw, max_photos=1)
    url_path = raw.get("url") or ""

    return Listing(
        id=listing_id(raw),
        rent=rent,
        deposit=parse_int(raw.get("bookingAmtExact")),
        sqft=parse_int(raw.get("carpetArea")) or parse_int(raw.get("coveredArea")),
        bhk=_parse_bhk(raw),
        lat=lat,
        lng=lng,
        locality=raw.get("lmtDName") or "",
        society=raw.get("prjname") or raw.get("lmtDName") or "",
        building_type="AP",
        floor=_parse_floor(raw),
        total_floors=parse_int(raw.get("floors")),
        has_lift=_parse_has_lift(raw, amenities),
        parking=parking,
        title=raw.get("propertyTitle", ""),
        url=f"https://www.magicbricks.com/propertyDetails/{url_path}" if url_path else "",
        photo_url=photos[0] if photos else (raw.get("image") or ""),
        facing=_parse_facing(raw),
        balconies=_parse_balconies(raw),
        age_years=_parse_age_years(raw),
        water_supply=_parse_water_supply(raw),
        is_negotiable=False,
        nobroker_transit_score=0,  # NoBroker-only scores
        nobroker_lifestyle_score=0,
        has_power_backup="power_backup" in amenities,
        is_gated_community="security" in amenities,  # MB has no explicit "gated"; security is the proxy
        has_covered_parking=parking in CAR_PARKING_TYPES,
        has_security="security" in amenities,
        has_fire_safety="fire_safety" in amenities,
        has_car_parking=parking in CAR_PARKING_TYPES,
    )


def iter_saved_listings(pages_dir: Path) -> Iterator[dict]:
    """Yield each raw listing from saved result pages, once per id."""
    seen_ids = set()
    for page_path in sorted(Path(pages_dir).glob("*.json")):
        with open(page_path) as f:
            page = json.load(f)
        for raw in page.get("resultList") or []:
            listing_key = listing_id(raw)
            if listing_key not in seen_ids:
                seen_ids.add(listing_key)
                yield raw


def parse_listings(raw_listings: list[dict]) -> list[Listing]:
    """Parse raw MB listings into Listings, de-duplicated by MB id."""
    seen_ids, listings = set(), []
    for raw in raw_listings:
        listing_key = listing_id(raw)
        if listing_key in seen_ids:
            continue
        seen_ids.add(listing_key)
        listing = normalize_listing(raw)
        if listing:
            listings.append(listing)
    return listings


def drop_nobroker_duplicates(nobroker_listings: list[Listing], magicbricks_listings: list[Listing],
                             rent_tolerance: float = 0.15, sqft_tolerance: float = 0.15) -> list[Listing]:
    """Return the MagicBricks listings that don't duplicate a NoBroker listing.

    A duplicate has the same BHK, rent and sqft within tolerance, and a fuzzy
    (substring) match on locality or society name.
    """
    def within(value: int, reference: int, tolerance: float) -> bool:
        return reference <= 0 or abs(value - reference) / reference <= tolerance

    nobroker_index = [(nb.bhk, nb.rent, nb.sqft,
                       nb.locality.lower().split(",")[0].strip(), nb.society.lower().strip())
                      for nb in nobroker_listings]

    unique = []
    for mb in magicbricks_listings:
        locality, society = mb.locality.lower().strip(), mb.society.lower().strip()
        is_duplicate = any(
            bhk == mb.bhk
            and within(mb.rent, rent, rent_tolerance)
            and (mb.sqft <= 0 or within(mb.sqft, sqft, sqft_tolerance))
            and (locality in nb_locality or nb_locality in locality
                 or society in nb_society or nb_society in society)
            for bhk, rent, sqft, nb_locality, nb_society in nobroker_index
        )
        if not is_duplicate:
            unique.append(mb)

    duplicates = len(magicbricks_listings) - len(unique)
    print(f"  Cross-platform dedup: {len(magicbricks_listings)} MB → {duplicates} dupes → {len(unique)} unique")
    return unique


# --- Fetching ---------------------------------------------------------------

def fetch_page(client: httpx.Client, page_number: int = 1,
               budget_min: int = 0, budget_max: int = 150000) -> dict:
    """Fetch one results page; {} on any network/parse error."""
    try:
        return get_json(client, SEARCH_API, {
            "editSearch": "Y",
            "category": "R",
            "propertyType": PROPERTY_TYPES,
            "bedrooms": BHK_TYPES,
            "cityName": CITY,
            "budgetMin": str(budget_min),
            "budgetMax": str(budget_max),
            "page": str(page_number),
        })
    except (httpx.HTTPError, ValueError) as e:
        print(f"  [!] Error page {page_number}: {e}")
        return {}


def fetch_all(budget_min: int = 0, budget_max: int = 150000, max_pages: int = 50,
              pages_dir: Optional[Path] = None) -> list[dict]:
    """Fetch result pages until one comes back empty; returns raw dicts."""
    raw_listings: list[dict] = []
    pages_fetched = 0
    with httpx.Client(follow_redirects=True, timeout=15, headers=REQUEST_HEADERS) as client:
        for page_number in range(1, max_pages + 1):
            print(f"  MagicBricks page {page_number}...")
            page = fetch_page(client, page_number, budget_min, budget_max)
            results = page.get("resultList") or []
            if not results:
                break

            raw_listings.extend(results)
            pages_fetched = page_number
            if pages_dir:
                pages_dir.mkdir(parents=True, exist_ok=True)
                (pages_dir / f"magicbricks_page{page_number}.json").write_text(json.dumps(page, indent=2))
            time.sleep(1)

    print(f"  MagicBricks total: {len(raw_listings)} raw listings across {pages_fetched} pages")
    return raw_listings
