# Rental Lookup — TDD Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fetch rental listings from NoBroker's JSON API for central Bangalore (<=60K, 2-3 BHK), score each against cat-owner criteria using OpenStreetMap geospatial data, output a ranked CSV shortlist.

**Architecture:** Python CLI with 4 modules: `nobroker.py` (API client), `geo.py` (bulk OSM fetch + spatial nearest-neighbor), `scorer.py` (hard filters + weighted scoring), `run.py` (orchestrator). Data flows: NoBroker JSON → Listing dataclasses → enriched with LocationScore from cached OSM GeoDataFrames → scored → sorted → CSV.

**Tech Stack:** Python 3.9+, httpx (sync HTTP), osmnx + geopandas (geospatial), geopy (distance), pandas (CSV output), pytest (tests). No async, no web framework, no database.

**Output:** Results appear in three places:
1. **Terminal** — top-10 printed with scores, rent, distances, amenity flags
2. **`output/results.csv`** — full ranked list (open in Excel/Sheets), includes NoBroker URL + first photo URL per listing
3. **NoBroker links** — each CSV row has a clickable URL to the full listing page with all photos

**Addendum — photo_url:** The Listing model includes `photo_url: str` parsed from `originalImageUrl` in the NoBroker response. The CSV includes this column so you can preview the first image without clicking into each listing. NoBroker serves images from their CDN at these URLs.

**Spike data (already captured):**
- `data/spike/nobroker-api-contract.md` — verified API endpoint, params, response shape
- `data/spike/nobroker-sample-response.json` — 2-listing fixture with real field names
- `data/spike/osm-tags-verified.md` — Namma Metro uses `network=Namma Metro` + `station=subway`

---

### Task 1: Project Setup + Models

**Files:**
- Create: `pyproject.toml`
- Create: `rental_lookup/__init__.py`
- Create: `rental_lookup/models.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`
- Create: `.gitignore`

**Step 1: Create project scaffolding**

Create `pyproject.toml`:
```toml
[project]
name = "rental-lookup"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = [
    "httpx>=0.27",
    "osmnx>=2.0",
    "geopandas>=1.0",
    "geopy>=2.4",
    "pandas>=2.0",
    "tqdm>=4.66",
    "shapely>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends._legacy:_Backend"
```

Create `.gitignore`:
```
data/raw/
data/cache/
output/
__pycache__/
*.egg-info/
.venv/
```

Create `rental_lookup/__init__.py` (empty).
Create `tests/__init__.py` (empty).

**Step 2: Install dependencies**

Run: `pip3 install -e ".[dev]"`
Expected: all packages install successfully

**Step 3: Write the failing test for models**

