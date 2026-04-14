# Bangalore Rental Lookup

Find the best rental apartments in Bangalore. Scrapes NoBroker, scores against quality/value metrics, and shows results on an interactive map with photos.

## What's Inside

- **8,712 listings** scraped from NoBroker across 24 neighborhoods
- **Interactive map** (`output/map.html`) with filters, scoring, hover photos, and sidebar
- **HTML gallery** (`output/top100.html`) of top 100 apartments with photos
- **CSV export** (`output/results.csv`) for spreadsheet analysis

## Quick Start

### Just browse what we already have

Open `output/map.html` in a browser. Everything is baked in — no server needed.

**Map features:**
- Sliders: total cost (rent + maintenance), min sqft, min photos, max deposit, min score, max days since posted
- Toggle chips: No W/NW facing, Has Balcony, No Standalone, No Independent House, Real Photo, Pet Friendly Only, Pool Only, Brand Only
- Quality / Value toggle: rank by apartment quality or best quality-per-rupee
- Hover any dot for photo + details, click to open on NoBroker
- Sidebar shows listings in current map view, updates as you pan/zoom
- Circle color = score (quality mode) or value (value mode)
- Circle size = sqft
- Dashed circles = approximate location

### Refresh with latest NoBroker data

```bash
# Install dependencies (first time only)
pip3 install -e ".[dev]"

# Fetch fresh listings (uses cached data for neighborhoods already scraped)
python3 -m rental_lookup

# If NoBroker blocks you (403), grab a cookie from Chrome DevTools:
# 1. Open nobroker.in in Chrome
# 2. DevTools > Application > Cookies > copy any cookie value
# 3. Pass it:
python3 -m rental_lookup "your_cookie_string"
```

After fetching, regenerate the map by running the map generation script (see Development section).

### Adjust filters

Edit `rental_lookup/scorer.py` to change:
```python
MAX_RENT = 70000   # upper rent limit
MIN_RENT = 30000   # lower rent limit
MIN_SQFT = 700     # minimum square footage
```

Edit `rental_lookup/nobroker.py` to add/remove neighborhoods:
```python
NEIGHBORHOODS = {
    "Indiranagar": {"lat": 12.9716, "lon": 77.6412, ...},
    # Add more areas here
}
```

## Data We Collect Per Listing

From the NoBroker listing API:
- Rent, deposit, sqft, BHK, floor, total floors
- Lat/lng, locality, society name, building type
- Facing direction, balconies, property age
- Parking, power backup, gated community, security, pool, gym, club
- NoBroker transit score, lifestyle score
- Photo URLs, photo count
- Negotiable flag, lease type, water supply

From the NoBroker detail API (top 300 only):
- Exact maintenance amount
- Owner description (checked for pet-friendly mentions)
- Cupboard count
- Full street address
- Available from date
- Property code

## Scoring

**Quality score** — how good is this apartment:
- Facing (E/SE/S/NE) + balconies
- Property age (newer = better)
- Amenities: power backup, security, gated, fire safety, pool, gym, club
- Car parking
- NoBroker transit + lifestyle scores
- Water supply reliability
- Negotiable rent
- Photo count (more = more transparent)
- Brand developer (Prestige, Brigade, Sobha, etc.)
- Space (sqft bonus)

**Value score** — how good is it for the price:
- `quality_score / total_cost * 100000`
- Higher = better apartment per rupee

**Red flag filters** (applied via map chips):
- Placeholder photos (owner didn't upload real photos)
- Zero balconies
- Standalone/unnamed buildings
- NoBroker scores 0/0
- Top floor of low-rise with no lift
- High deposit (>8x rent)
- West/NW facing (hot afternoons)

## File Structure

```
rental_lookup/
├── __main__.py          # CLI entry: python3 -m rental_lookup
├── run.py               # Orchestrator
├── nobroker.py          # NoBroker API client
├── geo.py               # OSM bulk fetch + spatial scoring
├── scorer.py            # Filters + scoring
├── models.py            # Listing, LocationScore, ScoredListing
└── fb_scraper.py        # Facebook group scraper (needs cookies)

data/
├── raw/                 # 217 raw NoBroker JSON files (92MB)
├── cache/               # OSM GeoPackage + detail enrichment
│   ├── parks.gpkg
│   ├── lakes.gpkg
│   ├── metro.gpkg
│   └── detail_enrichment.json
└── spike/               # API contract docs from initial research

output/
├── map.html             # Interactive map (self-contained, shareable)
├── top100.html          # Photo gallery of top 100
└── results.csv          # Full ranked CSV

tests/                   # 37 tests
```

## Neighborhoods Covered

Indiranagar, Jayanagar, Malleshwaram, Basavanagudi, Ulsoor, Rajajinagar, Koramangala, HSR Layout, BTM Layout, Sadashivanagar, Frazer Town, Shivajinagar, JP Nagar, Banashankari, KR Puram, MG Road, Whitefield, Marathahalli, CV Raman Nagar, Richmond Town, Vasanth Nagar, Wilson Garden, Domlur, Cunningham Road

## Facebook Scraper (Phase 2)

The FB scraper is built but needs Facebook cookies to access group posts.

```bash
# Export cookies from Chrome using "Get cookies.txt LOCALLY" extension
# Then:
python3 -m rental_lookup.fb_scraper cookies.txt
```

It scrapes "Flat and Flatmates Bangalore" group, extracts rent/BHK/area/phone numbers from posts, and saves to `data/fb/`.

## Known Limitations

- NoBroker API is undocumented — may break if they change it
- ~20% of listings have approximate locations (centroid-snapped)
- Maintenance cost only available for top 300 (requires detail API call per listing)
- No phone numbers (NoBroker paywalls these)
- Description/pet-friendly signals only for top 300
- Photos load from NoBroker CDN — won't work offline

## Tips for Actually Finding a Place

1. Use the **Value** toggle on the map to find underpriced gems
2. Set **Max days since posted** to 7-14 to only see fresh listings
3. For named societies (Prestige, Brigade etc.), skip NoBroker — visit the building and ask the security guard
4. Google "[society name] [area] for rent" to find the same listing on other platforms with visible phone numbers
5. NoBroker's cheapest plan (Rs.999) gives ~25 contacts — worth it once you've narrowed to a shortlist
6. Re-run the scraper weekly — best apartments go within days
