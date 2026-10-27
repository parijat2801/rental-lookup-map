"""99acres: fetch rental listings and normalise them to `Listing`.

Fetch order when calling `fetch_all`:
  1. Apify actor `themineworks/99acres-scraper` when `APIFY_TOKEN` is set
     (env or `.env`) — best against Akamai; paid per listing.
  2. JSON API (`/api-aggregator/srp/search`) with an optional browser cookie.
  3. Chrome SSR via Playwright reading `window.__initialData__`.

Apify items are adapted into the same SRP-shaped dicts the API/SSR paths save,
so `normalize_listing` / the map builder stay unchanged.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import httpx

from rental_lookup.models import CAR_PARKING_TYPES, Listing
from rental_lookup.paths import ENV_PATH
from rental_lookup.sources.http import get_json

APIFY_ACTOR = "themineworks/99acres-scraper"
# Actor input schema rejects anything above this.
APIFY_MAX_RESULTS_CAP = 2000

SEARCH_API = "https://www.99acres.com/api-aggregator/srp/search"
SITE_URL = "https://www.99acres.com"
CITY_ID = "20"  # Bangalore
BHK_TYPES = "1,2,3"
# 1=Apartment / flat (residential)
PROPERTY_TYPES = "1"
PAGE_SIZE = 30
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Origin": SITE_URL,
    "Referer": f"{SITE_URL}/search/property/rent/bangalore?city={CITY_ID}&preference=R&area_unit=1&res_com=R",
}

# Amenity / feature numeric codes seen on SRP payloads.
AMENITY_CODES = {
    "lift": "3", "park": "5", "reserved_parking": "6", "security": "9",
    "water_storage": "10", "maintenance_staff": "12", "piped_gas": "19",
    "pool": "21", "gym": "22", "club": "23", "visitor_parking": "26",
    "waste_disposal": "28", "fire_safety": "39", "gymnasium": "40",
    "rainwater": "41", "intercom": "17", "power_backup": "1",
}
FACING_CODES = {
    "1": "N", "2": "S", "3": "E", "4": "W",
    "5": "NE", "6": "NW", "7": "SE", "8": "SW",
    "north": "N", "south": "S", "east": "E", "west": "W",
    "north-east": "NE", "north-west": "NW", "south-east": "SE", "south-west": "SW",
    "northeast": "NE", "northwest": "NW", "southeast": "SE", "southwest": "SW",
}
# furnish code -> map-record furnishing ("" = unknown)
FURNISH_CODES = {"1": "FULL", "2": "NONE", "4": "SEMI"}
GROUND_FLOOR_LABELS = ("ground", "g", "lower basement", "upper basement", "basement")
# India bounds used to detect MAP_DETAILS lat/lng that arrive swapped.
_LAT_RANGE = (6.0, 37.0)
_LNG_RANGE = (68.0, 98.0)


# --- Field helpers ----------------------------------------------------------

def _get(raw: dict, *keys, default=None):
    """First present key (UPPERCASE API keys or Apify-style lowercase)."""
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return raw[key]
        lower = key.lower()
        if lower in raw and raw[lower] not in (None, ""):
            return raw[lower]
    return default


def parse_int(value, default: int = 0) -> int:
    """Lenient int(): accepts ints, floats and numeric strings; else `default`."""
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def _parse_float(value) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def prop_id(raw: dict) -> str:
    return str(_get(raw, "PROP_ID", "prop_id", "SPID", "spid") or "").strip()


def building_name(raw: dict) -> str:
    return str(_get(raw, "BUILDING_NAME", "building_name") or "").strip()


def floor_known(raw: dict) -> bool:
    return _get(raw, "FLOOR_NUM", "floor_num") is not None


def posting_date_ms(raw: dict):
    """Epoch milliseconds from POSTING_DATE / POSTING_DATE__U / posted_on, or None."""
    value = _get(raw, "POSTING_DATE", "posting_date", "POSTING_DATE__U", "posting_date__u")
    if value not in (None, ""):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            pass
    return _parse_posted_on_ms(_get(raw, "posted_on", "POSTED_ON"))


def _parse_posted_on_ms(value) -> Optional[int]:
    """Apify-style `17th Oct, 2026` → epoch ms at midnight local; None if unparseable."""
    if value in (None, ""):
        return None
    text = str(value).strip()
    match = re.match(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9}),?\s+(\d{4})$", text
    )
    if not match:
        return None
    day, month_token, year = match.groups()
    for fmt in ("%b", "%B"):
        try:
            dt = datetime.strptime(f"{day} {month_token} {year}", f"%d {fmt} %Y")
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    return None


def listing_id(raw: dict) -> str:
    """Prefixed with '9a_' so ids never collide with other sources'."""
    return f"9a_{prop_id(raw)}"


