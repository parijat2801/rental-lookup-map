"""Property Angel: fetch rental listings and normalise them to `Listing`.

API (JSON, no auth, but requests must carry the site's Origin/Referer):
  GET https://pa-api-core-509395667802.us-central1.run.app/properties/all
      every marketed property, summary fields only (no coordinates)
  GET .../properties/detail/{PropID}
      one property in full, including `LatLong`
The API allows 100 requests per 15 minutes per IP, and the site's own property
pages spend that same quota (one detail request per page view). Saved details
are reused across runs and new ones are capped per run, so the listing links
keep working while you browse right after a fetch.
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

API_BASE = "https://pa-api-core-509395667802.us-central1.run.app"
SITE_URL = "https://www.propertyangel.in"
CITY = "Bangalore"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": SITE_URL,
    "Referer": f"{SITE_URL}/",
}
MAX_NEW_DETAILS_PER_RUN = 60  # of the 100-per-15-minutes quota; the rest is left for browsing
# Their image CDN resizes on the fly; originals are multi-MB PNGs.
IMAGE_RESIZE_QUERY = "imop=Resize,width=800;Convert,format=webp"

BUILDING_TYPES = {
    "Apartment": "AP", "Duplex": "AP", "Villament": "AP",
    "Building Unit": "IF", "Independent House": "IH", "Villa": "GC",
}
FACING_CODES = {
    "east": "E", "west": "W", "north": "N", "south": "S",
    "northeast": "NE", "northwest": "NW", "southeast": "SE", "southwest": "SW",
}
# Bangalore building bylaws require a lift above ground + 4 floors; the API has no lift field.
MIN_FLOORS_WITH_LIFT = 5


# --- Field parsers ----------------------------------------------------------

def parse_int(value, default: int = 0) -> int:
    """Lenient int(): accepts ints, floats and numeric strings; else `default`."""
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def _display_value(raw: dict, key: str) -> str:
    """Text of a Zoho lookup field ({"ID": ..., "display_value": ...})."""
    value = raw.get(key)
    return str(value.get("display_value") or "") if isinstance(value, dict) else ""


def is_yes(value) -> bool:
    return str(value or "").strip().lower() in ("yes", "true", "1")


def prop_id(raw: dict) -> str:
    return _display_value(raw, "PropID")


def listing_id(raw: dict) -> str:
    """Prefixed with 'pa_' so ids never collide with other sources'."""
    return f"pa_{prop_id(raw)}"


def parse_coords(raw: dict) -> Optional[tuple[float, float]]:
    """`LatLong` from the detail payload, falling back to the newer `Latitude_New`/`Longitude_New`."""
    lat_long = raw.get("LatLong")
    candidates = []
    if isinstance(lat_long, dict):
        candidates.append((lat_long.get("latitude"), lat_long.get("longitude")))
    candidates.append((raw.get("Latitude_New"), raw.get("Longitude_New")))
    for lat, lng in candidates:
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            continue
        if lat and lng:
            return lat, lng
    return None


def _parse_bhk(raw: dict) -> str:
    bedrooms = parse_int(raw.get("No_of_Bedrooms"))
    return f"BHK{bedrooms}" if bedrooms > 0 else ""


def _parse_facing(raw: dict) -> str:
    direction = re.sub(r"[^a-z]", "", str(raw.get("Main_door_facing_Direction") or "").lower())
    return FACING_CODES.get(direction, "")


def parse_parking(raw: dict) -> str:
    """Car-parking code; "" when both count fields are absent (unknown)."""
    covered = raw.get("No_of_Covered_Car_Parks")
    open_ = raw.get("No_of_Open_Car_Parks")
    if covered is None and open_ is None:
        return ""
    if parse_int(covered) or parse_int(open_):
        return "FOUR_WHEELER"
    return "NONE"


def parse_balconies(raw: dict) -> int:
    """Balcony count; -1 when the field is absent (unknown)."""
    if raw.get("No_of_Balconies") is None:
        return -1
    return parse_int(raw.get("No_of_Balconies"))


