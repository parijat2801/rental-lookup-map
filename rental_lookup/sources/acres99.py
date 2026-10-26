"""99acres: fetch rental listings and normalise them to `Listing`.

Primary: SSR HTML search pages expose `window.__initialData__` (loaded in Chrome
via Playwright). The JSON API (`/api-aggregator/srp/search`) now returns 401/403
for non-browser clients, so httpx is only tried first and abandoned on failure.
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
    """Epoch milliseconds from POSTING_DATE / POSTING_DATE__U, or None."""
    value = _get(raw, "POSTING_DATE", "posting_date", "POSTING_DATE__U", "posting_date__u")
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
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
    return {name for name, code in AMENITY_CODES.items() if code in codes}


def parse_coords(raw: dict) -> Optional[tuple[float, float]]:
    """Property coordinates from MAP_DETAILS (and a top-level `location` fallback).

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
    bedrooms = parse_int(_get(raw, "BEDROOM_NUM", "bedroom_num"))
    return f"BHK{bedrooms}" if bedrooms > 0 else ""


def _parse_floor(raw: dict) -> int:
    floor = _get(raw, "FLOOR_NUM", "floor_num")
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
        return ""
    key = re.sub(r"\s+", "", str(facing).strip().lower())
    return FACING_CODES.get(str(facing).strip(), FACING_CODES.get(key, ""))


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
    if not amenity_codes(raw):
        return None
    return "lift" in amenities


def _parse_age_years(raw: dict) -> int:
    age = _get(raw, "AGE", "age")
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
                "SUPERBUILTUP_SQFT", "superbuiltup_sqft", "SUPER_SQFT", "super_sqft"):
        value = parse_int(_get(raw, key))
        if value > 50:  # skip sq.m values mistakenly labelled as sqft
            return value
    area = str(_get(raw, "AREA", "area") or "")
    match = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:sq\.?\s*ft|sqft)", area, re.I)
    if match:
        return parse_int(match.group(1))
    return parse_int(re.search(r"[\d,]+", area).group()) if re.search(r"[\d,]+", area) else 0


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
    """Convert a raw 99acres SRP item to a Listing; None if unusable."""
    coords = parse_coords(raw)
    rent = parse_int(_get(raw, "MIN_PRICE", "min_price", "MAX_PRICE", "max_price"))
    if not coords or rent <= 0 or not prop_id(raw):
        return None

    lat, lng = coords
    amenities = amenity_names(raw)
    parking = _parse_parking(raw, amenities)
    photos = photo_urls(raw, max_photos=1)
    society = str(_get(raw, "SOCIETY_NAME", "society_name", "BUILDING_NAME", "building_name",
                       "PROP_NAME", "prop_name") or "").strip()
    locality = str(_get(raw, "LOCALITY_WO_CITY", "locality_wo_city", "LOCALITY", "locality") or "").strip()
    locality = locality.split(",")[0].strip()
    has_security = "security" in amenities
    gated = str(_get(raw, "GATED", "gated") or "").upper() in ("Y", "YES", "TRUE", "1")

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
        total_floors=parse_int(_get(raw, "TOTAL_FLOOR", "total_floor")),
        has_lift=_parse_has_lift(raw, amenities),
        parking=parking,
        title=str(_get(raw, "PROP_HEADING", "prop_heading", "PROP_NAME", "prop_name") or ""),
        url=listing_url(raw),
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


def _save_page(pages_dir: Optional[Path], page_number: int, page: dict) -> None:
    if not pages_dir:
        return
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / f"acres99_page{page_number}.json").write_text(json.dumps(page, indent=2))


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


def fetch_all_via_browser(budget_min: int = 0, budget_max: int = 150000, max_pages: int = 50,
                          pages_dir: Optional[Path] = None) -> list[dict]:
    """Load SSR search pages in Chrome and read `window.__initialData__`.

    Requires the optional `playwright` package and a local Chrome install
    (`playwright install` is not needed when using `channel='chrome'`).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit(
            "99acres JSON API is blocked; install Playwright to scrape SSR pages:\n"
            "  pip install playwright\n"
            "Then re-run: rental-map-fetch 99acres"
        ) from e

    raw_listings: list[dict] = []
    base = (
        f"{SEARCH_PAGE}&budget_min={budget_min}&budget_max={budget_max}"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        page = browser.new_page()
        try:
            for page_number in range(1, max_pages + 1):
                print(f"  99acres page {page_number}...")
                url = f"{base}&page={page_number}"
                data = None
                for attempt in range(1, 4):
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=90000)
                        page.wait_for_function(
                            "() => window.__initialData__ && window.__initialData__.srp",
                            timeout=45000,
                        )
                        page.wait_for_timeout(800)
                        data = page.evaluate(_EXTRACT_SRP_JS)
                        break
                    except Exception as e:
                        print(f"  [!] attempt {attempt}/3: {type(e).__name__}: {e}")
                        time.sleep(2 * attempt)
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
                time.sleep(1.2)
        finally:
            browser.close()
    return raw_listings


def fetch_all(budget_min: int = 0, budget_max: int = 150000, max_pages: int = 50,
              pages_dir: Optional[Path] = None, cookie: str = "") -> list[dict]:
    """Fetch result pages until one comes back empty; returns raw dicts.

    Tries the JSON API first; on block/empty first page, falls back to Chrome SSR.
    `cookie` only applies to the API path.
    """
    print("  trying JSON API...")
    raw_listings = fetch_all_via_api(
        budget_min=budget_min, budget_max=budget_max, max_pages=max_pages,
        pages_dir=pages_dir, cookie=cookie,
    )
    if not raw_listings:
        print("  JSON API empty/blocked; falling back to Chrome SSR...")
        raw_listings = fetch_all_via_browser(
            budget_min=budget_min, budget_max=budget_max, max_pages=max_pages,
            pages_dir=pages_dir,
        )
    pages_fetched = len(list(pages_dir.glob("acres99_page*.json"))) if pages_dir and pages_dir.exists() else 0
    print(f"  99acres total: {len(raw_listings)} raw listings across {pages_fetched or '?'} pages")
    return raw_listings