def amenity_codes(raw: dict) -> set[str]:
    """Numeric amenity/feature codes advertised on the listing."""
    codes = set()
    for field in ("AMENITIES", "amenities", "FEATURES", "features"):
        codes.update(re.findall(r"\d+", str(raw.get(field) or "")))
    return codes


def amenity_names(raw: dict) -> set[str]:
    codes = amenity_codes(raw)
    names = {name for name, code in AMENITY_CODES.items() if code in codes}
    # Apify (and some SSR blobs) ship human-readable amenity bullets instead of codes.
    names.update(_amenity_names_from_text(raw.get("amenities") or raw.get("AMENITIES")))
    return names


def _amenity_names_from_text(value) -> set[str]:
    if isinstance(value, list):
        texts = [str(item) for item in value]
    elif isinstance(value, str) and value.strip():
        texts = [value]
    else:
        return set()
    blob = " | ".join(texts).lower()
    names = set()
    if re.search(r"power\s*backup", blob):
        names.add("power_backup")
    if re.search(r"\blift\b|\belevator\b", blob):
        names.add("lift")
    if re.search(r"\bpark\b|garden", blob):
        names.add("park")
    if re.search(r"parking", blob):
        names.add("reserved_parking")
    if re.search(r"security|gated", blob):
        names.add("security")
    if re.search(r"\bpool\b|swimming", blob):
        names.add("pool")
    if re.search(r"\bgym", blob):
        names.add("gym")
    if re.search(r"fire\s*(safety|extinguisher|fighting)?", blob):
        names.add("fire_safety")
    if re.search(r"club\s*house|\bclub\b", blob):
        names.add("club")
    return names


def _facing_from_amenity_text(value) -> str:
    if isinstance(value, list):
        blob = " ".join(str(item) for item in value)
    else:
        blob = str(value or "")
    match = re.search(
        r"\b(north-east|north-west|south-east|south-west|northeast|northwest|"
        r"southeast|southwest|north|south|east|west)\s*facing\b",
        blob, re.I,
    )
    if not match:
        return ""
    return FACING_CODES.get(re.sub(r"\s+", "", match.group(1).lower()), "")


def parse_coords(raw: dict) -> Optional[tuple[float, float]]:
    """Property coordinates from MAP_DETAILS, `location`, or top-level lat/lng (Apify).

    99acres occasionally swaps lat/lng labels; values are resolved by India bounds.
    """
    candidates = []
    details = _get(raw, "MAP_DETAILS", "map_details", default={}) or {}
    if isinstance(details, dict):
        candidates.append((
            _parse_float(_get(details, "LATITUDE", "latitude")),
            _parse_float(_get(details, "LONGITUDE", "longitude")),
        ))
    location = raw.get("location") or raw.get("LOCATION")
    if isinstance(location, dict):
        candidates.append((
            _parse_float(_get(location, "LATITUDE", "latitude")),
            _parse_float(_get(location, "LONGITUDE", "longitude")),
        ))
    candidates.append((
        _parse_float(_get(raw, "LATITUDE", "latitude")),
        _parse_float(_get(raw, "LONGITUDE", "longitude")),
    ))
    for a, b in candidates:
        if _LAT_RANGE[0] <= a <= _LAT_RANGE[1] and _LNG_RANGE[0] <= b <= _LNG_RANGE[1]:
            return a, b
        if _LAT_RANGE[0] <= b <= _LAT_RANGE[1] and _LNG_RANGE[0] <= a <= _LNG_RANGE[1]:
            return b, a
    return None


