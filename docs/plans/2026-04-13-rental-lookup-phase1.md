# Rental Lookup Phase 1: NoBroker + Location Scoring

**Goal:** Fetch rental listings from NoBroker's undocumented JSON API for central Bangalore (budget <= 60K, 2-3 BHK, unfurnished), score each listing against 7 cat-owner criteria using OpenStreetMap geospatial data, and output a ranked shortlist as JSON/CSV.

## Design

1. The project is a Python CLI (`python -m rental_lookup`) with three modules: `nobroker.py` (fetch listings), `location.py` (geospatial scoring), `scorer.py` (rank and output). Dependencies: `httpx` for async HTTP (NoBroker API returns paginated JSON, async lets us fetch pages concurrently), `osmnx` for OpenStreetMap queries (5000+ stars, actively maintained, returns GeoDataFrames — the gold standard for querying parks/lakes/metro by coordinates), and `pandas` for tabular output. No web framework, no database — plain CLI that writes `output/results.csv` and `output/results.json`.

2. `nobroker.py` hits `GET https://www.nobroker.in/api/v3/multi/property/RENT/filter` with query params: `city=bangalore`, `rent=0-60000`, `type=BHK2,BHK3`, `furnishing=NOT_FURNISHED,SEMI_FURNISHED`, `buildingType=AP,IH` (apartments + independent houses), `pageNo=N`, `radius=5`. The `searchParam` is a base64-encoded JSON blob containing lat/lng centroids for target neighborhoods (Indiranagar: 12.9716/77.6412, Jayanagar: 12.9250/77.5938, Malleshwaram: 12.9963/77.5713, Basavanagudi: 12.9416/77.5713, Ulsoor: 12.9812/77.6200, Rajajinagar: 12.9900/77.5525); we fire one search per neighborhood. Headers mimic a browser (`User-Agent`, `Accept: application/json`); cookies are optional but improve reliability — the fetcher logs a warning if a 403 is returned and retries once with a fresh session. Each response's `data` array contains objects with `rent`, `deposit`, `latitude`, `longitude`, `propertySize`, `furnishing`, `parking`, `powerBackup`, `balconyCount`, `floorNo`, `society`, `locality`, `photoUrls`, `propertyTitle`, `detailUrl`. We deduplicate by `propertyId` across neighborhoods and store as a list of `Listing` dataclass instances.

3. `location.py` takes a `(lat, lng)` and uses `osmnx.features.features_from_point()` to query three categories within configurable radii: parks (`{"leisure": "park"}`, 1km radius), water bodies (`{"natural": "water"}`, 1.5km radius — covers lakes), and metro stations (`{"railway": "station", "station": "subway"}`, 1.5km radius — Namma Metro is tagged as subway in OSM). Each query returns a GeoDataFrame; we compute haversine distance from the listing to the nearest feature in each category using `geopy.distance.distance()`. Returns a `LocationScore` dataclass: `nearest_park_m`, `nearest_lake_m`, `nearest_metro_m`, `park_count_1km`, `lake_count_1500m`. OSMnx caches aggressively by default (filesystem cache), so repeated queries for nearby listings are fast.

4. `scorer.py` combines NoBroker listing fields with location scores into a weighted total (0-100). Weights and thresholds: **metro** (25pts: <500m=25, <1000m=20, <1500m=10, else 0), **greenery** (20pts: park <500m=15 + lake <1500m=5, diminishing with distance), **cat safety** (20pts: gated community/society name present=10, has balcony grills or ground/1st floor=5, parking=covered adds 5 — proxy for well-maintained building), **spacious** (15pts: >1000sqft=15, >800sqft=10, else 5), **power backup** (10pts: field truthy=10), **parking** (10pts: car parking available=10). Wall color cannot be scored from data (NoBroker doesn't expose it) — we flag this as "verify in photos" in output. The scorer sorts descending by total score, writes top-50 to CSV (with columns: score, rent, deposit, sqft, locality, society, metro_dist, park_dist, lake_dist, parking, power_backup, url) and full results to JSON.

5. `config.py` holds all tunable constants: neighborhood centroids, rent range, BHK types, scoring weights, distance thresholds, output paths. A `config.yaml` override is optional (loaded with PyYAML if present, else defaults). This means re-running for different cities or budgets requires zero code changes.

6. `__main__.py` orchestrates: parse CLI args (`--city`, `--budget`, `--bhk`, `--output-dir`), fetch listings from NoBroker (with progress bar via `tqdm`), score each listing's location (batched to respect Overpass API rate limits — 1 req/sec, though OSMnx cache means most hits are local after the first run), merge scores, sort, write output, print top-10 summary to stdout.

7. Error handling: NoBroker 403/429 → exponential backoff (3 retries, 2s/4s/8s), then skip that neighborhood with a warning. Overpass timeout → retry once, then score that listing's location as 0 with a flag. Empty results for a neighborhood → log and continue. All errors surface to stderr with context, never silently swallowed.

## Files

| File | What it does |
|------|-------------|
| `rental_lookup/__init__.py` | Package marker |
| `rental_lookup/__main__.py` | CLI entrypoint, orchestration |
| `rental_lookup/nobroker.py` | NoBroker API client — fetch, paginate, deduplicate |
| `rental_lookup/location.py` | OSMnx queries — parks, lakes, metro distance |
| `rental_lookup/scorer.py` | Weighted scoring, CSV/JSON output |
| `rental_lookup/config.py` | Constants, defaults, YAML override loader |
| `rental_lookup/models.py` | `Listing`, `LocationScore`, `ScoredListing` dataclasses |
| `config.yaml` | Optional user overrides (neighborhoods, weights, budget) |
| `pyproject.toml` | Dependencies: httpx, osmnx, geopy, pandas, tqdm, pyyaml |
| `output/` | Generated results (gitignored) |
| `tests/test_scorer.py` | Unit tests for scoring logic |
| `tests/test_location.py` | Unit tests for distance calculations (mocked OSMnx) |
| `tests/test_nobroker.py` | Unit tests for response parsing, dedup (mocked HTTP) |

**What does NOT change:** No web framework, no database, no frontend, no MCP server (Phase 2 concern). No Selenium/Playwright — NoBroker is pure JSON API.
