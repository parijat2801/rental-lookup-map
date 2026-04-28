"""Rebuild output/map.html from data/raw/, data/raw_mb/, and data/cache/"""
import json, glob, time
from collections import Counter
from pathlib import Path

print("Building map...")

# Load stars and dismissals
stars_data = {}
stars_path = Path("data/cache/stars_and_dismissals.json")
if stars_path.exists():
    with open(stars_path) as f:
        stars_data = json.load(f)
    starred_urls = stars_data.get('starred', {})
    dismissed_urls = stars_data.get('dismissed', {})
    print(f"  Stars: {len(starred_urls)} starred, {len(dismissed_urls)} dismissed")
else:
    starred_urls = {}
    dismissed_urls = {}

# Load first_seen dates (when WE first saw each listing, not platform dates)
first_seen = {}
first_seen_path = Path('data/cache/first_seen.json')
if first_seen_path.exists():
    with open(first_seen_path) as f:
        first_seen = json.load(f)
    print(f'  First seen: {len(first_seen)} listings tracked')

from datetime import date
today = str(date.today())

# Load photo ratings
photo_ratings = {}
ratings_path = Path("data/cache/photo_ratings.json")
if ratings_path.exists():
    with open(ratings_path) as f:
        photo_ratings = json.load(f)
    print(f"  Photo ratings: {len(photo_ratings)} listings")

# Load fake location IDs
fake_ids = set()
fake_path = Path("data/cache/fake_location_ids.json")
if fake_path.exists():
    with open(fake_path) as f:
        fake_ids = set(json.load(f))
    print(f"  Fake locations: {len(fake_ids)} listings")

# Load previous listing IDs to detect delisted ones
prev_dir = Path("data/raw_prev")
prev_listings = {}  # id -> basic info
if prev_dir.exists():
    for f in sorted(prev_dir.glob("*.json")):
        with open(f) as fh:
            d = json.load(fh)
        for item in d.get('data', []):
            pid = item['id']
            if pid not in prev_listings:
                prev_listings[pid] = item
    print(f"  Previous data: {len(prev_listings)} listings")

# Load enrichment
enrichment = {}
enrich_path = Path("data/cache/detail_enrichment.json")
if enrich_path.exists():
    with open(enrich_path) as f:
        enrichment = json.load(f)

from rental_lookup.models import BRANDED_BUILDERS as brands

def get_photo_url(item):
    pid = item['id']
    for p in item.get('photos', [])[:1]:
        if isinstance(p, dict):
            fname = p.get('imagesMap', {}).get('medium') or p.get('imagesMap', {}).get('large', '')
            if fname: return f'https://assets.nobroker.in/images/{pid}/{fname}'
    thumb = item.get('thumbnailImage', '')
    if thumb and 'static/img' not in thumb: return thumb
    return ''

def get_all_photo_urls(item, max_photos=5):
    pid = item['id']
    urls = []
    for p in item.get('photos', [])[:max_photos]:
        if isinstance(p, dict):
            fname = p.get('imagesMap', {}).get('medium') or p.get('imagesMap', {}).get('large', '')
            if fname: urls.append(f'https://assets.nobroker.in/images/{pid}/{fname}')
    return urls

# Detect stacked coords
coord_counts = Counter()
for f in sorted(glob.glob('data/raw/*.json')):
    with open(f) as fh:
        d = json.load(fh)
    for item in d.get('data', []):
        lat, lng = item.get('latitude'), item.get('longitude')
        if lat and lng:
            coord_counts[(round(lat, 4), round(lng, 4))] += 1
stacked_coords = {k for k, v in coord_counts.items() if v > 3}

# Also detect stacked MB coordinates
mb_dir_check = Path('data/raw_mb')
if mb_dir_check.exists():
    for f in sorted(mb_dir_check.glob('*.json')):
        with open(f) as fh:
            d = json.load(fh)
        for item in d.get('resultList', []):
            lat_lng = item.get('ltcoordGeo', '')
            if lat_lng and ',' in lat_lng:
                parts = lat_lng.split(',')
                try:
                    lat, lng = float(parts[0].strip()), float(parts[1].strip())
                    coord_counts[(round(lat, 4), round(lng, 4))] += 1
                except (ValueError, IndexError):
                    pass
    stacked_coords = {k for k, v in coord_counts.items() if v > 3}
    print(f'  Stacked coords (NB+MB): {len(stacked_coords)} locations')

