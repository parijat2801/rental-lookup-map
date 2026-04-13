# Rental Lookup Phase 1: NoBroker + Location Scoring

**Goal:** Fetch rental listings from NoBroker for central Bangalore (budget <= 60K, 2-3 BHK), score each against cat-owner criteria using OpenStreetMap data, output a ranked shortlist. One-time tool — run it, find a house, done.

## Spike 0: Validate before building

0. Before writing any code, capture a real NoBroker API request from browser DevTools (Network tab → filter XHR → search for a 2BHK in Indiranagar → copy the request as cURL). Save the sanitized request and one sample response to `data/spike/nobroker-sample-request.txt` and `data/spike/nobroker-sample-response.json`. This tells us the real endpoint, params, headers, and response shape — everything in item 2 below is then adjusted to match reality. Also verify Bangalore metro OSM tags: run a quick Overpass query for `railway=station` within Bangalore bbox to see how Namma Metro stations are actually tagged.

## Design

1. Python CLI (`python -m rental_lookup`), four modules: `nobroker.py` (fetch), `geo.py` (location data), `scorer.py` (rank), `run.py` (orchestrate + output). Dependencies: `httpx` (sync — no async until we know the API tolerates concurrency), `osmnx`, `geopandas`, `geopy`, `pandas`, `tqdm`. Writes `output/results.csv`. No config files, no YAML, no CLI args — hardcode everything for Bangalore/60K/2-3BHK in constants at top of each module. Change a constant, re-run.

2. `nobroker.py` hits NoBroker's undocumented listing endpoint (exact URL/params/headers determined by Spike 0). We search 6 neighborhoods by lat/lng centroid: Indiranagar (12.9716, 77.6412), Jayanagar (12.9250, 77.5938), Malleshwaram (12.9963, 77.5713), Basavanagudi (12.9416, 77.5713), Ulsoor (12.9812, 77.6200), Rajajinagar (12.9900, 77.5525). Paginates until empty page. Saves raw JSON responses to `data/raw/` (so we can re-score without re-fetching). Parses each listing into a `Listing` dataclass, deduplicates by `propertyId`, skips listings missing lat/lng. If a 403 hits, prints the cURL equivalent so we can manually grab fresh cookies.

3. `geo.py` does NOT query Overpass per listing. Instead, it bulk-fetches three GeoDataFrames for all of central Bangalore (bbox: 12.90-13.05 lat, 77.50-77.70 lng) in exactly 3 Overpass calls: green spaces (`{"leisure": ["park", "garden"], "landuse": "recreation_ground"}`), water bodies (`{"natural": "water", "water": "lake"}`), metro/rail stations (`{"railway": "station", "public_transport": "station"}`). Caches results to `data/cache/parks.gpkg`, `lakes.gpkg`, `metro.gpkg` (GeoPackage files — reload on next run without hitting Overpass). For each listing, computes nearest-feature distance using geopandas spatial index (`sindex.nearest`) on projected CRS (UTM 43N for Bangalore) — proper geometry distance, not centroid-to-centroid haversine.

4. `scorer.py` applies hard filters first, then scores survivors. **Hard filters** (listing is dropped if any fail): rent <= 60000, sqft >= 700 (catches mismarked listings), has lat/lng. **Scoring** (0-100): **pet compatibility** (25pts: listing description/title contains "pet" or "pet friendly"=15, gated community/society name present=10), **greenery** (20pts: park <500m=15 + lake <1500m=5, linear decay with distance), **metro** (15pts: <500m=15, <1000m=12, <1500m=8, else 0), **space** (15pts: >1200sqft=15, >1000sqft=12, >800sqft=8, else 5), **power backup** (10pts: field truthy=10, missing=0), **parking** (10pts: car parking present=10), **floor safety** (5pts: ground or 1st floor=5 — easier for cat netting, less balcony risk). Wall color and balcony grills: can't score from data, added as "CHECK MANUALLY" columns. Unknowns score 0, not negative — we're ranking, not rejecting. Outputs sorted CSV with: score, rent, deposit, sqft, locality, society, floor, metro_dist_m, park_dist_m, lake_dist_m, parking, power_backup, pet_friendly_signal, nobroker_url. Prints top-10 to terminal.

5. `run.py` is the entrypoint: fetch listings → save raw → load geo data (from cache or Overpass) → score → write CSV → print summary. No error handling beyond printing what went wrong and continuing. This is a script, not a service.

## Spike 0 execution plan

Run these in Claude Code before writing any module code:
- Open NoBroker in Chrome (via claude-in-chrome), search 2BHK rent Indiranagar Bangalore < 60K, capture the XHR request
- Run an Overpass query: `[out:json];area["name"="Bengaluru"]->.a;node["railway"="station"](area.a);out;` to see how metro is tagged
- Document findings, adjust item 2 and 3 tag assumptions

## Files

| File | What it does |
|------|-------------|
| `rental_lookup/__init__.py` | Package marker |
| `rental_lookup/run.py` | Entrypoint — orchestrate fetch → geo → score → output |
| `rental_lookup/nobroker.py` | NoBroker fetcher — paginate, parse, save raw JSON |
| `rental_lookup/geo.py` | Bulk OSM fetch, cache, spatial nearest-neighbor |
| `rental_lookup/scorer.py` | Hard filters, weighted scoring, CSV output |
| `rental_lookup/models.py` | `Listing`, `LocationScore`, `ScoredListing` dataclasses |
| `pyproject.toml` | Dependencies |
| `data/raw/` | Raw NoBroker JSON responses (gitignored) |
| `data/cache/` | Cached GeoPackage files (gitignored) |
| `data/spike/` | Spike 0 artifacts |
| `output/results.csv` | Final ranked output |

**Tests** (strict TDD — test first, watch it fail, implement, watch it pass):

| File | What it tests |
|------|-------------|
| `tests/test_nobroker.py` | Response parsing, dedup by propertyId, skip-if-no-latlng, pagination assembly. Uses saved `data/spike/nobroker-sample-response.json` as fixture — no mocking, real data shape. |
| `tests/test_geo.py` | Nearest-feature distance calculation given a small synthetic GeoDataFrame (3 parks, 2 lakes, 2 metro stations with known coords). Verifies distances are in meters, correct nearest is picked, empty GeoDataFrame returns None. Does NOT hit Overpass — constructs GeoDataFrames in-memory. |
| `tests/test_scorer.py` | Hard filter rejects (over budget, too small, no latlng). Scoring arithmetic: a listing with park 200m away scores higher than one 800m away. Pet-friendly text signal scores 15pts. Unknown power_backup scores 0 not negative. Full ranking: given 3 listings with known attributes, verify sort order. |
| `tests/conftest.py` | Shared fixtures: sample listing dicts, sample GeoDataFrames. |

Test runner: `pytest`. Added to `pyproject.toml` as dev dependency.

**What does NOT change:** No config files, no async, no web framework, no database. Retries are "print error and move on."
