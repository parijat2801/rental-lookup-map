#!/bin/bash
cd /Users/parijat/dev/rental-lookup

echo "=== Step 1: Backup old data + Fetch fresh from NoBroker ==="
# Move old raw data to backup (keep it safe)
if [ -d "data/raw" ] && [ "$(ls data/raw/*.json 2>/dev/null | wc -l)" -gt 0 ]; then
    rm -rf data/raw_prev
    mv data/raw data/raw_prev
    mkdir -p data/raw
fi

python3 -m rental_lookup

echo ""
echo "=== Step 2: Fetch detail enrichment for top 300 ==="
python3 -c "
import json, glob, time, urllib.request

brands = ['prestige','brigade','sobha','mantri','puravankara','salarpuria','godrej','embassy','raheja','mahaveer','nitesh','ds max','sattva','shriram','sjr','sumadhura','rohan','dnr','gopalan','purva','adarsh','century','arvind','total environment','vaishnavi','casagrand']
results = []
seen = set()
for f in sorted(glob.glob('data/raw/*.json')):
    with open(f) as fh:
        d = json.load(fh)
    for item in d.get('data', []):
        if item['id'] in seen: continue
        seen.add(item['id'])
        rent = item.get('rent', 0)
        if rent < 25000 or rent > 80000: continue
        sqft = item.get('propertySize', 0)
        if sqft < 500: continue
        if not item.get('latitude') or not item.get('longitude'): continue
        amenities = item.get('amenitiesMap', {}) or {}
        score_data = item.get('score') or {}
        s = 0
        facing = item.get('facing', '') or ''
        if facing in ('E','SE','S','NE'): s += 10
        balc = item.get('balconies', 0) or 0
        if balc > 0: s += min(balc * 4, 12)
        age = item.get('propertyAge', 99)
        if age <= 3: s += 10
        elif age <= 7: s += 7
        elif age <= 15: s += 3
        if amenities.get('PB'): s += 5
        if amenities.get('SECURITY'): s += 5
        if amenities.get('GP'): s += 4
        if amenities.get('POOL'): s += 8
        if amenities.get('GYM'): s += 5
        if amenities.get('CLUB'): s += 5
        if item.get('parking','') in ('FOUR_WHEELER','BOTH'): s += 5
        nb_t = score_data.get('transit', 0) if isinstance(score_data, dict) else 0
        nb_l = score_data.get('lifestyle', 0) if isinstance(score_data, dict) else 0
        if nb_t >= 8: s += 5
        elif nb_t >= 7: s += 3
        if nb_l >= 8: s += 8
        elif nb_l >= 6: s += 4
        if item.get('negotiable'): s += 3
        if len(item.get('photos',[])) >= 5: s += 3
        soc_title = (item.get('society','') + ' ' + item.get('propertyTitle','')).lower()
        if any(b in soc_title for b in brands): s += 8
        results.append({'id': item['id'], 'score': s})

results.sort(key=lambda x: -x['score'])
top300_ids = set(r['id'] for r in results[:300])

try:
    with open('data/cache/detail_enrichment.json') as f:
        existing = json.load(f)
except: existing = {}

to_fetch = [pid for pid in top300_ids if pid not in existing]
print(f'Top 300: {len(to_fetch)} need enrichment ({len(existing)} already cached)')

headers = {'User-Agent': 'Mozilla/5.0','Accept': 'application/json'}
for i, pid in enumerate(to_fetch):
    url = f'https://www.nobroker.in/api/v3/property/{pid}?hopId=public'
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get('status') == 'success':
            p = data['data']
            existing[pid] = {
                'maintenanceAmount': p.get('maintenanceAmount'),
                'maintenance': p.get('maintenance'),
                'description': (p.get('description') or '')[:500],
                'cupBoard': p.get('cupBoard'),
                'completeStreetName': p.get('completeStreetName', ''),
                'availableFrom': p.get('formattedAvailableFrom', ''),
                'propertyCode': p.get('propertyCode', ''),
                'latitude': p.get('latitude'),
                'longitude': p.get('longitude'),
            }
    except: pass
    if (i+1) % 50 == 0: print(f'  {i+1}/{len(to_fetch)}')
    time.sleep(1)

with open('data/cache/detail_enrichment.json', 'w') as f:
    json.dump(existing, f, indent=2)
print(f'Enrichment cache: {len(existing)} listings')
"

echo ""
echo "=== Step 3: Rebuild map ==="
python3 /Users/parijat/dev/rental-lookup/build_map.py

echo ""
echo "=== Done! Map updated at $(date) ==="
