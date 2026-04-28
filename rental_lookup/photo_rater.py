"""
Rate apartment photos using OpenRouter vision API.
Sends all photos for each listing to a vision model and gets a structured rating.
"""

import json
import os
import time
import base64
import urllib.request
from pathlib import Path
from typing import Optional

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash"  # cheap, fast, good at vision

SYSTEM_PROMPT = """You are looking at apartment listing photos in Bangalore, India.

IMPORTANT CONTEXT:
- These are typical Indian apartment listing photos — often poorly lit, shot on phones, with wide-angle distortion. Judge the APARTMENT, not the photo quality.
- Window grills are standard in India — ignore them completely.
- Most rooms have tube lights on — that doesn't mean the room is dark. Look for windows and balcony doors to judge natural light.
- Many photos are close-ups of wardrobes, kitchen cabinets, or bathroom fixtures. These tell you about furnishing quality but NOT about the apartment's light or spaciousness.
- Cream, off-white, and light beige walls are all considered "light colored" and perfectly fine.

Answer each question true or false. If you genuinely cannot tell from the photos, answer null.

Return ONLY valid JSON:

{
  "well_lit": true/false/null,
  "has_big_windows": true/false/null,
  "trees_or_greenery_outside": true/false/null,
  "open_view_not_blocked": true/false/null,
  "light_colored_walls": true/false/null,
  "walls_in_good_condition": true/false/null,
  "modular_kitchen": true/false/null,
  "kitchen_has_storage": true/false/null,
  "kitchen_has_chimney": true/false/null,
  "bathroom_looks_ok": true/false/null,
  "has_balcony": true/false/null,
  "balcony_usable_size": true/false/null,
  "good_flooring": true/false/null,
  "has_wardrobes": true/false/null,
  "no_visible_damage": true/false/null,
  "rooms_feel_spacious": true/false/null,
  "cat_could_sit_at_window": true/false/null,
  "overall_impression": "would visit" | "maybe" | "would skip",
  "one_line": "under 12 words, be specific not generic"
}

Definitions:
- well_lit: Do the rooms LOOK like they get natural light? Big windows, balcony doors, daylight coming in. Even if photo is dark, if you see big windows, answer true.
- has_big_windows: Large windows or full-height balcony doors (not tiny ventilator windows)?
- trees_or_greenery_outside: ANY trees, plants, garden visible through windows or balcony?
- open_view_not_blocked: View is open (sky, distance) not staring at another building wall?
- light_colored_walls: Walls are white, off-white, cream, light beige, or any light neutral? One accent wall in a different color is fine — judge the majority.
- walls_in_good_condition: No water stains, damp patches, peeling paint, or cracks?
- modular_kitchen: Fitted modular cabinets (not just a granite slab with nothing above)?
- kitchen_has_storage: Upper cabinets, lower cabinets, or shelving present?
- kitchen_has_chimney: Chimney or exhaust hood above cooking area?
- bathroom_looks_ok: If shown — clean tiles, functioning fixtures?
- has_balcony: At least one balcony visible?
- balcony_usable_size: Big enough for a chair and a plant (not a 2-foot ledge)?
- good_flooring: Flooring in good condition — vitrified tiles, marble, granite all count.
- has_wardrobes: Built-in wardrobes or cupboards in bedrooms?
- no_visible_damage: No water damage, mold, broken tiles, peeling paint anywhere?
- rooms_feel_spacious: Rooms have reasonable space (judging proportions, not wide-angle tricks)?
- cat_could_sit_at_window: Window sill, balcony, or spot where a cat could sit and look outside?
- overall_impression: "would visit" = go see it. "maybe" = borderline. "would skip" = something clearly wrong.
- one_line: ONE specific thing that stands out. "huge balcony with tree view" NOT "decent apartment"

No preamble, no markdown, just JSON."""


def get_photo_urls(item, max_photos=50):
    """Get ALL photo URLs from a raw NoBroker listing (medium size ~18KB each)."""
    pid = item['id']
    urls = []
    for p in item.get('photos', [])[:max_photos]:
        if isinstance(p, dict):
            fname = p.get('imagesMap', {}).get('medium') or p.get('imagesMap', {}).get('large', '')
            if fname:
                urls.append(f'https://assets.nobroker.in/images/{pid}/{fname}')
    return urls


def build_listing_context(item):
    """Build text context about the listing."""
    amenities = item.get('amenitiesMap', {}) or {}
    perks = []
    if amenities.get('POOL'): perks.append('Pool')
    if amenities.get('GYM'): perks.append('Gym')
    if amenities.get('CLUB'): perks.append('Club')
    if amenities.get('GP'): perks.append('Gated Community')
    if amenities.get('SECURITY'): perks.append('24hr Security')
    if amenities.get('PB'): perks.append('Power Backup')
    if amenities.get('LIFT'): perks.append('Lift')
    if amenities.get('CPA'): perks.append('Covered Parking')

    return f"""Listing details:
- Price: Rs.{item.get('rent', 0):,}/month
- Size: {item.get('propertySize', 0)} sqft
- Type: {item.get('typeDesc', item.get('type', ''))}
- Society: {item.get('society', '')}
- Location: {item.get('locality', '')}
- Floor: {item.get('floor', '?')}/{item.get('totalFloor', '?')}
- Facing: {item.get('facing', '?')}
- Balconies: {item.get('balconies', '?')}
- Age: {item.get('propertyAge', '?')} years
- Furnishing: {item.get('furnishingDesc', '?')}
- Stated amenities: {', '.join(perks) if perks else 'None listed'}
- Parking: {item.get('parkingDesc', item.get('parking', '?'))}

Rate the photos below against these claims."""