Create `tests/test_models.py`:
```python
from rental_lookup.models import Listing, LocationScore, ScoredListing


def test_listing_from_nobroker_dict():
    """Parse a real NoBroker API response dict into a Listing."""
    raw = {
        "id": "ff808181651e847c016521d2c5e337d0",
        "rent": 45000,
        "deposit": 250000,
        "propertySize": 1100,
        "type": "BHK2",
        "latitude": 12.9718,
        "longitude": 77.6411,
        "locality": "Indiranagar, Bengaluru, Karnataka, India",
        "society": "Independent House",
        "buildingType": "IH",
        "floor": 1,
        "totalFloor": 1,
        "lift": False,
        "parking": "TWO_WHEELER",
        "propertyTitle": "2 BHK House for Rent In Indiranagar",
        "detailUrl": "/property/2-bhk-apartment-abc123",
        "amenitiesMap": {
            "PB": False, "GP": False, "CPA": False, "SECURITY": False,
        },
    }
    listing = Listing.from_nobroker(raw)
    assert listing.id == "ff808181651e847c016521d2c5e337d0"
    assert listing.rent == 45000
    assert listing.deposit == 250000
    assert listing.sqft == 1100
    assert listing.bhk == "BHK2"
    assert listing.lat == 12.9718
    assert listing.lng == 77.6411
    assert listing.society == "Independent House"
    assert listing.has_power_backup is False
    assert listing.has_gated_community is False
    assert listing.has_covered_parking is False
    assert listing.has_security is False
    assert listing.has_car_parking is False
    assert listing.floor == 1
    assert listing.url == "https://www.nobroker.in/property/2-bhk-apartment-abc123"


def test_listing_from_nobroker_with_amenities():
    """Listing with full amenities parses boolean flags correctly."""
    raw = {
        "id": "abc123",
        "rent": 55000,
        "deposit": 300000,
        "propertySize": 1450,
        "type": "BHK3",
        "latitude": 12.978,
        "longitude": 77.639,
        "locality": "Indiranagar",
        "society": "Prestige Shantiniketan",
        "buildingType": "AP",
        "floor": 5,
        "totalFloor": 12,
        "lift": True,
        "parking": "BOTH",
        "propertyTitle": "3 BHK Apartment pet friendly",
        "detailUrl": "/property/3-bhk-abc",
        "amenitiesMap": {
            "PB": True, "GP": True, "CPA": True, "SECURITY": True,
        },
    }
    listing = Listing.from_nobroker(raw)
    assert listing.has_power_backup is True
    assert listing.has_gated_community is True
    assert listing.has_covered_parking is True
    assert listing.has_security is True
    assert listing.has_car_parking is True  # parking == "BOTH" or "FOUR_WHEELER"


def test_listing_missing_latlng_returns_none():
    """Listings without lat/lng should return None from from_nobroker."""
    raw = {
        "id": "no-coords",
        "rent": 30000,
        "deposit": 100000,
        "propertySize": 800,
        "type": "BHK2",
        "latitude": None,
        "longitude": None,
        "locality": "Somewhere",
        "society": "",
        "buildingType": "AP",
        "floor": 2,
        "totalFloor": 5,
        "lift": False,
        "parking": "NONE",
        "propertyTitle": "2 BHK Flat",
        "detailUrl": "/property/xyz",
        "amenitiesMap": {},
    }
    assert Listing.from_nobroker(raw) is None


def test_listing_missing_latlng_zero_returns_none():
    """lat=0 lng=0 is also invalid (middle of ocean)."""
    raw = {
        "id": "zero-coords",
        "rent": 30000, "deposit": 100000, "propertySize": 800,
        "type": "BHK2", "latitude": 0, "longitude": 0,
        "locality": "X", "society": "", "buildingType": "AP",
        "floor": 1, "totalFloor": 1, "lift": False,
        "parking": "NONE", "propertyTitle": "Flat",
        "detailUrl": "/p/x", "amenitiesMap": {},
    }
    assert Listing.from_nobroker(raw) is None


def test_location_score_defaults():
    score = LocationScore()
    assert score.nearest_park_m is None
    assert score.nearest_lake_m is None
    assert score.nearest_metro_m is None


def test_scored_listing_combines_listing_and_location():
    raw = {
        "id": "test1", "rent": 40000, "deposit": 200000,
        "propertySize": 1000, "type": "BHK2",
        "latitude": 12.97, "longitude": 77.64,
        "locality": "Test", "society": "Test Society",
        "buildingType": "AP", "floor": 3, "totalFloor": 10,
        "lift": True, "parking": "FOUR_WHEELER",
        "propertyTitle": "Test", "detailUrl": "/p/test",
        "amenitiesMap": {"PB": True, "GP": True, "CPA": True, "SECURITY": True},
    }
    listing = Listing.from_nobroker(raw)
    loc = LocationScore(nearest_park_m=200, nearest_lake_m=1000, nearest_metro_m=500)
    scored = ScoredListing(listing=listing, location=loc, total_score=85)
    assert scored.listing.rent == 40000
    assert scored.location.nearest_park_m == 200
    assert scored.total_score == 85
```

**Step 4: Run test to verify it fails**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rental_lookup.models'`

**Step 5: Write minimal implementation**

Create `rental_lookup/models.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Listing:
    id: str
    rent: int
    deposit: int
    sqft: int
    bhk: str
    lat: float
    lng: float
    locality: str
    society: str
    building_type: str
    floor: int
    total_floor: int
    lift: bool
    parking: str
    title: str
    url: str
    has_power_backup: bool
    has_gated_community: bool
    has_covered_parking: bool
    has_security: bool
    has_car_parking: bool

    @classmethod
    def from_nobroker(cls, raw: dict) -> Listing | None:
        lat = raw.get("latitude")
        lng = raw.get("longitude")
        if not lat or not lng:
            return None

        amenities = raw.get("amenitiesMap") or {}
        parking_val = raw.get("parking", "NONE")
        detail_url = raw.get("detailUrl", "")

        return cls(
            id=raw["id"],
            rent=raw.get("rent", 0),
            deposit=raw.get("deposit", 0),
            sqft=raw.get("propertySize", 0),
            bhk=raw.get("type", ""),
            lat=lat,
            lng=lng,
            locality=raw.get("locality", ""),
            society=raw.get("society", ""),
            building_type=raw.get("buildingType", ""),
            floor=raw.get("floor", 0),
            total_floor=raw.get("totalFloor", 0),
            lift=raw.get("lift", False),
            parking=parking_val,
            title=raw.get("propertyTitle", ""),
            url=f"https://www.nobroker.in{detail_url}",
            has_power_backup=bool(amenities.get("PB")),
            has_gated_community=bool(amenities.get("GP")),
            has_covered_parking=bool(amenities.get("CPA")),
            has_security=bool(amenities.get("SECURITY")),
            has_car_parking=parking_val in ("FOUR_WHEELER", "BOTH"),
        )


@dataclass
class LocationScore:
    nearest_park_m: float | None = None
    nearest_lake_m: float | None = None
    nearest_metro_m: float | None = None


@dataclass
class ScoredListing:
    listing: Listing
    location: LocationScore
    total_score: float
```

**Step 6: Run test to verify it passes**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: all 7 tests PASS

**Step 7: Commit**

```bash
git add pyproject.toml .gitignore rental_lookup/ tests/
git commit -m "feat: project setup + Listing/LocationScore/ScoredListing models with TDD"
```