def has_property_pin(raw: dict) -> bool:
    """True when coordinates look like a property/project pin, not a city/locality centroid."""
    details = _get(raw, "MAP_DETAILS", "map_details", default={}) or {}
    if not isinstance(details, dict) or not parse_coords(raw):
        return False
    source = str(_get(details, "SOURCE", "source") or "").upper()
    if source in ("CITY", "LOCALITY"):
        return False
    accuracy = parse_int(_get(details, "MAP_ACCURACY", "map_accuracy"))
    return accuracy > 0 or source in ("PROJECT", "PROP", "BUILDING", "SOCIETY")


def _parse_bhk(raw: dict) -> str:
    bedrooms = parse_int(_get(raw, "BEDROOM_NUM", "bedroom_num", "bhk", "BHK"))
    return f"BHK{bedrooms}" if bedrooms > 0 else ""


def _parse_floor(raw: dict) -> int:
    floor = _get(raw, "FLOOR_NUM", "floor_num", "floor")
    if floor is None:
        return 0
    text = str(floor).strip().lower()
    if text in GROUND_FLOOR_LABELS or text.startswith("ground"):
        return 0
    match = re.search(r"\d+", text)
    return parse_int(match.group()) if match else 0


def _parse_facing(raw: dict) -> str:
    facing = _get(raw, "FACING", "facing")
    if facing is None or str(facing).strip() in ("", "0"):
        return _facing_from_amenity_text(raw.get("amenities") or raw.get("AMENITIES"))
    text = str(facing).strip()
    if text.upper() in {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}:
        return text.upper()
    key = re.sub(r"\s+", "", text.lower())
    return FACING_CODES.get(text, FACING_CODES.get(key, ""))


def _parse_parking(raw: dict, amenities: set[str]) -> str:
    """Car-parking code; "" when unknown."""
    if "reserved_parking" in amenities:
        return "FOUR_WHEELER"
    text = str(_get(raw, "PARKING", "parking") or "").lower()
    if not text and not amenities:
        return ""
    if "car" in text or "covered" in text or "reserved" in text:
        return "FOUR_WHEELER"
    if "bike" in text or "two" in text:
        return "TWO_WHEELER"
    if text in ("none", "no", "n"):
        return "NONE"
    return ""


def _parse_balconies(raw: dict) -> int:
    if _get(raw, "BALCONY_NUM", "balcony_num") is None:
        return -1
    return parse_int(_get(raw, "BALCONY_NUM", "balcony_num"))


def _parse_has_lift(raw: dict, amenities: set[str]) -> Optional[bool]:
    text_names = _amenity_names_from_text(raw.get("amenities") or raw.get("AMENITIES"))
    if not amenity_codes(raw) and not text_names:
        return None
    return "lift" in amenities


def _parse_age_years(raw: dict) -> int:
    age = _get(raw, "AGE", "age", "age_years")
    if age is None or age == "":
        return 99
    years = parse_int(age, default=-1)
    if years >= 0:
        return years
    label = str(age).lower()
    if "new" in label or "under construction" in label:
        return 1
    numbers = [int(n) for n in re.findall(r"\d+", label)]
    return numbers[0] if numbers else 99


def _parse_sqft(raw: dict) -> int:
    for key in ("BUILTUP_SQFT", "builtup_sqft", "CARPET_SQFT", "carpet_sqft",
                "SUPERBUILTUP_SQFT", "superbuiltup_sqft", "SUPER_SQFT", "super_sqft",
                "AREA_SQFT", "area_sqft"):
        value = parse_int(_get(raw, key))
        if value > 50:  # skip sq.m values mistakenly labelled as sqft
            return value
    area = str(_get(raw, "AREA", "area") or "")
    match = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:sq\.?\s*ft|sqft)", area, re.I)
    if match:
        return parse_int(match.group(1))
    if re.search(r"[\d,]+", area):
        return parse_int(re.search(r"[\d,]+", area).group())
    # Apify sometimes returns absurdly small AREA_SQFT; the listing URL usually has the real figure.
    url = str(_get(raw, "PD_URL", "pd_url", "listing_url", "LISTING_URL") or "")
    url_match = re.search(r"(\d+)\s*-?\s*sq\.?ft", url, re.I)
    return parse_int(url_match.group(1)) if url_match else 0


