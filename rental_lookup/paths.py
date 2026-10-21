"""Every file and folder the project reads or writes, relative to the repo root.

The on-disk names are kept short and stable (CI caches them); the constant names
describe what each one holds.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = REPO_ROOT / "output"

# Raw API responses, one JSON file per results page (re-fetched every run).
NOBROKER_PAGES_DIR = DATA_DIR / "raw"
PREVIOUS_NOBROKER_PAGES_DIR = DATA_DIR / "raw_prev"  # last run's pages, to spot delisted listings
MAGICBRICKS_PAGES_DIR = DATA_DIR / "raw_mb"
FACEBOOK_POSTS_DIR = DATA_DIR / "fb"

# Long-lived state, committed to git and cached by CI.
STARS_PATH = CACHE_DIR / "stars_and_dismissals.json"  # user stars/dismissals (published as stars.json)
FIRST_SEEN_PATH = CACHE_DIR / "first_seen.json"  # listing url -> date we first saw it
LISTING_DETAILS_PATH = CACHE_DIR / "detail_enrichment.json"  # listing id -> NoBroker detail-page extras
# listing id -> NoBroker [transit, lifestyle] from the detail page (null = it has none either),
# for listings whose search result came without them
PLATFORM_SCORES_PATH = CACHE_DIR / "platform_scores.json"
FAKE_LOCATION_IDS_PATH = CACHE_DIR / "fake_location_ids.json"  # listing ids with known-bogus coordinates

METRO_LINES_PATH = DATA_DIR / "metro_lines.json"  # map overlay, from scripts/fetch_metro_lines.py
ENV_PATH = REPO_ROOT / ".env"  # optional local secrets (gitignored)

# Outputs
MAP_TEMPLATE_PATH = Path(__file__).resolve().parent / "webmap" / "template.html"
MAP_PAGE_PATH = OUTPUT_DIR / "map.html"
RANKING_CSV_PATH = OUTPUT_DIR / "results.csv"