---

### Task 2: NoBroker API Client — Response Parsing + Dedup

**Files:**
- Create: `rental_lookup/nobroker.py`
- Create: `tests/test_nobroker.py`
- Create: `tests/conftest.py`

**Step 1: Write the failing test**

Create `tests/conftest.py`:
```python
import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_nobroker_response():
    path = Path(__file__).parent.parent / "data" / "spike" / "nobroker-sample-response.json"
    with open(path) as f:
        return json.load(f)
```

Create `tests/test_nobroker.py`:
```python
from rental_lookup.nobroker import parse_listings, deduplicate


def test_parse_listings_from_sample_response(sample_nobroker_response):
    """Parse real NoBroker API response into Listing objects."""
    listings = parse_listings(sample_nobroker_response)
    assert len(listings) == 2
    assert listings[0].id == "ff808181651e847c016521d2c5e337d0"
    assert listings[0].rent == 45000
    assert listings[1].rent == 55000
    assert listings[1].has_power_backup is True


def test_parse_listings_skips_missing_coords(sample_nobroker_response):
    """Listings without lat/lng are silently dropped."""
    data = sample_nobroker_response.copy()
    data["data"].append({
        "id": "no-coords", "rent": 30000, "deposit": 100000,
        "propertySize": 800, "type": "BHK2",
        "latitude": None, "longitude": None,
        "locality": "X", "society": "", "buildingType": "AP",
        "floor": 1, "totalFloor": 1, "lift": False,
        "parking": "NONE", "propertyTitle": "Flat",
        "detailUrl": "/p/x", "amenitiesMap": {},
    })
    listings = parse_listings(data)
    assert len(listings) == 2  # third one dropped


def test_parse_listings_empty_data():
    """Empty data array returns empty list."""
    listings = parse_listings({"status": "success", "data": []})
    assert listings == []


def test_parse_listings_failed_response():
    """Non-success response returns empty list."""
    listings = parse_listings({"status": "error", "data": []})
    assert listings == []


def test_deduplicate_by_id():
    """Deduplicate listings by id, keeping first occurrence."""
    from rental_lookup.models import Listing

    raw1 = {
        "id": "dup1", "rent": 40000, "deposit": 200000,
        "propertySize": 1000, "type": "BHK2",
        "latitude": 12.97, "longitude": 77.64,
        "locality": "A", "society": "S", "buildingType": "AP",
        "floor": 1, "totalFloor": 5, "lift": False,
        "parking": "BOTH", "propertyTitle": "T",
        "detailUrl": "/p/1", "amenitiesMap": {},
    }
    raw2 = {**raw1, "rent": 45000}  # same id, different rent
    raw3 = {**raw1, "id": "unique1"}

    l1 = Listing.from_nobroker(raw1)
    l2 = Listing.from_nobroker(raw2)
    l3 = Listing.from_nobroker(raw3)

    result = deduplicate([l1, l2, l3])
    assert len(result) == 2
    assert result[0].id == "dup1"
    assert result[0].rent == 40000  # first one kept
    assert result[1].id == "unique1"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_nobroker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rental_lookup.nobroker'`

**Step 3: Write minimal implementation**

