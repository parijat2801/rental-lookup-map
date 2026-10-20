"""Build output/map.html from scraped listings and cached extras.

Inputs (all optional except the template):
  data/raw/*.json        NoBroker pages (current run)
  data/raw_prev/*.json   NoBroker pages from the previous run, to show delisted listings
  data/raw_mb/*.json     MagicBricks pages
  data/cache/*.json      stars/dismissals, first-seen dates, photo ratings, fake-location ids,
                         listing details
  data/metro_lines.json  Namma Metro overlay (regenerate with scripts/fetch_metro_lines.py)

Run: python -m rental_lookup.webmap.builder

The listing records built here are read by webmap/template.html, so their keys
are part of the template's contract: rename them in both places together.
"""
from __future__ import annotations

import html
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rental_lookup.listing_age import days_since_posted_magicbricks, days_since_posted_nobroker
from rental_lookup.models import NOBROKER_BASE_URL, Listing, mentions_branded_builder, nobroker_platform_scores
from rental_lookup.paths import (
    ENV_PATH, FAKE_LOCATION_IDS_PATH, FIRST_SEEN_PATH, LISTING_DETAILS_PATH, MAGICBRICKS_PAGES_DIR,
    MAP_PAGE_PATH, MAP_TEMPLATE_PATH, METRO_LINES_PATH, NOBROKER_PAGES_DIR,
    PREVIOUS_NOBROKER_PAGES_DIR, STARS_PATH,
)
from rental_lookup.sources import magicbricks
from rental_lookup.sources.nobroker import has_real_photo, iter_saved_listings, photo_urls

MAX_RENT = 150000
MIN_SQFT = 500
STACKED_LISTING_THRESHOLD = 3  # more listings than this at one coordinate = likely a fake/centroid location
PET_PHRASES = ("pet-friendly", "pet friendly", "pets allowed", "pets welcome")
# NoBroker amenitiesMap code -> map record key
NOBROKER_AMENITY_KEYS = {
    "PB": "hasPowerBackup", "GP": "isGated", "SECURITY": "hasSecurity", "FS": "hasFireSafety",
    "POOL": "hasPool", "GYM": "hasGym", "CLUB": "hasClubhouse", "PARK": "hasPark",
    "INTERCOM": "hasIntercom", "CPA": "hasCoveredParking",
}
# Source furnishing values -> map record "furnishing" ("" = unknown)
NOBROKER_FURNISHING = {"FULLY_FURNISHED": "FULL", "SEMI_FURNISHED": "SEMI", "NOT_FURNISHED": "NONE"}
MAGICBRICKS_FURNISHING = {11900: "FULL", 11902: "SEMI", 11901: "NONE"}


@dataclass
class BuildContext:
    """Lookups shared by every record builder."""
    fake_location_ids: set
    stacked_coordinates: set  # coordinate_key()s shared by too many listings


def load_json(path: Path, default):
    """Read a JSON cache file, falling back to `default` if missing or corrupt."""
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default
    except ValueError as e:
        print(f"  [!] Ignoring unreadable {path.name}: {e}")
        return default


def coordinate_key(lat: float, lng: float) -> tuple[float, float]:
    return round(lat, 4), round(lng, 4)  # ~11m grid


def _nobroker_in_scope(raw: dict) -> bool:
    return (0 <= (raw.get("rent") or 0) <= MAX_RENT
            and (raw.get("propertySize") or 0) >= MIN_SQFT
            and bool(raw.get("latitude")) and bool(raw.get("longitude")))


def _short_description(text: str) -> str:
    return (text or "")[:200].replace("\n", " ")


def _nobroker_cover_photo(raw: dict, photos: list[str]) -> str:
    if photos:
        return photos[0]
    thumbnail = raw.get("thumbnailImage") or ""
    return "" if "static/img" in thumbnail else thumbnail  # skip NoBroker's placeholder


# --- Record builders ----------------------------------------------------------