def furnishing(raw: dict) -> str:
    """Map-record furnishing code ("" = unknown)."""
    code = str(_get(raw, "FURNISH", "furnish") or "").strip()
    if code in FURNISH_CODES:
        return FURNISH_CODES[code]
    text = code.lower()
    if "semi" in text:
        return "SEMI"
    if "unfurnish" in text or text in ("none", "not furnished"):
        return "NONE"
    return "FULL" if "furnish" in text else ""


def photo_urls(raw: dict, max_photos: int = 10) -> list[str]:
    urls: list[str] = []
    for key in ("PROPERTY_IMAGES", "property_images", "THUMBNAIL_IMAGES", "thumbnail_images"):
        images = raw.get(key)
        if isinstance(images, list):
            urls.extend(u for u in images if isinstance(u, str) and u.startswith("http"))
    formatted = _get(raw, "FORMATTED", "formatted", default={}) or {}
    if isinstance(formatted, dict):
        images = formatted.get("property_images") or formatted.get("PROPERTY_IMAGES") or []
        if isinstance(images, list):
            urls.extend(u for u in images if isinstance(u, str) and u.startswith("http"))
    for key in ("MEDIUM_PHOTO_URL", "medium_photo_url", "PHOTO_URL", "photo_url"):
        url = raw.get(key)
        if isinstance(url, str) and url.startswith("http"):
            urls.append(url)
    seen, unique = set(), []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique[:max_photos]


def listing_url(raw: dict) -> str:
    path = str(_get(raw, "PD_URL", "pd_url", "PROP_DETAILS_URL", "prop_details_url") or "").strip()
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return f"{SITE_URL}{path if path.startswith('/') else '/' + path}"


# --- Normalisation ----------------------------------------------------------

def normalize_listing(raw: dict) -> Optional[Listing]:
    """Convert a raw 99acres SRP item (or Apify-adapted dict) to a Listing; None if unusable."""
    coords = parse_coords(raw)
    rent = parse_int(_get(raw, "MIN_PRICE", "min_price", "MAX_PRICE", "max_price", "price", "PRICE"))
    if not coords or rent <= 0 or not prop_id(raw):
        return None

    lat, lng = coords
    amenities = amenity_names(raw)
    parking = _parse_parking(raw, amenities)
    photos = photo_urls(raw, max_photos=1)
    society = str(_get(raw, "SOCIETY_NAME", "society_name", "BUILDING_NAME", "building_name",
                       "PROP_NAME", "prop_name", "society") or "").strip()
    locality = str(_get(raw, "LOCALITY_WO_CITY", "locality_wo_city", "LOCALITY", "locality") or "").strip()
    locality = locality.split(",")[0].strip()
    has_security = "security" in amenities
    gated = str(_get(raw, "GATED", "gated") or "").upper() in ("Y", "YES", "TRUE", "1")
    title = str(_get(raw, "PROP_HEADING", "prop_heading", "PROP_NAME", "prop_name", "title") or "")
    url = listing_url(raw) or str(_get(raw, "listing_url", "LISTING_URL") or "")

    return Listing(
        id=listing_id(raw),
        rent=rent,
        deposit=parse_int(_get(raw, "SECURITY_DEPOSIT", "security_deposit", "DEPOSIT", "deposit")),
        sqft=_parse_sqft(raw),
        bhk=_parse_bhk(raw),
        lat=lat,
        lng=lng,
        locality=locality,
        society=society or locality,
        building_type="AP",
        floor=_parse_floor(raw),
        total_floors=parse_int(_get(raw, "TOTAL_FLOOR", "total_floor", "total_floors")),
        has_lift=_parse_has_lift(raw, amenities),
        parking=parking,
        title=title,
        url=url,
        photo_url=photos[0] if photos else "",
        facing=_parse_facing(raw),
        balconies=_parse_balconies(raw),
        age_years=_parse_age_years(raw),
        water_supply="",
        is_negotiable=False,
        nobroker_transit_score=0,
        nobroker_lifestyle_score=0,
        has_power_backup="power_backup" in amenities,
        is_gated_community=gated or has_security,
        has_covered_parking=parking in CAR_PARKING_TYPES,
        has_security=has_security,
        has_fire_safety="fire_safety" in amenities,
        has_car_parking=parking in CAR_PARKING_TYPES,
    )