Create `rental_lookup/nobroker.py`:
```python
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import httpx

from rental_lookup.models import Listing

# --- Constants ---
NOBROKER_API = "https://www.nobroker.in/api/v3/multi/property/RENT/filter"
CITY = "bangalore"
RENT_RANGE = "0,60000"
BHK_TYPES = "BHK2,BHK3"
PAGE_SIZE = 26

NEIGHBORHOODS = {
    "Indiranagar": {"lat": 12.9716, "lon": 77.6412, "placeId": "ChIJbTDDCWAXujYRZyFs0FD4KFI"},
    "Jayanagar": {"lat": 12.9250, "lon": 77.5938, "placeId": ""},
    "Malleshwaram": {"lat": 12.9963, "lon": 77.5713, "placeId": ""},
    "Basavanagudi": {"lat": 12.9416, "lon": 77.5713, "placeId": ""},
    "Ulsoor": {"lat": 12.9812, "lon": 77.6200, "placeId": ""},
    "Rajajinagar": {"lat": 12.9900, "lon": 77.5525, "placeId": ""},
}


def make_search_param(name: str, lat: float, lon: float, place_id: str = "") -> str:
    """Encode neighborhood as base64 searchParam."""
    payload = [{"lat": lat, "lon": lon, "placeId": place_id, "placeName": name}]
    return base64.b64encode(json.dumps(payload).encode()).decode()


def parse_listings(response: dict) -> list[Listing]:
    """Parse NoBroker API response dict into Listing objects."""
    if response.get("status") != "success":
        return []
    listings = []
    for raw in response.get("data", []):
        listing = Listing.from_nobroker(raw)
        if listing is not None:
            listings.append(listing)
    return listings


def deduplicate(listings: list[Listing]) -> list[Listing]:
    """Remove duplicate listings by id, keeping first occurrence."""
    seen: set[str] = set()
    result: list[Listing] = []
    for listing in listings:
        if listing.id not in seen:
            seen.add(listing.id)
            result.append(listing)
    return result


def fetch_neighborhood(
    name: str, lat: float, lon: float, place_id: str = "",
    cookie: str = "",
    raw_dir: Path | None = None,
) -> list[Listing]:
    """Fetch all pages of listings for one neighborhood."""
    search_param = make_search_param(name, lat, lon, place_id)
    all_listings: list[Listing] = []
    page = 1

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    if cookie:
        headers["Cookie"] = cookie

    while True:
        params = {
            "city": CITY,
            "pageNo": str(page),
            "searchParam": search_param,
            "rent": RENT_RANGE,
            "type": BHK_TYPES,
        }
        try:
            resp = httpx.get(NOBROKER_API, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [!] Error fetching {name} page {page}: {e}")
            break

        if raw_dir:
            raw_dir.mkdir(parents=True, exist_ok=True)
            path = raw_dir / f"{name.lower()}_page{page}.json"
            path.write_text(json.dumps(data, indent=2))

        page_listings = parse_listings(data)
        if not page_listings:
            break

        all_listings.extend(page_listings)
        page += 1
        time.sleep(1)  # be polite

    return all_listings


def fetch_all(cookie: str = "", raw_dir: Path | None = None) -> list[Listing]:
    """Fetch listings from all neighborhoods, deduplicate."""
    from tqdm import tqdm

    all_listings: list[Listing] = []
    for name, coords in tqdm(NEIGHBORHOODS.items(), desc="Fetching neighborhoods"):
        print(f"\n  Fetching {name}...")
        listings = fetch_neighborhood(
            name, coords["lat"], coords["lon"], coords.get("placeId", ""),
            cookie=cookie, raw_dir=raw_dir,
        )
        print(f"  Got {len(listings)} listings from {name}")
        all_listings.extend(listings)

    deduped = deduplicate(all_listings)
    print(f"\nTotal: {len(all_listings)} raw, {len(deduped)} after dedup")
    return deduped
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_nobroker.py -v`
Expected: all 5 tests PASS

**Step 5: Commit**

```bash
git add rental_lookup/nobroker.py tests/conftest.py tests/test_nobroker.py
git commit -m "feat: NoBroker API client — parse listings, dedup, paginated fetch"
```

---

### Task 3: Geo Module — Bulk OSM Fetch + Spatial Nearest-Neighbor

**Files:**
- Create: `rental_lookup/geo.py`
- Create: `tests/test_geo.py`

**Step 1: Write the failing test**

Create `tests/test_geo.py`:
```python
import geopandas as gpd
import numpy as np
from shapely.geometry import Point

from rental_lookup.geo import nearest_distance_m, compute_location_scores
from rental_lookup.models import LocationScore


def _make_gdf(coords: list[tuple[float, float]]) -> gpd.GeoDataFrame:
    """Helper to build a GeoDataFrame from (lat, lng) pairs in EPSG:4326."""
    points = [Point(lng, lat) for lat, lng in coords]
    return gpd.GeoDataFrame(geometry=points, crs="EPSG:4326")


def test_nearest_distance_to_single_point():
    """Distance from a listing to the only park should be correct."""
    # Indiranagar metro: 12.9784, 77.6408
    # A park 500m north-ish: ~12.9829, 77.6408
    parks = _make_gdf([(12.9829, 77.6408)])
    dist = nearest_distance_m(12.9784, 77.6408, parks)
    assert dist is not None
    assert 400 < dist < 600  # ~500m, allow tolerance for projection


def test_nearest_distance_picks_closest():
    """When multiple features exist, return distance to nearest."""
    parks = _make_gdf([
        (12.9829, 77.6408),  # ~500m away
        (12.9900, 77.6408),  # ~1300m away
    ])
    dist = nearest_distance_m(12.9784, 77.6408, parks)
    assert dist is not None
    assert dist < 600  # picked the closer one


def test_nearest_distance_empty_gdf():
    """Empty GeoDataFrame returns None."""
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    dist = nearest_distance_m(12.97, 77.64, empty)
    assert dist is None


def test_compute_location_scores():
    """Full scoring pipeline with parks, lakes, metro GeoDataFrames."""
    parks = _make_gdf([(12.9829, 77.6408)])   # ~500m from listing
    lakes = _make_gdf([(12.9600, 77.6400)])    # ~2km from listing
    metro = _make_gdf([(12.9784, 77.6350)])    # ~600m from listing

    score = compute_location_scores(12.9784, 77.6408, parks, lakes, metro)
    assert isinstance(score, LocationScore)
    assert score.nearest_park_m is not None
    assert 400 < score.nearest_park_m < 600
    assert score.nearest_lake_m is not None
    assert score.nearest_lake_m > 1500
    assert score.nearest_metro_m is not None
    assert 500 < score.nearest_metro_m < 700


def test_compute_location_scores_no_data():
    """All empty GeoDataFrames → all None distances."""
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    score = compute_location_scores(12.97, 77.64, empty, empty, empty)
    assert score.nearest_park_m is None
    assert score.nearest_lake_m is None
    assert score.nearest_metro_m is None
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_geo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rental_lookup.geo'`