now_ms = time.time() * 1000
results = []
seen = set()
for f in sorted(glob.glob('data/raw/*.json')):
    with open(f) as fh:
        d = json.load(fh)
    for item in d.get('data', []):
        if item['id'] in seen: continue
        seen.add(item['id'])
        rent = item.get('rent', 0)
        if rent < 0 or rent > 150000: continue
        sqft = item.get('propertySize', 0)
        if sqft < 500: continue
        lat, lng = item.get('latitude'), item.get('longitude')
        if not lat or not lng: continue
        amenities = item.get('amenitiesMap', {}) or {}
        score_data = item.get('score') or {}
        photos = item.get('photos', [])
        img = item.get('originalImageUrl', '')
        society = item.get('society', '')
        facing = item.get('facing', '') or ''
        balconies = item.get('balconies') if item.get('balconies') is not None else -1
        nb_transit = score_data.get('transit', 0) if isinstance(score_data, dict) else 0
        nb_lifestyle = score_data.get('lifestyle', 0) if isinstance(score_data, dict) else 0
        enrich = enrichment.get(item['id'], {})
        maint_amount = enrich.get('maintenanceAmount') or 0
        if not isinstance(maint_amount, (int, float)): maint_amount = 0
        total_cost = rent + maint_amount
        description = enrich.get('description', '')
        desc_lower = description.lower()
        pet_friendly = bool(any(w in desc_lower for w in ['pet-friendly','pet friendly','pets allowed','pets welcome']))
        act = item.get('activationDate', 0)
        # Use first_seen date (when WE first saw it) instead of platform date
        nb_url = 'https://www.nobroker.in' + item.get('detailUrl', '')
        if nb_url not in first_seen:
            first_seen[nb_url] = today
        try:
            fs_date = date.fromisoformat(first_seen[nb_url])
            days_ago = (date.today() - fs_date).days
        except (ValueError, TypeError):
            days_ago = 0
        key = (round(lat, 4), round(lng, 4))
        soc_title = (society + ' ' + item.get('propertyTitle', '')).lower()

        results.append({
            'lat': lat, 'lng': lng,
            'rent': rent, 'maint': maint_amount, 'totalCost': total_cost,
            'deposit': item.get('deposit', 0), 'sqft': sqft,
            'bhk': item.get('type', ''), 'society': society,
            'locality': item.get('locality', ''), 'facing': facing,
            'balconies': balconies, 'floor': item.get('floor', 0),
            'totalFloor': item.get('totalFloor', 0),
            'lift': item.get('lift', False) or amenities.get('LIFT', False),
            'age': item.get('propertyAge', 99),
            'bt': item.get('buildingType', ''),
            'parking': item.get('parking', 'NONE'),
            'negotiable': item.get('negotiable', False),
            'water': item.get('waterSupply', ''),
            'nbT': nb_transit, 'nbL': nb_lifestyle,
            'pb': amenities.get('PB', False), 'gp': amenities.get('GP', False),
            'sec': amenities.get('SECURITY', False), 'fs': amenities.get('FS', False),
            'pool': amenities.get('POOL', False), 'gym': amenities.get('GYM', False),
            'club': amenities.get('CLUB', False), 'park': amenities.get('PARK', False),
            'intercom': amenities.get('INTERCOM', False), 'cpa': amenities.get('CPA', False),
            'photoCount': len(photos), 'hasRealPhoto': bool(img) and 'static/img' not in img,
            'isBrand': any(b in soc_title for b in brands),
            'petFriendly': pet_friendly,
            'cupboard': enrich.get('cupBoard') or 0,
            'street': (enrich.get('completeStreetName') or '')[:80],
            'availFrom': enrich.get('availableFrom', ''),
            'propCode': enrich.get('propertyCode', ''),
            'desc': description[:200].replace('"', '\\"').replace('\n', ' '),
            'stacked': key in stacked_coords,
            'fake': item['id'] in fake_ids,
            'rated': item['id'] in photo_ratings,
            'pr': photo_ratings.get(item['id'], {}),
            'daysAgo': days_ago,
            'img': get_photo_url(item),
            'imgs': get_all_photo_urls(item),
            'url': 'https://www.nobroker.in' + item.get('detailUrl', ''),
        })