def iter_saved_listings(pages_dir: Path) -> Iterator[dict]:
    """Yield each raw listing from saved result pages, once per PROP_ID."""
    seen_ids = set()
    for page_path in sorted(Path(pages_dir).glob("*.json")):
        with open(page_path) as f:
            page = json.load(f)
        for raw in page_properties(page):
            listing_key = listing_id(raw)
            if listing_key not in seen_ids and prop_id(raw):
                seen_ids.add(listing_key)
                yield raw


def page_properties(page: dict) -> list[dict]:
    """Property dicts from one SRP response (skips ads / pseudo tuples)."""
    if not isinstance(page, dict):
        return []
    properties = page.get("properties") or page.get("PROPERTIES") or []
    if not isinstance(properties, list):
        return []
    return [item for item in properties if isinstance(item, dict) and prop_id(item)]


def parse_listings(raw_listings: list[dict]) -> list[Listing]:
    """Parse raw 99acres listings into Listings, de-duplicated by PROP_ID."""
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

SEARCH_PAGE = (
    f"{SITE_URL}/search/property/rent/bangalore"
    f"?city={CITY_ID}&preference=R&area_unit=1&res_com=R"
    f"&property_type={PROPERTY_TYPES}&bedroom_num={BHK_TYPES}"
)

# Pull the SRP property tuples out of the hydrated Redux-ish SSR blob.
_EXTRACT_SRP_JS = """() => {
  const d = window.__initialData__;
  if (!d || !d.srp) return null;
  let properties = null;
  const stack = [d.srp];
  while (stack.length) {
    const cur = stack.pop();
    if (!cur || typeof cur !== 'object') continue;
    if (Array.isArray(cur) && cur[0] && cur[0].PROP_ID) { properties = cur; break; }
    if (!Array.isArray(cur)) for (const v of Object.values(cur)) stack.push(v);
  }
  return {
    properties: properties || [],
    pagination: d.pagination || null,
    isLast: !!(d.srp && d.srp.isLastpage),
  };
}"""


def fetch_page(client: httpx.Client, page_number: int = 1,
               budget_min: int = 0, budget_max: int = 150000) -> dict:
    """Fetch one results page via the JSON API; {} on any network/parse error."""
    try:
        return get_json(client, SEARCH_API, {
            "city": CITY_ID,
            "preference": "R",
            "area_unit": "1",
            "res_com": "R",
            "property_type": PROPERTY_TYPES,
            "bedroom_num": BHK_TYPES,
            "budget_min": str(budget_min),
            "budget_max": str(budget_max),
            "page": str(page_number),
            "page_size": str(PAGE_SIZE),
            "platform": "DESKTOP",
            "moduleName": "GRAILS_SRP",
            "workflow": "GRAILS_SRP",
        })
    except (httpx.HTTPError, ValueError) as e:
        print(f"  [!] Error page {page_number}: {e}")
        return {}


# How long to leave Chrome open for a human to clear Akamai/captcha when SSR
# hydration stalls (common around page 6+). Browser runs headed, so this is usable.
CAPTCHA_WAIT_MS = 180_000
PAGE_LOAD_TIMEOUT_MS = 90_000
SRP_HYDRATE_TIMEOUT_MS = 45_000
# Pause between pages; Akamai often trips if we hammer &page=N too fast.
INTER_PAGE_SLEEP_S = 3.0