**Step 3: Write minimal implementation**

Create `rental_lookup/geo.py`:
```python
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import Point

from rental_lookup.models import LocationScore

# Central Bangalore bounding box
BBOX = (12.90, 77.50, 13.05, 77.70)  # south, west, north, east

# UTM zone 43N — appropriate for Bangalore (~77°E)
UTM_CRS = "EPSG:32643"


def nearest_distance_m(
    lat: float, lng: float, features: gpd.GeoDataFrame
) -> float | None:
    """Compute distance in meters from (lat, lng) to nearest feature in GeoDataFrame."""
    if features.empty:
        return None

    # Project everything to UTM for meter-based distance
    point = gpd.GeoSeries([Point(lng, lat)], crs="EPSG:4326").to_crs(UTM_CRS)
    projected = features.to_crs(UTM_CRS)

    # Compute distance from point to each feature geometry
    distances = projected.geometry.distance(point.iloc[0])
    return float(distances.min())


def compute_location_scores(
    lat: float, lng: float,
    parks: gpd.GeoDataFrame,
    lakes: gpd.GeoDataFrame,
    metro: gpd.GeoDataFrame,
) -> LocationScore:
    """Compute distances to nearest park, lake, and metro station."""
    return LocationScore(
        nearest_park_m=nearest_distance_m(lat, lng, parks),
        nearest_lake_m=nearest_distance_m(lat, lng, lakes),
        nearest_metro_m=nearest_distance_m(lat, lng, metro),
    )


def fetch_osm_features(cache_dir: Path | None = None) -> tuple[
    gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame
]:
    """Bulk-fetch parks, lakes, and metro stations for central Bangalore.

    Returns (parks_gdf, lakes_gdf, metro_gdf).
    Caches to GeoPackage files if cache_dir is provided.
    """
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        parks_path = cache_dir / "parks.gpkg"
        lakes_path = cache_dir / "lakes.gpkg"
        metro_path = cache_dir / "metro.gpkg"

        if parks_path.exists() and lakes_path.exists() and metro_path.exists():
            print("  Loading cached OSM data...")
            return (
                gpd.read_file(parks_path),
                gpd.read_file(lakes_path),
                gpd.read_file(metro_path),
            )

    import osmnx as ox

    south, west, north, east = BBOX
    print("  Fetching parks from OSM...")
    try:
        parks = ox.features_from_bbox(
            bbox=(west, south, east, north),
            tags={"leisure": ["park", "garden"]},
        )
    except Exception:
        parks = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    print("  Fetching lakes from OSM...")
    try:
        lakes = ox.features_from_bbox(
            bbox=(west, south, east, north),
            tags={"natural": "water", "water": "lake"},
        )
    except Exception:
        lakes = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    print("  Fetching metro stations from OSM...")
    try:
        metro = ox.features_from_bbox(
            bbox=(west, south, east, north),
            tags={"network": "Namma Metro"},
        )
    except Exception:
        metro = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    if cache_dir:
        # Reset index to avoid gpkg issues with MultiIndex
        for gdf, path in [(parks, parks_path), (lakes, lakes_path), (metro, metro_path)]:
            if not gdf.empty:
                gdf.reset_index(drop=True).to_file(path, driver="GPKG")
            else:
                gpd.GeoDataFrame(geometry=[], crs="EPSG:4326").to_file(path, driver="GPKG")

    return parks, lakes, metro
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_geo.py -v`
Expected: all 6 tests PASS

**Step 5: Commit**

```bash
git add rental_lookup/geo.py tests/test_geo.py
git commit -m "feat: geo module — bulk OSM fetch + spatial nearest-neighbor scoring"
```

---

### Task 4: Scorer — Hard Filters + Weighted Scoring

**Files:**
- Create: `rental_lookup/scorer.py`
- Create: `tests/test_scorer.py`

**Step 1: Write the failing test**