def maintenance(raw: dict) -> int:
    """Monthly maintenance on top of the rent; 0 when it's included or unknown."""
    if "includ" in str(raw.get("Advertised_Rent_Includes_Mnt") or "").lower():
        return 0
    return parse_int(raw.get("Association_maintenance_amount"))


def furnishing(raw: dict) -> str:
    """Map-record furnishing code ("" = unknown)."""
    text = str(raw.get("Furnishing") or "").lower()
    if "semi" in text:
        return "SEMI"
    if "unfurnished" in text or "not furnished" in text:
        return "NONE"
    return "FULL" if "furnished" in text else ""


def photo_urls(raw: dict, max_photos: int = 10) -> list[str]:
    """Image URLs, the listing's primary photo first."""
    images = [image for image in raw.get("ImageList") or []
              if isinstance(image, dict) and isinstance(image.get("image"), str)]
    images.sort(key=lambda image: not image.get("isPrimary"))
    return [url if "?" in url else f"{url}?{IMAGE_RESIZE_QUERY}"
            for url in (image["image"] for image in images[:max_photos])]


def title(raw: dict) -> str:
    """The site's own heading, e.g. "2 BHK Semi Furnished Apartment for Rent in X, Budigere, Bangalore"."""
    bedrooms = parse_int(raw.get("No_of_Bedrooms"))
    place = ", ".join(filter(None, (_display_value(raw, "Projects"), _display_value(raw, "Location_Area"),
                                    raw.get("City_Zone_Classification.City") or CITY)))
    return " ".join(filter(None, (f"{bedrooms} BHK" if bedrooms > 0 else "", raw.get("Furnishing") or "",
                                  raw.get("Property_Type") or "Apartment", "for Rent", f"in {place}")))


def listing_url(raw: dict) -> str:
    """Public listing page; the site only reads the trailing `papid-<PropID>`."""
    slug = re.sub(r"[^a-z0-9]+", "-", title(raw).lower()).strip("-")
    return f"{SITE_URL}/property/{slug}-papid-{prop_id(raw)}"


# --- Normalisation ----------------------------------------------------------

def normalize_listing(raw: dict) -> Optional[Listing]:
    """Convert a Property Angel detail payload to a Listing; None if unusable."""
    coords = parse_coords(raw)
    rent = parse_int(raw.get("Advertised_Rent"))
    if not coords or rent <= 0 or not prop_id(raw):
        return None

    lat, lng = coords
    building_type = BUILDING_TYPES.get(raw.get("Property_Type") or "", "AP")
    total_floors = parse_int(raw.get("Total_no_of_Floors"))
    parking = parse_parking(raw)
    photos = photo_urls(raw, max_photos=1)
    has_security = is_yes(raw.get("Projects.Security"))
    project = _display_value(raw, "Projects")
    locality = _display_value(raw, "Location_Area")

    return Listing(
        id=listing_id(raw),
        rent=rent,
        deposit=parse_int(raw.get("Advertised_Security_Deposit")),
        sqft=parse_int(raw.get("Built_Up_Area_sft")),
        bhk=_parse_bhk(raw),
        lat=lat,
        lng=lng,
        locality=locality,
        society=project or locality,
        building_type=building_type,
        floor=parse_int(raw.get("Unit_is_on_Floor_0_for_Ground_floor")),
        total_floors=total_floors,
        has_lift=building_type == "AP" and total_floors >= MIN_FLOORS_WITH_LIFT,
        parking=parking,
        title=title(raw),
        url=listing_url(raw),
        photo_url=photos[0] if photos else "",
        facing=_parse_facing(raw),
        balconies=parse_balconies(raw),
        age_years=99,  # not published
        water_supply="",
        is_negotiable=False,
        nobroker_transit_score=0,  # NoBroker-only scores
        nobroker_lifestyle_score=0,
        has_power_backup=is_yes(raw.get("Projects.Power_backup")),
        is_gated_community=bool(project) and has_security,
        has_covered_parking=parse_int(raw.get("No_of_Covered_Car_Parks")) > 0,
        has_security=has_security,
        has_fire_safety=False,
        has_car_parking=parking in CAR_PARKING_TYPES,
    )