# Load MagicBricks data and merge unique listings
mb_dir = Path("data/raw_mb")
if mb_dir.exists() and any(mb_dir.glob("*.json")):
    from rental_lookup.magicbricks import normalize_listing as mb_normalize, dedupe_cross_platform
    def _mb_first_seen_days(url):
        if url not in first_seen:
            first_seen[url] = today
        try:
            fs_date = date.fromisoformat(first_seen[url])
            return (date.today() - fs_date).days
        except (ValueError, TypeError):
            return 0
    from rental_lookup.models import Listing

    mb_raw = []
    for f in sorted(mb_dir.glob("*.json")):
        with open(f) as fh:
            d = json.load(fh)
        mb_raw.extend(d.get('resultList', []))

    # Parse MB listings
    mb_seen = set()
    mb_listings = []
    for raw in mb_raw:
        mb_id = f"mb_{raw.get('id', '')}"
        if mb_id in mb_seen:
            continue
        mb_seen.add(mb_id)
        listing = mb_normalize(raw)
        if listing:
            mb_listings.append((listing, raw))

    # Simple dedup: check if rent+sqft+bhk+locality combo already exists in NB results
    nb_sigs = set()
    for r in results:
        sig = f"{r['rent']}_{r['sqft']}_{r['bhk']}_{r['locality'].lower().split(',')[0].strip()}"
        nb_sigs.add(sig)

    mb_added = 0
    for listing, raw in mb_listings:
        sig = f"{listing.rent}_{listing.sqft}_{listing.bhk}_{listing.locality.lower().strip()}"
        if sig in nb_sigs:
            continue

        # Get photos from MB
        all_imgs = raw.get('allImgPath', [])
        imgs = [img for img in all_imgs[:10] if isinstance(img, str)] if isinstance(all_imgs, list) else []

        key = (round(listing.lat, 4), round(listing.lng, 4))
        results.append({
            'lat': listing.lat, 'lng': listing.lng,
            'rent': listing.rent, 'maint': int(raw.get('maintenanceCharges', 0) or 0),
            'totalCost': listing.rent + int(raw.get('maintenanceCharges', 0) or 0),
            'deposit': listing.deposit, 'sqft': listing.sqft,
            'bhk': listing.bhk, 'society': listing.society,
            'locality': listing.locality, 'facing': listing.facing,
            'balconies': listing.balconies, 'floor': listing.floor,
            'totalFloor': listing.total_floor,
            'lift': listing.lift, 'age': listing.age,
            'bt': listing.building_type,
            'parking': listing.parking,
            'negotiable': False,
            'water': listing.water_supply,
            'nbT': 0, 'nbL': 0,
            'pb': listing.has_power_backup, 'gp': listing.has_gated_community,
            'sec': listing.has_security, 'fs': listing.has_fire_safety,
            'pool': '12205' in str(raw.get('amenities', '')),
            'gym': '12204' in str(raw.get('amenities', '')),
            'club': '12206' in str(raw.get('amenities', '')),
            'park': '12209' in str(raw.get('amenities', '')),
            'intercom': '12214' in str(raw.get('amenities', '')),
            'cpa': listing.has_covered_parking,
            'photoCount': int(raw.get('imgCt', 0) or 0),
            'hasRealPhoto': len(imgs) > 0,
            'isBrand': False,
            'petFriendly': False,
            'cupboard': 0,
            'street': raw.get('psmAdd', '')[:80],
            'availFrom': raw.get('possStatusD', ''),
            'propCode': '',
            'desc': raw.get('auto_desc', '')[:200].replace('"', '\\"').replace('\n', ' '),
            'stacked': key in stacked_coords,
            'fake': False,
            'rated': False,
            'pr': {},
            'daysAgo': _mb_first_seen_days(listing.url),
            'delisted': False,
            'img': imgs[0] if imgs else (raw.get('image', '') or ''),
            'imgs': imgs,
            'url': listing.url,
            'source': 'mb',
        })
        mb_added += 1

    print(f"  MagicBricks: {len(mb_listings)} parsed, {mb_added} unique added to map")