Create `tests/test_scorer.py`:
```python
from rental_lookup.models import Listing, LocationScore, ScoredListing
from rental_lookup.scorer import passes_hard_filters, score_listing, rank_listings


def _make_listing(**overrides) -> Listing:
    """Factory for test listings with sensible defaults."""
    defaults = dict(
        id="test1", rent=40000, deposit=200000, sqft=1000, bhk="BHK2",
        lat=12.97, lng=77.64, locality="Test", society="Test Society",
        building_type="AP", floor=3, total_floor=10, lift=True,
        parking="FOUR_WHEELER", title="2 BHK Apartment for Rent",
        url="https://www.nobroker.in/property/test",
        has_power_backup=True, has_gated_community=True,
        has_covered_parking=True, has_security=True, has_car_parking=True,
    )
    defaults.update(overrides)
    return Listing(**defaults)


def _make_location(**overrides) -> LocationScore:
    defaults = dict(nearest_park_m=300, nearest_lake_m=1000, nearest_metro_m=400)
    defaults.update(overrides)
    return LocationScore(**defaults)


# --- Hard filter tests ---

def test_hard_filter_passes_valid_listing():
    listing = _make_listing(rent=50000, sqft=1000, lat=12.97, lng=77.64)
    assert passes_hard_filters(listing) is True


def test_hard_filter_rejects_over_budget():
    listing = _make_listing(rent=70000)
    assert passes_hard_filters(listing) is False


def test_hard_filter_rejects_too_small():
    listing = _make_listing(sqft=500)
    assert passes_hard_filters(listing) is False


def test_hard_filter_rejects_no_coords():
    """This shouldn't happen (from_nobroker filters), but defense in depth."""
    listing = _make_listing(lat=0.0, lng=0.0)
    assert passes_hard_filters(listing) is False


# --- Scoring tests ---

def test_score_pet_compatibility_gated():
    """Gated community gets 10pts for pet compatibility."""
    listing = _make_listing(has_gated_community=True, title="Normal Flat")
    loc = _make_location()
    score = score_listing(listing, loc)
    # gated=10, no pet text=0 → pet_compat = 10
    assert score.total_score > 0


def test_score_pet_text_signal():
    """Title containing 'pet friendly' gets 15pts."""
    listing = _make_listing(
        has_gated_community=False, title="Pet Friendly 2 BHK Apartment"
    )
    loc = _make_location()
    score_with = score_listing(listing, loc)

    listing_without = _make_listing(
        has_gated_community=False, title="2 BHK Apartment"
    )
    score_without = score_listing(listing_without, loc)
    assert score_with.total_score > score_without.total_score


def test_score_closer_park_scores_higher():
    listing = _make_listing()
    close_park = _make_location(nearest_park_m=200)
    far_park = _make_location(nearest_park_m=800)
    score_close = score_listing(listing, close_park)
    score_far = score_listing(listing, far_park)
    assert score_close.total_score > score_far.total_score


def test_score_closer_metro_scores_higher():
    listing = _make_listing()
    close_metro = _make_location(nearest_metro_m=300)
    far_metro = _make_location(nearest_metro_m=2000)
    score_close = score_listing(listing, close_metro)
    score_far = score_listing(listing, far_metro)
    assert score_close.total_score > score_far.total_score


def test_score_power_backup_adds_10():
    listing_with = _make_listing(has_power_backup=True)
    listing_without = _make_listing(has_power_backup=False)
    loc = _make_location()
    assert score_listing(listing_with, loc).total_score - score_listing(listing_without, loc).total_score == 10


def test_score_car_parking_adds_10():
    listing_with = _make_listing(has_car_parking=True)
    listing_without = _make_listing(has_car_parking=False)
    loc = _make_location()
    assert score_listing(listing_with, loc).total_score - score_listing(listing_without, loc).total_score == 10


def test_score_floor_safety():
    """Ground/1st floor gets 5pts for floor safety."""
    low = _make_listing(floor=1)
    high = _make_listing(floor=8)
    loc = _make_location()
    assert score_listing(low, loc).total_score > score_listing(high, loc).total_score


def test_score_unknown_location_scores_zero_not_negative():
    listing = _make_listing()
    loc = LocationScore()  # all None
    score = score_listing(listing, loc)
    assert score.total_score >= 0


def test_score_bigger_space_scores_higher():
    big = _make_listing(sqft=1400)
    small = _make_listing(sqft=750)
    loc = _make_location()
    assert score_listing(big, loc).total_score > score_listing(small, loc).total_score


# --- Ranking test ---

def test_rank_listings_sorted_descending():
    """Given 3 listings with different qualities, rank descending by score."""
    great = _make_listing(
        id="great", rent=40000, sqft=1400,
        has_power_backup=True, has_gated_community=True, has_car_parking=True,
        title="Pet Friendly Gated Community",
    )
    ok = _make_listing(
        id="ok", rent=50000, sqft=1000,
        has_power_backup=True, has_gated_community=False, has_car_parking=True,
    )
    bad = _make_listing(
        id="bad", rent=58000, sqft=750,
        has_power_backup=False, has_gated_community=False, has_car_parking=False,
    )

    loc_great = _make_location(nearest_park_m=200, nearest_metro_m=300, nearest_lake_m=800)
    loc_ok = _make_location(nearest_park_m=600, nearest_metro_m=1200, nearest_lake_m=2000)
    loc_bad = _make_location(nearest_park_m=1500, nearest_metro_m=3000, nearest_lake_m=5000)

    ranked = rank_listings(
        [(great, loc_great), (bad, loc_bad), (ok, loc_ok)]
    )
    assert len(ranked) == 3
    assert ranked[0].listing.id == "great"
    assert ranked[1].listing.id == "ok"
    assert ranked[2].listing.id == "bad"
    assert ranked[0].total_score > ranked[1].total_score > ranked[2].total_score
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_scorer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rental_lookup.scorer'`

**Step 3: Write minimal implementation**