def nobroker_record(raw: dict, details: dict, context: BuildContext) -> dict:
    """Map record for a current NoBroker listing (`details` from the detail-page cache)."""
    amenities = raw.get("amenitiesMap") or {}
    society = raw.get("society") or ""
    description = details.get("description") or ""
    maintenance = details.get("maintenanceAmount") or 0
    if not isinstance(maintenance, (int, float)):
        maintenance = 0
    transit_score, lifestyle_score = nobroker_platform_scores(raw)
    photos = photo_urls(raw)
    rent = raw.get("rent") or 0
    balconies = raw.get("balconies")

    return {
        "lat": raw["latitude"], "lng": raw["longitude"],
        "rent": rent, "maintenance": maintenance, "totalCost": rent + maintenance,
        "deposit": raw.get("deposit", 0), "sqft": raw.get("propertySize", 0),
        "bhk": raw.get("type", ""), "society": society,
        "locality": raw.get("locality", ""), "facing": raw.get("facing") or "",
        "balconies": balconies if balconies is not None else -1,  # -1 = unknown
        "floor": raw.get("floor", 0), "totalFloors": raw.get("totalFloor", 0),
        "hasLift": raw.get("lift", False) or amenities.get("LIFT", False),
        "ageYears": raw.get("propertyAge", 99),
        "buildingType": raw.get("buildingType", ""),
        "furnishing": NOBROKER_FURNISHING.get(raw.get("furnishing"), ""),
        "parking": raw.get("parking", "NONE"),
        "isNegotiable": raw.get("negotiable", False),
        "waterSupply": raw.get("waterSupply", ""),
        "nbTransit": transit_score, "nbLifestyle": lifestyle_score,
        **{key: amenities.get(code, False) for code, key in NOBROKER_AMENITY_KEYS.items()},
        "photoCount": len(raw.get("photos") or []),
        "hasRealPhoto": has_real_photo(raw),
        "isBrandedBuilder": mentions_branded_builder(f"{society} {raw.get('propertyTitle') or ''}"),
        "isPetFriendly": any(phrase in description.lower() for phrase in PET_PHRASES),
        "cupboards": details.get("cupBoard") or 0,
        "street": (details.get("completeStreetName") or "")[:80],
        "availableFrom": details.get("availableFrom", ""),
        "propertyCode": details.get("propertyCode", ""),
        "description": _short_description(description),
        "isStacked": coordinate_key(raw["latitude"], raw["longitude"]) in context.stacked_coordinates,
        "isFakeLocation": raw["id"] in context.fake_location_ids,
        "daysAgo": 0,
        "coverPhoto": _nobroker_cover_photo(raw, photos),
        "photos": photos,
        "url": NOBROKER_BASE_URL + raw.get("detailUrl", ""),
        "source": "nb",
        "isDelisted": False,
    }


def delisted_nobroker_record(raw: dict, context: BuildContext) -> dict:
    """Greyed-out record for a listing seen last run but gone now.

    Only the search-result data from last run is used: no details, platform
    scores or recency.
    """
    record = nobroker_record(raw, {}, context)
    record.update({
        "hasLift": raw.get("lift", False),
        "isNegotiable": False, "nbTransit": 0, "nbLifestyle": 0, "isBrandedBuilder": False,
        "isStacked": False, "daysAgo": -1, "isDelisted": True,
    })
    return record