def _save_page(pages_dir: Optional[Path], page_number: int, page: dict) -> None:
    if not pages_dir:
        return
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / f"acres99_page{page_number}.json").write_text(json.dumps(page, indent=2))


def _env_value(name: str) -> str:
    """`$NAME` from the environment, else the same key in the gitignored `.env`."""
    value = os.environ.get(name, "").strip()
    if value or not ENV_PATH.exists():
        return value
    for line in ENV_PATH.read_text().splitlines():
        key, sep, raw = line.partition("=")
        if sep and key.strip() == name:
            return raw.strip().strip("'\"")
    return ""


def apify_token() -> str:
    return _env_value("APIFY_TOKEN")


def is_apify_item(raw: dict) -> bool:
    """True for Apify listing rows (skips the run-summary object in the dataset)."""
    return isinstance(raw, dict) and bool(raw.get("spid")) and not raw.get("_type")


def _area_sqft_from_apify(item: dict) -> int:
    area = parse_int(item.get("area_sqft"))
    url = str(item.get("listing_url") or "")
    url_match = re.search(r"(\d+)\s*-?\s*sq\.?ft", url, re.I)
    url_area = parse_int(url_match.group(1)) if url_match else 0
    # Prefer the URL figure when Apify's area looks like sq.m mislabelled as sqft.
    if url_area >= 200 and (area < 200 or area < url_area * 0.5):
        return url_area
    return area if area > 0 else url_area


def apify_to_srp(item: dict) -> Optional[dict]:
    """Map one Apify 99acres record onto the SRP dict shape `normalize_listing` expects."""
    if not is_apify_item(item):
        return None
    amenities = item.get("amenities") or []
    amenity_codes_csv = ",".join(
        AMENITY_CODES[name] for name in sorted(_amenity_names_from_text(amenities))
        if name in AMENITY_CODES
    )
    facing = _facing_from_amenity_text(amenities)
    posted_ms = _parse_posted_on_ms(item.get("posted_on"))
    return {
        "PROP_ID": str(item.get("spid") or "").strip(),
        "MIN_PRICE": item.get("price"),
        "BEDROOM_NUM": item.get("bhk"),
        "AREA": _area_sqft_from_apify(item),
        "SOCIETY_NAME": item.get("society") or "",
        "LOCALITY": item.get("locality") or "",
        "MAP_DETAILS": {
            "LATITUDE": item.get("latitude"),
            "LONGITUDE": item.get("longitude"),
            "SOURCE": "PROJECT",
            "MAP_ACCURACY": "1",
        },
        "FLOOR_NUM": item.get("floor"),
        "TOTAL_FLOOR": item.get("total_floors"),
        "FURNISH": item.get("furnishing"),
        "FACING": facing,
        "AGE": item.get("age_years"),
        "PD_URL": item.get("listing_url") or "",
        "PROP_HEADING": item.get("title") or "",
        "MEDIUM_PHOTO_URL": item.get("photo_url") or "",
        "AMENITIES": amenity_codes_csv,
        "amenities": amenities,  # keep text for lift/parking fallbacks
        "POSTING_DATE": posted_ms or 0,
        "GATED": "Y" if "security" in _amenity_names_from_text(amenities) else "",
    }


