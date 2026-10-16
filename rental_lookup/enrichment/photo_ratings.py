"""Rate apartment photos with a vision model via OpenRouter.

Sends every photo of a listing in one request and gets back a structured JSON
checklist. Ratings are cached in data/cache/photo_ratings.json and shown on the map.
Run: OPENROUTER_API_KEY=... python -m rental_lookup.enrichment.photo_ratings [TOP_N]
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
import httpx

from rental_lookup.paths import NOBROKER_PAGES_DIR, PHOTO_RATINGS_PATH
from rental_lookup.sources.nobroker import follow_up_priority, has_real_photo, iter_saved_listings, photo_urls

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
VISION_MODEL = "google/gemini-2.5-flash"  # cheap, fast, good at vision

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

_AMENITY_LABELS = (
    ("POOL", "Pool"), ("GYM", "Gym"), ("CLUB", "Club"), ("GP", "Gated Community"),
    ("SECURITY", "24hr Security"), ("PB", "Power Backup"), ("LIFT", "Lift"), ("CPA", "Covered Parking"),
)


def describe_listing_claims(raw: dict) -> str:
    """Text summary of the listing's claims, sent alongside the photos."""
    amenities = raw.get("amenitiesMap") or {}
    stated_amenities = [label for key, label in _AMENITY_LABELS if amenities.get(key)]
    return f"""Listing details:
- Price: Rs.{raw.get('rent', 0):,}/month
- Size: {raw.get('propertySize', 0)} sqft
- Type: {raw.get('typeDesc', raw.get('type', ''))}
- Society: {raw.get('society', '')}
- Location: {raw.get('locality', '')}
- Floor: {raw.get('floor', '?')}/{raw.get('totalFloor', '?')}
- Facing: {raw.get('facing', '?')}
- Balconies: {raw.get('balconies', '?')}
- Age: {raw.get('propertyAge', '?')} years
- Furnishing: {raw.get('furnishingDesc', '?')}
- Stated amenities: {', '.join(stated_amenities) if stated_amenities else 'None listed'}
- Parking: {raw.get('parkingDesc', raw.get('parking', '?'))}

Rate the photos below against these claims."""


def _strip_code_fence(text: str) -> str:
    """Models sometimes wrap JSON in ```json ... ``` despite being told not to."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return text[4:].strip() if text.startswith("json") else text


def rate_listing(raw: dict, api_key: str = "") -> dict:
    """Send all of a listing's photos to the vision model; returns its JSON rating.

    On failure returns {"verdict": "error", ...}, which callers should not cache.
    """
    urls = photo_urls(raw, max_photos=50)
    if not urls:
        return {"verdict": "skip", "overall_score": 0, "one_line_summary": "No photos available"}

    content = [{"type": "text", "text": describe_listing_claims(raw)}]
    content += [{"type": "image_url", "image_url": {"url": url}} for url in urls]
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
    }
    headers = {
        "Authorization": f"Bearer {api_key or os.environ.get('OPENROUTER_API_KEY', '')}",
        "HTTP-Referer": "https://rental-lookup.local",
    }
    try:
        response = httpx.post(OPENROUTER_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return json.loads(_strip_code_fence(text))
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as e:
        return {"verdict": "error", "overall_score": 0, "one_line_summary": f"API error: {str(e)[:50]}"}


def _worth_rating(raw: dict) -> bool:
    return (30000 <= (raw.get("rent") or 0) <= 70000
            and (raw.get("propertySize") or 0) >= 700
            and bool(raw.get("latitude")) and bool(raw.get("longitude"))
            and len(raw.get("photos") or []) >= 3
            and has_real_photo(raw))


def _save_ratings(ratings: dict) -> None:
    PHOTO_RATINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PHOTO_RATINGS_PATH.write_text(json.dumps(ratings, indent=2))


def rate_top_listings(top_n: int = 50) -> None:
    """Rate the not-yet-rated listings among the top N by follow-up priority."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        sys.exit("Set OPENROUTER_API_KEY to rate photos.")

    candidates = [raw for raw in iter_saved_listings(NOBROKER_PAGES_DIR) if _worth_rating(raw)]
    candidates.sort(key=lambda raw: -follow_up_priority(raw))
    top = candidates[:top_n]
    print(f"Rating top {len(top)} listings...")

    ratings = json.loads(PHOTO_RATINGS_PATH.read_text()) if PHOTO_RATINGS_PATH.exists() else {}
    newly_rated = 0
    for position, raw in enumerate(top, 1):
        if raw["id"] in ratings:
            continue
        print(f"  [{position}/{len(top)}] {raw.get('society', '')[:30]} | Rs.{raw.get('rent', 0):,} | "
              f"{len(raw.get('photos') or [])} photos")

        rating = rate_listing(raw, api_key)
        if rating.get("verdict") == "error":
            print(f"    → {rating['one_line_summary']} (will retry next run)")
        else:
            ratings[raw["id"]] = rating
            newly_rated += 1
            answers = [value for value in rating.values() if isinstance(value, bool)]
            print(f"    → {sum(answers)}/{len(answers)} yes: {rating.get('one_line', '')}")
            if newly_rated % 10 == 0:
                _save_ratings(ratings)  # checkpoint
        time.sleep(1)  # rate limit

    _save_ratings(ratings)

    impressions = Counter(rating.get("overall_impression", rating.get("verdict", "unknown"))
                          for rating in ratings.values())
    print(f"\nRated {newly_rated} new listings ({len(ratings)} total)")
    print(f"Impressions: {dict(impressions)}")

    candidates_by_id = {raw["id"]: raw for raw in candidates}
    worth_visiting = [(listing_id, rating) for listing_id, rating in ratings.items()
                      if rating.get("overall_impression") == "would visit" and listing_id in candidates_by_id]
    if worth_visiting:
        print(f"\n=== WOULD VISIT ({len(worth_visiting)}) ===")
        for listing_id, rating in worth_visiting:
            raw = candidates_by_id[listing_id]
            print(f"  Rs.{raw.get('rent', 0):,} | {raw.get('society', '')[:30]}")
            print(f"    {rating.get('one_line', '')}")
            print(f"    https://www.nobroker.in{raw.get('detailUrl', '')}")
            print()


if __name__ == "__main__":
    rate_top_listings(int(sys.argv[1]) if len(sys.argv) > 1 else 5)  # default: small test batch
