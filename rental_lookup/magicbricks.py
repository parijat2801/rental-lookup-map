"""
MagicBricks scraper — fetches rental listings and normalizes to our Listing format.
API: GET https://www.magicbricks.com/mbsrp/propertySearch.html (returns JSON, no auth)
"""

import json
import time
from pathlib import Path
from typing import List, Optional

import httpx

from rental_lookup.models import Listing

MB_API = "https://www.magicbricks.com/mbsrp/propertySearch.html"
CITY = "Bangalore"
PAGE_SIZE = 30

# MagicBricks bedroom codes: just use "2,3"
BHK_TYPES = "2,3"
# Property types: 10002=Apartment, 10003=Builder Floor, 10021=Penthouse, 10022=Studio
PROP_TYPES = "10002,10003,10021,10022"


def normalize_listing(raw: dict) -> Optional[Listing]:
    """Convert a MagicBricks listing to our Listing format."""
    lat_lng = raw.get('ltcoordGeo', '')
    if lat_lng and ',' in lat_lng:
        parts = lat_lng.split(',')
        try:
            lat = float(parts[0].strip())
            lng = float(parts[1].strip())
        except (ValueError, IndexError):
            lat, lng = 0, 0
    else:
        lat = float(raw.get('pmtLat', 0) or 0)
        lng = float(raw.get('pmtLong', 0) or 0)

    if not lat or not lng or lat == 0 or lng == 0:
        return None

    rent = int(raw.get('price', 0) or 0)
    if rent <= 0:
        return None

    sqft = int(raw.get('carpetArea', 0) or raw.get('coveredArea', 0) or 0)
    deposit = int(raw.get('bookingAmtExact', 0) or 0)

    # BHK
    bedroom_d = raw.get('bedroomD', '')
    if '3' in str(bedroom_d):
        bhk = 'BHK3'
    elif '2' in str(bedroom_d):
        bhk = 'BHK2'
    elif '4' in str(bedroom_d):
        bhk = 'BHK4'
    elif '1' in str(bedroom_d):
        bhk = 'BHK1'
    else:
        bhk = ''

    # Floor
    floor_raw = raw.get('floorNo', 0)
    if str(floor_raw).lower() in ('ground', 'g', 'lower basement', 'upper basement'):
        floor = 0
    else:
        try:
            floor = int(floor_raw or 0)
        except (ValueError, TypeError):
            floor = 0
    try:
        total_floor = int(raw.get('floors', 0) or 0)
    except (ValueError, TypeError):
        total_floor = 0

    # Facing
    facing_map = {
        'East': 'E', 'West': 'W', 'North': 'N', 'South': 'S',
        'North-East': 'NE', 'North-West': 'NW', 'South-East': 'SE', 'South-West': 'SW',
    }
    facing = facing_map.get(raw.get('facingD', ''), '')

    # Parking
    parking_d = raw.get('parkingD', '')
    if 'Covered' in str(parking_d) or 'Car' in str(parking_d):
        parking = 'FOUR_WHEELER'
    elif 'Bike' in str(parking_d) or 'Two' in str(parking_d):
        parking = 'TWO_WHEELER'
    elif parking_d and parking_d != 'None':
        parking = 'BOTH'
    else:
        parking = 'NONE'

    # Amenities from space-separated codes
    amenity_str = str(raw.get('amenities', ''))
    # Common MB amenity codes (approximate mapping)
    # 12201=Lift, 12202=Security, 12203=Playground, 12204=Gym, 12205=Swimming Pool
    # 12206=Clubhouse, 12207=Power Backup, 12208=Gas Pipeline, 12209=Park
    # 12214=Intercom, 12215=AC, 12218=Fire Safety, 12220=Laundry
    has_lift = '12201' in amenity_str
    has_security = '12202' in amenity_str
    has_gym = '12204' in amenity_str
    has_pool = '12205' in amenity_str
    has_club = '12206' in amenity_str
    has_power_backup = '12207' in amenity_str
    has_park = '12209' in amenity_str
    has_intercom = '12214' in amenity_str
    has_fire_safety = '12218' in amenity_str

    # Society / Project name
    society = raw.get('prjname', '') or raw.get('lmtDName', '') or ''
    locality = raw.get('lmtDName', '') or ''

    # Photos
    all_imgs = raw.get('allImgPath', [])
    photo_url = ''
    if all_imgs and isinstance(all_imgs, list) and len(all_imgs) > 0:
        photo_url = all_imgs[0] if isinstance(all_imgs[0], str) else ''
    elif raw.get('image'):
        photo_url = raw.get('image', '')

    # URL
    url_path = raw.get('url', '')
    url = f"https://www.magicbricks.com/{url_path}" if url_path else ''

    # Age
    age_str = raw.get('acD', '')
    if '0 to 1' in age_str:
        age = 1
    elif '1 to 5' in age_str:
        age = 3
    elif '5 to 10' in age_str:
        age = 7
    elif '10' in age_str:
        age = 15
    else:
        age = 99

    # Water supply
    water = raw.get('waterStatus', '')
    if '24' in water:
        water_supply = 'CORPORATION'
    elif 'Borewell' in water:
        water_supply = 'BOREWELL'
    else:
        water_supply = ''

    # Balconies
    try:
        balconies = int(raw.get('balconiesD', 0) or 0)
    except (ValueError, TypeError):
        balconies = 0

    # NoBroker transit/lifestyle equivalent — MB doesn't have this
    # Use 0 so it doesn't get filtered out by our NB score check
    # We'll need to handle this in the map

    # Maintenance
    maintenance = int(raw.get('maintenanceCharges', 0) or 0)

    # Build a unique ID prefixed with 'mb_' to avoid collision with NoBroker IDs
    mb_id = f"mb_{raw.get('id', '')}"

    return Listing(
        id=mb_id,
        rent=rent,
        deposit=deposit,
        sqft=sqft,
        bhk=bhk,
        lat=lat,
        lng=lng,
        locality=locality,
        society=society,
        building_type='AP',
        floor=floor,
        total_floor=total_floor,
        lift=has_lift,
        parking=parking,
        title=raw.get('propertyTitle', ''),
        url=url,
        photo_url=photo_url,
        facing=facing,
        balconies=balconies,
        age=age,
        water_supply=water_supply,
        negotiable=False,
        nb_transit=0,
        nb_lifestyle=0,
        has_power_backup=has_power_backup,
        has_gated_community=has_security,  # MB doesn't have explicit "gated" — use security as proxy
        has_covered_parking=parking in ('FOUR_WHEELER', 'BOTH'),
        has_security=has_security,
        has_fire_safety=has_fire_safety,
        has_car_parking=parking in ('FOUR_WHEELER', 'BOTH'),
    )