def fetch_all_via_apify(budget_min: int = 0, budget_max: int = 150000, max_pages: int = 50,
                        pages_dir: Optional[Path] = None, token: str = "") -> list[dict]:
    """Run the Apify 99acres actor and return SRP-shaped dicts.

    Requires `pip install apify-client` (optional extra `acres99-apify`) and a
    non-empty `APIFY_TOKEN`. Saves results as `acres99_page*.json` under `pages_dir`.
    """
    token = token or apify_token()
    if not token:
        return []
    try:
        from apify_client import ApifyClient
    except ImportError as e:
        raise SystemExit(
            "APIFY_TOKEN is set but apify-client is not installed:\n"
            "  pip install 'rental-lookup[acres99-apify]'\n"
            "Then re-run: rental-map-fetch 99acres"
        ) from e

    override = _env_value("APIFY_MAX_RESULTS")
    try:
        requested = max(1, int(override)) if override else max(1, max_pages * PAGE_SIZE)
    except ValueError:
        requested = max(1, max_pages * PAGE_SIZE)
    max_results = min(requested, APIFY_MAX_RESULTS_CAP)
    if requested > APIFY_MAX_RESULTS_CAP:
        print(f"  [!] APIFY_MAX_RESULTS={requested} exceeds actor cap; using {APIFY_MAX_RESULTS_CAP}")
    run_input = {
        "city": "Bangalore",
        "listingType": "rent",
        "bhk": BHK_TYPES,
        "minPrice": budget_min,
        "maxPrice": budget_max,
        "maxResults": max_results,
        "allowResidentialFallback": True,
    }
    print(f"  Apify {APIFY_ACTOR}: up to {max_results} listings "
          f"(~${max_results * 0.002:.2f} if all charged)...")
    client = ApifyClient(token)
    run = client.actor(APIFY_ACTOR).call(run_input=run_input)
    if not run or run.get("status") != "SUCCEEDED":
        print(f"  [!] Apify run status: {(run or {}).get('status')}")
        return []

    adapted: list[dict] = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        srp = apify_to_srp(item)
        if srp and prop_id(srp):
            adapted.append(srp)

    if pages_dir is not None:
        pages_dir.mkdir(parents=True, exist_ok=True)
        for stale in pages_dir.glob("acres99_page*.json"):
            stale.unlink()
        for index in range(0, len(adapted), PAGE_SIZE):
            chunk = adapted[index:index + PAGE_SIZE]
            _save_page(pages_dir, index // PAGE_SIZE + 1, {"properties": chunk, "source": "apify"})

    print(f"  Apify delivered {len(adapted)} listings")
    return adapted


def _parse_cookie_header(cookie: str) -> list[dict]:
    """Turn a raw `Cookie` request-header value into Playwright cookie dicts."""
    cookies = []
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": ".99acres.com",
            "path": "/",
        })
    return cookies


def _resume_from_saved(pages_dir: Optional[Path]) -> tuple[list[dict], int]:
    """Load already-saved pages so a stalled run can continue past page N."""
    if not pages_dir or not pages_dir.exists():
        return [], 1
    raw_listings: list[dict] = []
    next_page = 1
    for page_path in sorted(pages_dir.glob("acres99_page*.json")):
        match = re.fullmatch(r"acres99_page(\d+)\.json", page_path.name)
        if not match:
            continue
        page_number = int(match.group(1))
        with open(page_path) as f:
            page = json.load(f)
        raw_listings.extend(page_properties(page))
        next_page = max(next_page, page_number + 1)
    return raw_listings, next_page


def fetch_all_via_api(budget_min: int = 0, budget_max: int = 150000, max_pages: int = 50,
                      pages_dir: Optional[Path] = None, cookie: str = "") -> list[dict]:
    """JSON API fetch. Returns [] when the first page is empty/blocked."""
    raw_listings: list[dict] = []
    headers = dict(REQUEST_HEADERS)
    if cookie:
        headers["Cookie"] = cookie
    with httpx.Client(follow_redirects=True, timeout=20, headers=headers) as client:
        for page_number in range(1, max_pages + 1):
            print(f"  99acres page {page_number}...")
            page = fetch_page(client, page_number, budget_min, budget_max)
            results = page_properties(page)
            if not results:
                break
            raw_listings.extend(results)
            _save_page(pages_dir, page_number, page)
            time.sleep(1)
    return raw_listings


def _wait_for_srp(page, timeout_ms: int) -> None:
    page.wait_for_function(
        "() => window.__initialData__ && window.__initialData__.srp",
        timeout=timeout_ms,
    )