Create `rental_lookup/scorer.py`:
```python
from __future__ import annotations

import csv
from pathlib import Path

from rental_lookup.models import Listing, LocationScore, ScoredListing

# --- Constants ---
MAX_RENT = 60000
MIN_SQFT = 700


def passes_hard_filters(listing: Listing) -> bool:
    """Return True if listing passes all hard filters."""
    if listing.rent > MAX_RENT:
        return False
    if listing.sqft < MIN_SQFT:
        return False
    if not listing.lat or not listing.lng:
        return False
    return True


def _score_pet_compatibility(listing: Listing) -> float:
    """0-25 pts: pet-friendly text (15) + gated community (10)."""
    score = 0.0
    title_lower = listing.title.lower()
    if "pet" in title_lower or "pet friendly" in title_lower or "pet-friendly" in title_lower:
        score += 15.0
    if listing.has_gated_community:
        score += 10.0
    return min(score, 25.0)


def _score_greenery(loc: LocationScore) -> float:
    """0-20 pts: park proximity (15) + lake proximity (5)."""
    score = 0.0
    if loc.nearest_park_m is not None:
        if loc.nearest_park_m < 500:
            score += 15.0
        elif loc.nearest_park_m < 1000:
            score += 15.0 * (1 - (loc.nearest_park_m - 500) / 500)
        # >1000m = 0
    if loc.nearest_lake_m is not None:
        if loc.nearest_lake_m < 1500:
            score += 5.0
        elif loc.nearest_lake_m < 3000:
            score += 5.0 * (1 - (loc.nearest_lake_m - 1500) / 1500)
    return score


def _score_metro(loc: LocationScore) -> float:
    """0-15 pts based on metro distance."""
    if loc.nearest_metro_m is None:
        return 0.0
    d = loc.nearest_metro_m
    if d < 500:
        return 15.0
    elif d < 1000:
        return 12.0
    elif d < 1500:
        return 8.0
    return 0.0


def _score_space(listing: Listing) -> float:
    """0-15 pts based on sqft."""
    if listing.sqft > 1200:
        return 15.0
    elif listing.sqft > 1000:
        return 12.0
    elif listing.sqft > 800:
        return 8.0
    return 5.0


def _score_power_backup(listing: Listing) -> float:
    """0-10 pts."""
    return 10.0 if listing.has_power_backup else 0.0


def _score_parking(listing: Listing) -> float:
    """0-10 pts."""
    return 10.0 if listing.has_car_parking else 0.0


def _score_floor_safety(listing: Listing) -> float:
    """0-5 pts: ground or 1st floor = easier cat netting."""
    return 5.0 if listing.floor <= 1 else 0.0


def score_listing(listing: Listing, location: LocationScore) -> ScoredListing:
    """Compute total score for a listing."""
    total = (
        _score_pet_compatibility(listing)
        + _score_greenery(location)
        + _score_metro(location)
        + _score_space(listing)
        + _score_power_backup(listing)
        + _score_parking(listing)
        + _score_floor_safety(listing)
    )
    return ScoredListing(listing=listing, location=location, total_score=round(total, 1))


def rank_listings(
    pairs: list[tuple[Listing, LocationScore]],
) -> list[ScoredListing]:
    """Score and rank listings, descending by total_score."""
    scored = [score_listing(listing, loc) for listing, loc in pairs]
    scored.sort(key=lambda s: s.total_score, reverse=True)
    return scored


def write_csv(scored: list[ScoredListing], output_path: Path) -> None:
    """Write ranked results to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "score", "rent", "deposit", "sqft", "bhk", "locality", "society",
        "floor", "total_floor", "metro_dist_m", "park_dist_m", "lake_dist_m",
        "car_parking", "power_backup", "gated_community", "security",
        "pet_signal", "wall_color", "balcony_grills", "url",
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in scored:
            writer.writerow({
                "score": s.total_score,
                "rent": s.listing.rent,
                "deposit": s.listing.deposit,
                "sqft": s.listing.sqft,
                "bhk": s.listing.bhk,
                "locality": s.listing.locality,
                "society": s.listing.society,
                "floor": s.listing.floor,
                "total_floor": s.listing.total_floor,
                "metro_dist_m": round(s.location.nearest_metro_m) if s.location.nearest_metro_m else "N/A",
                "park_dist_m": round(s.location.nearest_park_m) if s.location.nearest_park_m else "N/A",
                "lake_dist_m": round(s.location.nearest_lake_m) if s.location.nearest_lake_m else "N/A",
                "car_parking": "Yes" if s.listing.has_car_parking else "No",
                "power_backup": "Yes" if s.listing.has_power_backup else "No",
                "gated_community": "Yes" if s.listing.has_gated_community else "No",
                "security": "Yes" if s.listing.has_security else "No",
                "pet_signal": "Yes" if "pet" in s.listing.title.lower() else "",
                "wall_color": "CHECK MANUALLY",
                "balcony_grills": "CHECK MANUALLY",
                "url": s.listing.url,
            })
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_scorer.py -v`
Expected: all 14 tests PASS

**Step 5: Commit**