# Mark NoBroker listings with source + embed stars
for r in results:
    if 'source' not in r:
        r['source'] = 'nb'
    url = r.get('url', '')
    if url in starred_urls:
        r['_starred'] = starred_urls[url]
    if url in dismissed_urls:
        r['_dismissed'] = dismissed_urls[url]

# Add delisted listings (were in prev, not in current)
current_ids = seen  # 'seen' set from the NB loop above has all current NB IDs

delisted_count = 0
if prev_listings:
    for pid, item in prev_listings.items():
        if pid in current_ids:
            continue  # still active
        rent = item.get('rent', 0)
        if rent < 0 or rent > 150000: continue
        sqft = item.get('propertySize', 0)
        if sqft < 500: continue
        lat, lng = item.get('latitude'), item.get('longitude')
        if not lat or not lng: continue

        amenities = item.get('amenitiesMap', {}) or {}
        society = item.get('society', '')
        results.append({
            'lat': lat, 'lng': lng,
            'rent': rent, 'maint': 0, 'totalCost': rent,
            'deposit': item.get('deposit', 0), 'sqft': sqft,
            'bhk': item.get('type', ''), 'society': society,
            'locality': item.get('locality', ''), 'facing': item.get('facing', '') or '',
            'balconies': item.get('balconies') if item.get('balconies') is not None else -1,
            'floor': item.get('floor', 0), 'totalFloor': item.get('totalFloor', 0),
            'lift': item.get('lift', False), 'age': item.get('propertyAge', 99),
            'bt': item.get('buildingType', ''), 'parking': item.get('parking', 'NONE'),
            'negotiable': False, 'water': item.get('waterSupply', ''),
            'nbT': 0, 'nbL': 0,
            'pb': amenities.get('PB', False), 'gp': amenities.get('GP', False),
            'sec': amenities.get('SECURITY', False), 'fs': amenities.get('FS', False),
            'pool': amenities.get('POOL', False), 'gym': amenities.get('GYM', False),
            'club': amenities.get('CLUB', False), 'park': amenities.get('PARK', False),
            'intercom': amenities.get('INTERCOM', False), 'cpa': amenities.get('CPA', False),
            'photoCount': len(item.get('photos', [])),
            'hasRealPhoto': bool(item.get('originalImageUrl', '')) and 'static/img' not in item.get('originalImageUrl', ''),
            'isBrand': False, 'petFriendly': False,
            'cupboard': 0, 'street': '', 'availFrom': '', 'propCode': '',
            'desc': '', 'stacked': False, 'daysAgo': -1,
            'img': get_photo_url(item),
            'url': 'https://www.nobroker.in' + item.get('detailUrl', ''),
            'delisted': True,
        })
        delisted_count += 1

    print(f"  Delisted listings added: {delisted_count}")

# Mark current listings as not delisted
for r in results:
    if 'delisted' not in r:
        r['delisted'] = False

# Save updated first_seen
with open(first_seen_path, 'w') as f:
    json.dump(first_seen, f)
print(f'  First seen saved: {len(first_seen)} listings')

# Clean HTML entities that break JS JSON parsing
import html as html_module
data_json = json.dumps(results, separators=(',', ':'))
data_json = html_module.unescape(data_json)

# Read the existing map.html as template (it has all the JS/CSS)
with open('output/map_template.html') as f:
    template = f.read()

# Replace the data
start = template.index('var ALL = ') + len('var ALL = ')
end = template.index(';\nvar map =')
html = template[:start] + data_json + template[end:]

with open('output/map.html', 'w') as f:
    f.write(html)

print(f"Map built with {len(results)} listings")