def rate_listing(item, api_key=OPENROUTER_API_KEY):
    """Send listing photos to vision model and get rating."""
    photo_urls = get_photo_urls(item)
    if not photo_urls:
        return {"verdict": "skip", "overall_score": 0, "one_line_summary": "No photos available"}

    context = build_listing_context(item)

    # Build message with images
    content = [{"type": "text", "text": context}]
    for url in photo_urls:
        content.append({
            "type": "image_url",
            "image_url": {"url": url}
        })

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content}
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://rental-lookup.local",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())

        text = result['choices'][0]['message']['content']
        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        if text.startswith('json'):
            text = text[4:].strip()

        return json.loads(text)
    except Exception as e:
        return {"verdict": "error", "overall_score": 0, "one_line_summary": f"API error: {str(e)[:50]}"}


def rate_top_listings(n=50):
    """Rate the top N listings by our scoring."""
    import glob

    from rental_lookup.models import BRANDED_BUILDERS as brands

    # Load all listings with scoring
    results = []
    seen = set()
    for f in sorted(glob.glob('data/raw/*.json')):
        with open(f) as fh:
            d = json.load(fh)
        for item in d.get('data', []):
            if item['id'] in seen: continue
            seen.add(item['id'])
            rent = item.get('rent', 0)
            if rent < 30000 or rent > 70000: continue
            sqft = item.get('propertySize', 0)
            if sqft < 700: continue
            if not item.get('latitude') or not item.get('longitude'): continue
            photos = item.get('photos', [])
            if len(photos) < 3: continue
            img = item.get('originalImageUrl', '')
            if not img or 'static/img' in img: continue

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
            parking = item.get('parking', 'NONE')
            if parking in ('FOUR_WHEELER','BOTH'): s += 5
            nb_t = score_data.get('transit', 0) if isinstance(score_data, dict) else 0
            nb_l = score_data.get('lifestyle', 0) if isinstance(score_data, dict) else 0
            if nb_t >= 8: s += 5
            elif nb_t >= 7: s += 3
            if nb_l >= 8: s += 8
            elif nb_l >= 6: s += 4
            if item.get('negotiable'): s += 3
            if len(photos) >= 10: s += 5
            elif len(photos) >= 5: s += 3
            soc_title = (item.get('society','') + ' ' + item.get('propertyTitle','')).lower()
            if any(b in soc_title for b in brands): s += 8

            results.append({'item': item, 'score': s})

    results.sort(key=lambda x: -x['score'])
    top = results[:n]

    print(f"Rating top {len(top)} listings...")

    # Load existing ratings
    ratings_path = Path('data/cache/photo_ratings.json')
    existing = {}
    if ratings_path.exists():
        with open(ratings_path) as f:
            existing = json.load(f)

    rated = 0
    for i, r in enumerate(top):
        item = r['item']
        pid = item['id']

        if pid in existing:
            continue  # already rated

        print(f"  [{i+1}/{len(top)}] {item.get('society','')[:30]} | Rs.{item.get('rent',0):,} | {len(item.get('photos',[]))} photos")

        rating = rate_listing(item)
        existing[pid] = rating

        yes_count = sum(1 for k, v in rating.items() if v is True)
        total_q = sum(1 for k, v in rating.items() if isinstance(v, bool))
        summary = rating.get('one_line', '')
        print(f"    → {yes_count}/{total_q} yes: {summary}")

        rated += 1
        time.sleep(1)  # rate limit

        # Save periodically
        if rated % 10 == 0:
            with open(ratings_path, 'w') as f:
                json.dump(existing, f, indent=2)

    # Final save
    with open(ratings_path, 'w') as f:
        json.dump(existing, f, indent=2)

    # Summary
    verdicts = {}
    for pid, rating in existing.items():
        v = rating.get('verdict', 'unknown')
        verdicts[v] = verdicts.get(v, 0) + 1

    print(f"\nRated {rated} new listings ({len(existing)} total)")
    print(f"Verdicts: {verdicts}")

    # Show shortlisted
    shortlisted = [(pid, r) for pid, r in existing.items() if r.get('verdict') == 'shortlist']
    if shortlisted:
        print(f"\n=== SHORTLISTED ({len(shortlisted)}) ===")
        for pid, r in sorted(shortlisted, key=lambda x: -x[1].get('overall_score', 0)):
            # Find the listing
            for res in results:
                if res['item']['id'] == pid:
                    item = res['item']
                    print(f"  {r.get('overall_score',0)}/10 | Rs.{item.get('rent',0):,} | {item.get('society','')[:30]}")
                    print(f"    {r.get('one_line_summary','')}")
                    print(f"    Greens: {r.get('green_flags', [])}")
                    print(f"    Reds: {r.get('red_flags', [])}")
                    print(f"    https://www.nobroker.in{item.get('detailUrl','')}")
                    print()
                    break


if __name__ == '__main__':
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5  # default: test with 5
    rate_top_listings(n)