def _load_srp_page(page, url: str) -> Optional[dict]:
    """Navigate to one SSR search URL and return extracted SRP data, or None."""
    for attempt in range(1, 4):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
            _wait_for_srp(page, SRP_HYDRATE_TIMEOUT_MS)
            page.wait_for_timeout(800)
            data = page.evaluate(_EXTRACT_SRP_JS)
            if data:
                return data
        except Exception as e:
            print(f"  [!] attempt {attempt}/3: {type(e).__name__}: {e}")
            time.sleep(2 * attempt)

    # Akamai / captcha often appears here (frequently around page 6). Chrome is
    # headed — give the user time to clear the challenge, then keep going.
    print(
        f"  [!] SSR still blocked. If Chrome shows a captcha/challenge, solve it "
        f"within {CAPTCHA_WAIT_MS // 1000}s — waiting..."
    )
    try:
        _wait_for_srp(page, CAPTCHA_WAIT_MS)
        page.wait_for_timeout(800)
        return page.evaluate(_EXTRACT_SRP_JS)
    except Exception as e:
        print(f"  [!] captcha wait failed: {type(e).__name__}: {e}")
        return None


def fetch_all_via_browser(budget_min: int = 0, budget_max: int = 150000, max_pages: int = 50,
                          pages_dir: Optional[Path] = None, cookie: str = "") -> list[dict]:
    """Load SSR search pages in Chrome and read `window.__initialData__`.

    Requires the optional `playwright` package and a local Chrome install
    (`playwright install` is not needed when using `channel='chrome'`).
    Resumes from `acres99_page*.json` already in `pages_dir`. Passes `cookie`
    into the browser context when provided. On mid-run blocks, waits for a
    human to clear the challenge in the visible Chrome window.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit(
            "99acres JSON API is blocked; install Playwright to scrape SSR pages:\n"
            "  pip install playwright\n"
            "Then re-run: rental-map-fetch 99acres"
        ) from e

    raw_listings, start_page = _resume_from_saved(pages_dir)
    if start_page > 1:
        print(f"  resuming Chrome SSR from page {start_page} "
              f"({len(raw_listings)} listings already saved)")
    base = f"{SEARCH_PAGE}&budget_min={budget_min}&budget_max={budget_max}"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context()
        if cookie:
            context.add_cookies(_parse_cookie_header(cookie))
        page = context.new_page()
        try:
            for page_number in range(start_page, max_pages + 1):
                print(f"  99acres page {page_number}...")
                data = _load_srp_page(page, f"{base}&page={page_number}")
                if not data:
                    break
                results = page_properties({"properties": data.get("properties") or []})
                if not results:
                    break
                raw_listings.extend(results)
                _save_page(
                    pages_dir,
                    page_number,
                    {"properties": results, "pagination": data.get("pagination")},
                )
                if data.get("isLast") or len(results) < 10:
                    break
                time.sleep(INTER_PAGE_SLEEP_S)
        finally:
            browser.close()
    return raw_listings


def fetch_all(budget_min: int = 0, budget_max: int = 150000, max_pages: int = 50,
              pages_dir: Optional[Path] = None, cookie: str = "") -> list[dict]:
    """Fetch result pages until one comes back empty; returns SRP-shaped dicts.

    Prefers Apify when `APIFY_TOKEN` is set; otherwise JSON API (optional `cookie`),
    then Chrome SSR.
    """
    raw_listings: list[dict] = []
    if apify_token():
        print("  trying Apify...")
        raw_listings = fetch_all_via_apify(
            budget_min=budget_min, budget_max=budget_max, max_pages=max_pages,
            pages_dir=pages_dir,
        )
    if not raw_listings:
        print("  trying JSON API...")
        raw_listings = fetch_all_via_api(
            budget_min=budget_min, budget_max=budget_max, max_pages=max_pages,
            pages_dir=pages_dir, cookie=cookie,
        )
    if not raw_listings:
        print("  JSON API empty/blocked; falling back to Chrome SSR...")
        raw_listings = fetch_all_via_browser(
            budget_min=budget_min, budget_max=budget_max, max_pages=max_pages,
            pages_dir=pages_dir, cookie=cookie,
        )
    pages_fetched = len(list(pages_dir.glob("acres99_page*.json"))) if pages_dir and pages_dir.exists() else 0
    print(f"  99acres total: {len(raw_listings)} raw listings across {pages_fetched or '?'} pages")
    return raw_listings