def magicbricks_record(listing: Listing, raw: dict, context: BuildContext) -> dict:
    """Map record for a MagicBricks listing (`listing` is its normalised form)."""
    photos = magicbricks.photo_urls(raw)
    amenities = magicbricks.amenity_names(raw)
    maintenance = magicbricks.parse_int(raw.get("maintenanceCharges"))
    return {
        "lat": listing.lat, "lng": listing.lng,
        "rent": listing.rent, "maintenance": maintenance, "totalCost": listing.rent + maintenance,
        "deposit": listing.deposit, "sqft": listing.sqft,
        "bhk": listing.bhk, "society": listing.society,
        "locality": listing.locality, "facing": listing.facing,
        "balconies": listing.balconies, "floor": listing.floor,
        "totalFloors": listing.total_floors,
        "hasLift": listing.has_lift, "ageYears": listing.age_years,
        "buildingType": listing.building_type, "parking": listing.parking,
        "furnishing": MAGICBRICKS_FURNISHING.get(magicbricks.parse_int(raw.get("furnished")), ""),
        "isNegotiable": False, "waterSupply": listing.water_supply,
        "nbTransit": 0, "nbLifestyle": 0,
        "hasPowerBackup": listing.has_power_backup, "isGated": listing.is_gated_community,
        "hasSecurity": listing.has_security, "hasFireSafety": listing.has_fire_safety,
        "hasPool": "pool" in amenities, "hasGym": "gym" in amenities, "hasClubhouse": "club" in amenities,
        "hasPark": "park" in amenities, "hasIntercom": "intercom" in amenities,
        "hasCoveredParking": listing.has_covered_parking,
        "photoCount": magicbricks.parse_int(raw.get("imgCt")),
        "hasRealPhoto": bool(photos),
        "isBrandedBuilder": False, "isPetFriendly": False, "cupboards": 0,
        "street": (raw.get("psmAdd") or "")[:80],
        "availableFrom": raw.get("possStatusD") or "",
        "propertyCode": "",
        "description": _short_description(raw.get("auto_desc")),
        "isStacked": coordinate_key(listing.lat, listing.lng) in context.stacked_coordinates,
        "isFakeLocation": False,
        "daysAgo": 0,
        "coverPhoto": photos[0] if photos else (raw.get("image") or ""),
        "photos": photos,
        "url": listing.url,
        "source": "mb",
        "isDelisted": False,
    }


# --- Assembly -------------------------------------------------------------------

def _duplicate_signature(rent, sqft, bhk, locality: str) -> str:
    return f"{rent}_{sqft}_{bhk}_{locality}"


def build_records(today: date, first_seen: dict) -> list[dict]:
    """All map records: current NoBroker, then unique MagicBricks, then delisted.

    Updates `first_seen` in place with listings seen for the first time today.
    """
    stars = load_json(STARS_PATH, {})
    starred, dismissed = stars.get("starred") or {}, stars.get("dismissed") or {}
    print(f"  Stars: {len(starred)} starred, {len(dismissed)} dismissed")
    print(f"  First seen: {len(first_seen)} listings tracked")
    fake_location_ids = set(load_json(FAKE_LOCATION_IDS_PATH, []))
    details_by_id = load_json(LISTING_DETAILS_PATH, {})
    print(f"  Fake locations: {len(fake_location_ids)} listings")

    nobroker_raw = list(iter_saved_listings(NOBROKER_PAGES_DIR))
    magicbricks_listings = [(listing, raw) for raw in magicbricks.iter_saved_listings(MAGICBRICKS_PAGES_DIR)
                            if (listing := magicbricks.normalize_listing(raw))]

    # Several distinct listings on one exact spot means a shared (fake / centroid) location.
    listings_per_coordinate = Counter(coordinate_key(raw["latitude"], raw["longitude"]) for raw in nobroker_raw
                                      if raw.get("latitude") and raw.get("longitude"))
    listings_per_coordinate.update(coordinate_key(listing.lat, listing.lng) for listing, _ in magicbricks_listings)
    context = BuildContext(
        fake_location_ids=fake_location_ids,
        stacked_coordinates={key for key, count in listings_per_coordinate.items()
                             if count > STACKED_LISTING_THRESHOLD},
    )
    print(f"  Stacked coords (NB+MB): {len(context.stacked_coordinates)} locations")

    records = []
    for raw in filter(_nobroker_in_scope, nobroker_raw):
        record = nobroker_record(raw, details_by_id.get(raw["id"]) or {}, context)
        first_seen.setdefault(record["url"], str(today))
        record["daysAgo"] = days_since_posted_nobroker(raw.get("activationDate", 0), first_seen[record["url"]], today)
        records.append(record)

    # MagicBricks: skip listings that look like a NoBroker one already on the map.
    nobroker_signatures = {
        _duplicate_signature(r["rent"], r["sqft"], r["bhk"], r["locality"].lower().split(",")[0].strip())
        for r in records
    }
    magicbricks_added = 0
    for listing, raw in magicbricks_listings:
        signature = _duplicate_signature(listing.rent, listing.sqft, listing.bhk, listing.locality.lower().strip())
        if signature in nobroker_signatures:
            continue
        record = magicbricks_record(listing, raw, context)
        record["daysAgo"] = days_since_posted_magicbricks(raw.get("postDateT"),
                                                          first_seen.setdefault(listing.url, str(today)), today)
        records.append(record)
        magicbricks_added += 1
    if magicbricks_listings:
        print(f"  MagicBricks: {len(magicbricks_listings)} parsed, {magicbricks_added} unique added to map")

    current_ids = {raw["id"] for raw in nobroker_raw}
    previous_raw = list(iter_saved_listings(PREVIOUS_NOBROKER_PAGES_DIR))
    if previous_raw:
        print(f"  Previous data: {len(previous_raw)} listings")
        delisted = [delisted_nobroker_record(raw, context) for raw in previous_raw
                    if raw["id"] not in current_ids and _nobroker_in_scope(raw)]
        records.extend(delisted)
        print(f"  Delisted listings added: {len(delisted)}")

    # Embed saved stars/dismissals (the page merges them with localStorage and stars.json).
    for record in records:
        if record["url"] in starred:
            record["savedStarredAt"] = starred[record["url"]]
        if record["url"] in dismissed:
            record["savedDismissedAt"] = dismissed[record["url"]]
    return records