def iter_saved_listings(pages_dir: Path) -> Iterator[dict]:
    """Yield each saved detail payload, once per PropID."""
    seen_ids = set()
    for page_path in sorted(Path(pages_dir).glob("*.json")):
        with open(page_path) as f:
            raw = json.load(f)
        listing_key = listing_id(raw)
        if listing_key not in seen_ids:
            seen_ids.add(listing_key)
            yield raw


def parse_listings(raw_listings: list[dict]) -> list[Listing]:
    """Parse detail payloads into Listings, de-duplicated by PropID."""
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


# --- Fetching ---------------------------------------------------------------

def fetch_summaries(client: httpx.Client) -> list[dict]:
    """Every marketed property in CITY (summary fields); [] on any network/parse error."""
    try:
        results = get_json(client, f"{API_BASE}/properties/all", {}).get("data") or []
    except (httpx.HTTPError, ValueError) as e:
        print(f"  [!] Error fetching Property Angel listings: {e}")
        return []
    summaries = [item.get("meta_data") or {} for item in results if isinstance(item, dict)]
    return [s for s in summaries if s.get("City_Zone_Classification.City") == CITY and prop_id(s)]


class RateLimited(Exception):
    """The API's per-IP quota is used up."""


def fetch_detail(client: httpx.Client, property_id: str) -> dict:
    """One property's detail payload; {} on any error. Raises RateLimited on HTTP 429.

    Not retried: a retry spends quota, and a failed property is fetched next run.
    """
    try:
        return get_json(client, f"{API_BASE}/properties/detail/{property_id}", {}, attempts=1).get("data") or {}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise RateLimited from e
        print(f"  [!] Error fetching Property Angel property {property_id}: {e}")
    except (httpx.HTTPError, ValueError) as e:
        print(f"  [!] Error fetching Property Angel property {property_id}: {e}")
    return {}


def _saved_path(pages_dir: Path, property_id: str) -> Path:
    return pages_dir / f"propertyangel_{property_id}.json"


def fetch_all(pages_dir: Optional[Path] = None, max_new_details: int = MAX_NEW_DETAILS_PER_RUN) -> list[dict]:
    """Fetch every listing in CITY as a detail payload; returns raw dicts.

    Details already saved in `pages_dir` are reused, with the fresh summary
    fields (rent, furnishing, tenancy...) written over them. At most
    `max_new_details` new properties are fetched; the rest wait for a later run.
    Saved properties that are no longer listed are deleted.
    """
    raw_listings: list[dict] = []
    with httpx.Client(follow_redirects=True, timeout=30, headers=REQUEST_HEADERS) as client:
        summaries = fetch_summaries(client)
        if not summaries:
            return []
        saved = {prop_id(raw): raw for raw in iter_saved_listings(pages_dir)} if pages_dir else {}
        new_ids = [prop_id(s) for s in summaries if prop_id(s) not in saved]
        print(f"  Property Angel: {len(summaries)} listings in {CITY}, {len(new_ids)} new, "
              f"fetching up to {max_new_details}...")

        details_left = max_new_details
        for summary in summaries:
            property_id = prop_id(summary)
            detail = saved.get(property_id)
            if detail is None:
                if details_left <= 0:
                    continue
                details_left -= 1
                try:
                    detail = fetch_detail(client, property_id)
                except RateLimited:
                    print("  [!] Property Angel rate limit reached; remaining properties will be fetched next run")
                    details_left = 0
                    continue
                time.sleep(1)
                if not detail:
                    continue
            raw = {**detail, **summary}
            raw_listings.append(raw)
            if pages_dir:
                pages_dir.mkdir(parents=True, exist_ok=True)
                _saved_path(pages_dir, property_id).write_text(json.dumps(raw, indent=2))

    if pages_dir:
        listed = {prop_id(s) for s in summaries}
        for property_id in set(saved) - listed:
            _saved_path(pages_dir, property_id).unlink(missing_ok=True)
        print(f"  Property Angel: removed {len(set(saved) - listed)} listings no longer marketed")
    print(f"  Property Angel total: {len(raw_listings)} listings with details")
    return raw_listings