```bash
git add rental_lookup/scorer.py tests/test_scorer.py
git commit -m "feat: scorer — hard filters + weighted scoring + CSV output"
```

---

### Task 5: Run Module — Orchestrator + End-to-End

**Files:**
- Create: `rental_lookup/run.py`
- Create: `rental_lookup/__main__.py`

**Step 1: Write the orchestrator**

Create `rental_lookup/run.py`:
```python
from __future__ import annotations

from pathlib import Path

from tqdm import tqdm

from rental_lookup.geo import compute_location_scores, fetch_osm_features
from rental_lookup.models import LocationScore
from rental_lookup.nobroker import fetch_all
from rental_lookup.scorer import passes_hard_filters, rank_listings, write_csv

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")


def main(cookie: str = "") -> None:
    # 1. Fetch listings from NoBroker
    print("=" * 60)
    print("STEP 1: Fetching listings from NoBroker")
    print("=" * 60)
    listings = fetch_all(cookie=cookie, raw_dir=DATA_DIR / "raw")

    # 2. Hard filter
    print(f"\nApplying hard filters (rent <= 60K, sqft >= 700)...")
    filtered = [l for l in listings if passes_hard_filters(l)]
    print(f"  {len(listings)} → {len(filtered)} after filters")

    if not filtered:
        print("No listings passed filters. Try adjusting budget or area.")
        return

    # 3. Load OSM geo data
    print("\n" + "=" * 60)
    print("STEP 2: Loading geospatial data (parks, lakes, metro)")
    print("=" * 60)
    parks, lakes, metro = fetch_osm_features(cache_dir=DATA_DIR / "cache")
    print(f"  Parks: {len(parks)}, Lakes: {len(lakes)}, Metro stations: {len(metro)}")

    # 4. Score each listing
    print("\n" + "=" * 60)
    print("STEP 3: Scoring listings")
    print("=" * 60)
    pairs = []
    for listing in tqdm(filtered, desc="Scoring"):
        loc = compute_location_scores(listing.lat, listing.lng, parks, lakes, metro)
        pairs.append((listing, loc))

    ranked = rank_listings(pairs)

    # 5. Write output
    output_path = OUTPUT_DIR / "results.csv"
    write_csv(ranked, output_path)
    print(f"\nResults written to {output_path}")

    # 6. Print top 10
    print("\n" + "=" * 60)
    print("TOP 10 LISTINGS")
    print("=" * 60)
    for i, s in enumerate(ranked[:10], 1):
        l = s.listing
        loc = s.location
        print(f"\n{i}. Score: {s.total_score}/100")
        print(f"   {l.bhk} | {l.sqft} sqft | ₹{l.rent:,}/mo | Deposit: ₹{l.deposit:,}")
        print(f"   {l.locality} — {l.society}")
        print(f"   Floor: {l.floor}/{l.total_floor} | Parking: {l.parking}")
        print(f"   Metro: {round(loc.nearest_metro_m)}m" if loc.nearest_metro_m else "   Metro: N/A", end="")
        print(f" | Park: {round(loc.nearest_park_m)}m" if loc.nearest_park_m else " | Park: N/A", end="")
        print(f" | Lake: {round(loc.nearest_lake_m)}m" if loc.nearest_lake_m else " | Lake: N/A")
        flags = []
        if l.has_power_backup: flags.append("⚡ Power Backup")
        if l.has_gated_community: flags.append("🏘 Gated")
        if l.has_car_parking: flags.append("🚗 Parking")
        if l.has_security: flags.append("🔒 Security")
        if "pet" in l.title.lower(): flags.append("🐱 Pet Friendly")
        print(f"   {' | '.join(flags)}")
        print(f"   {l.url}")
```

Create `rental_lookup/__main__.py`:
```python
import sys

from rental_lookup.run import main

if __name__ == "__main__":
    cookie = ""
    if len(sys.argv) > 1:
        cookie = sys.argv[1]
    main(cookie=cookie)
```

**Step 2: Run all tests to verify nothing broke**

Run: `python3 -m pytest tests/ -v`
Expected: all tests PASS (models: 7, nobroker: 5, geo: 6, scorer: 14 = 32 total)

**Step 3: Commit**

```bash
git add rental_lookup/run.py rental_lookup/__main__.py
git commit -m "feat: run module — orchestrate fetch, score, and output pipeline"
```

---

### Task 6: End-to-End Smoke Test

**Step 1: Run the tool against real NoBroker API**

Run: `python3 -m rental_lookup`

If 403 error: grab a cookie string from Chrome DevTools and run:
```bash
python3 -m rental_lookup "PASTE_COOKIE_HERE"
```

**Step 2: Verify output**

- Check `output/results.csv` exists and has rows
- Check `data/raw/` has JSON files
- Check `data/cache/` has .gpkg files
- Verify top-10 printed to terminal looks reasonable

**Step 3: Commit everything**

```bash
git add -A
git commit -m "feat: rental-lookup v1 complete — NoBroker + OSM scoring pipeline"
```

---

Plan complete and saved to `docs/plans/2026-04-13-rental-lookup-tdd-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