def fetch_page(page: int = 1, budget_min: int = 0, budget_max: int = 150000) -> dict:
    """Fetch one page of results from MagicBricks."""
    client = httpx.Client(follow_redirects=True, timeout=15, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    })
    try:
        resp = client.get(MB_API, params={
            'editSearch': 'Y',
            'category': 'R',
            'propertyType': PROP_TYPES,
            'bedrooms': BHK_TYPES,
            'cityName': CITY,
            'budgetMin': str(budget_min),
            'budgetMax': str(budget_max),
            'page': str(page),
        })
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [!] Error page {page}: {e}")
        return {}
    finally:
        client.close()


def fetch_all(budget_min: int = 0, budget_max: int = 150000, max_pages: int = 50,
              raw_dir: Optional[Path] = None) -> List[dict]:
    """Fetch all pages of MagicBricks listings. Returns raw dicts."""
    all_raw = []
    page = 1

    while page <= max_pages:
        print(f"  MagicBricks page {page}...")
        data = fetch_page(page, budget_min, budget_max)

        results = data.get('resultList', [])
        if not results:
            break

        all_raw.extend(results)

        if raw_dir:
            raw_dir.mkdir(parents=True, exist_ok=True)
            path = raw_dir / f"magicbricks_page{page}.json"
            path.write_text(json.dumps(data, indent=2))

        page += 1
        time.sleep(1)

    print(f"  MagicBricks total: {len(all_raw)} raw listings across {page-1} pages")
    return all_raw


def parse_all(raw_listings: List[dict]) -> List[Listing]:
    """Parse raw MB listings into our Listing format, dedup by MB id."""
    seen = set()
    listings = []
    for raw in raw_listings:
        mb_id = f"mb_{raw.get('id', '')}"
        if mb_id in seen:
            continue
        seen.add(mb_id)
        listing = normalize_listing(raw)
        if listing:
            listings.append(listing)
    return listings


def dedupe_cross_platform(nb_listings: List[Listing], mb_listings: List[Listing],
                          rent_tolerance: float = 0.15, sqft_tolerance: float = 0.15) -> List[Listing]:
    """Deduplicate MB listings against NoBroker listings.

    A MB listing is a duplicate if there's a NB listing with:
    - Same locality (fuzzy)
    - Rent within 15%
    - Sqft within 15%
    - Same BHK

    Returns only the MB listings that are NOT duplicates.
    """
    # Build lookup index from NB listings
    nb_index = []
    for nb in nb_listings:
        nb_index.append({
            'locality': nb.locality.lower().split(',')[0].strip(),
            'society': nb.society.lower().strip(),
            'rent': nb.rent,
            'sqft': nb.sqft,
            'bhk': nb.bhk,
        })

    unique_mb = []
    dupes = 0

    for mb in mb_listings:
        mb_loc = mb.locality.lower().strip()
        mb_soc = mb.society.lower().strip()
        is_dupe = False

        for nb in nb_index:
            # Same BHK
            if mb.bhk != nb['bhk']:
                continue

            # Rent within tolerance
            if nb['rent'] > 0 and abs(mb.rent - nb['rent']) / nb['rent'] > rent_tolerance:
                continue

            # Sqft within tolerance
            if nb['sqft'] > 0 and mb.sqft > 0 and abs(mb.sqft - nb['sqft']) / nb['sqft'] > sqft_tolerance:
                continue

            # Locality or society match (fuzzy)
            loc_match = (mb_loc in nb['locality'] or nb['locality'] in mb_loc or
                        mb_soc in nb['society'] or nb['society'] in mb_soc)

            if loc_match:
                is_dupe = True
                dupes += 1
                break

        if not is_dupe:
            unique_mb.append(mb)

    print(f"  Cross-platform dedup: {len(mb_listings)} MB → {dupes} dupes → {len(unique_mb)} unique")
    return unique_mb


if __name__ == '__main__':
    raw_dir = Path("data/raw_mb")
    raw_listings = fetch_all(raw_dir=raw_dir)
    listings = parse_all(raw_listings)
    print(f"\nParsed {len(listings)} MagicBricks listings")

    # Show sample
    for l in listings[:5]:
        print(f"  Rs.{l.rent:,} | {l.sqft}sqft | {l.bhk} | {l.society} | {l.locality}")
        print(f"    {l.url[:80]}")