def _unescape_strings(value):
    """Decode HTML entities (&amp;, &#39;, ...) that the platforms leave in text fields."""
    if isinstance(value, str):
        return html.unescape(value)
    if isinstance(value, list):
        return [_unescape_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: _unescape_strings(item) for key, item in value.items()}
    return value


def to_script_json(value) -> str:
    """Compact JSON that is safe to inline in a <script> block."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")


def inject(template: str, variable: str, value_json: str) -> str:
    """Replace the single-line `var NAME = ...;` declaration in the template."""
    declaration = re.compile(rf"^var {variable} = .*;$", re.MULTILINE)
    page, replaced = declaration.subn(lambda _: f"var {variable} = {value_json};", template, count=1)
    if replaced != 1:
        raise ValueError(f"Template is missing a single-line `var {variable} = ...;` declaration")
    return page


def carto_key(env_path: Path = ENV_PATH) -> str:
    """CARTO basemaps key from $CARTO_BASEMAPS_KEY, else from a gitignored .env; '' if unset."""
    key = os.environ.get("CARTO_BASEMAPS_KEY", "").strip()
    if key or not env_path.exists():
        return key
    for line in env_path.read_text().splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() == "CARTO_BASEMAPS_KEY":
            return value.strip().strip("'\"")
    return ""


def main() -> None:
    print("Building map...")
    today = date.today()
    first_seen = load_json(FIRST_SEEN_PATH, {})
    records = build_records(today, first_seen)

    FIRST_SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIRST_SEEN_PATH.write_text(json.dumps(first_seen))
    print(f"  First seen saved: {len(first_seen)} listings")

    page = MAP_TEMPLATE_PATH.read_text(encoding="utf-8")
    page = inject(page, "LISTINGS", to_script_json(_unescape_strings(records)))
    if METRO_LINES_PATH.exists():
        page = inject(page, "METRO_LINES", to_script_json(json.loads(METRO_LINES_PATH.read_text())))
    key = carto_key()
    page = inject(page, "CARTO_KEY", to_script_json(key))
    print(f"  Basemap: {'CARTO' if key else 'Esri (set CARTO_BASEMAPS_KEY for CARTO tiles)'}")

    MAP_PAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAP_PAGE_PATH.write_text(page, encoding="utf-8")
    print(f"Map built with {len(records)} listings")


if __name__ == "__main__":
    main()
