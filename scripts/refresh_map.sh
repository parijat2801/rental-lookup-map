#!/usr/bin/env bash
# Local full refresh: fetch fresh listings, enrich the top ones, rebuild output/map.html.
# Usage: scripts/refresh_map.sh   (uses .venv/bin/python if present, else python3)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

echo "=== Step 1: Back up previous data + fetch fresh from NoBroker ==="
# The previous run becomes data/raw_prev, which the map uses to show delisted
# listings. Also forces a fresh fetch (fetch_all skips neighbourhoods already in data/raw).
if compgen -G "data/raw/*.json" > /dev/null; then
    rm -rf data/raw_prev
    mv data/raw data/raw_prev
fi
mkdir -p data/raw
"$PY" -m rental_lookup.sources nobroker

echo
echo "=== Step 2: Fetch fresh from MagicBricks ==="
rm -rf data/raw_mb
"$PY" -m rental_lookup.sources magicbricks

echo
echo "=== Step 3: Fetch fresh from 99acres ==="
rm -rf data/raw_9a
"$PY" -m rental_lookup.sources 99acres

echo
echo "=== Step 4: Fetch fresh from Property Angel ==="
# Keeps data/raw_pa: details are reused and only new properties are fetched (the API is rate-limited).
"$PY" -m rental_lookup.sources propertyangel

echo
echo "=== Step 5: Rank NoBroker listings into output/results.csv ==="
"$PY" -m rental_lookup

echo
echo "=== Step 6: Fetch detail pages for the top 300 ==="
"$PY" -m rental_lookup.enrichment.listing_details 300

echo
echo "=== Step 7: Look up NoBroker ratings missing from search results ==="
"$PY" -m rental_lookup.enrichment.listing_details scores

echo
echo "=== Step 8: Rebuild map ==="
"$PY" -m rental_lookup.webmap.builder

echo
echo "=== Done! Map updated at $(date) ==="
