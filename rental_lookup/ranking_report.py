"""CLI ranking: fetch NoBroker listings, score them against OSM data, write results.csv."""
from __future__ import annotations

from typing import Optional

from tqdm import tqdm

from rental_lookup.location import fetch_osm_features, measure_nearby_distances, to_metric_crs
from rental_lookup.paths import CACHE_DIR, NOBROKER_PAGES_DIR, RANKING_CSV_PATH
from rental_lookup.scoring import MAX_RENT, MIN_RENT, MIN_SQFT, passes_hard_filters, rank_listings, write_csv
from rental_lookup.sources.nobroker import fetch_all


def _banner(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def _format_metres(distance: Optional[float]) -> str:
    return f"{round(distance)}m" if distance is not None else "N/A"


def main(cookie: str = "") -> None:
    _banner("STEP 1: Loading listings")
    listings = fetch_all(cookie=cookie, pages_dir=NOBROKER_PAGES_DIR)

    print(f"\nApplying hard filters (rent {MIN_RENT // 1000}K-{MAX_RENT // 1000}K, sqft >= {MIN_SQFT})...")
    candidates = [listing for listing in listings if passes_hard_filters(listing)]
    print(f"  {len(listings)} -> {len(candidates)} after filters")
    if not candidates:
        print("No listings passed filters. Try adjusting budget or area.")
        return

    _banner("STEP 2: Loading geospatial data (parks, lakes, metro)")
    parks, lakes, metro_stations = fetch_osm_features(cache_dir=CACHE_DIR)
    print(f"  Parks: {len(parks)}, Lakes: {len(lakes)}, Metro stations: {len(metro_stations)}")
    # Project once up front rather than per listing.
    parks, lakes, metro_stations = to_metric_crs(parks), to_metric_crs(lakes), to_metric_crs(metro_stations)

    _banner("STEP 3: Scoring listings")
    listings_with_distances = [
        (listing, measure_nearby_distances(listing.lat, listing.lng, parks, lakes, metro_stations))
        for listing in tqdm(candidates, desc="Scoring")
    ]
    ranked = rank_listings(listings_with_distances)

    write_csv(ranked, RANKING_CSV_PATH)
    print(f"\nResults written to {RANKING_CSV_PATH}")

    _banner("TOP 10 LISTINGS")
    for rank, result in enumerate(ranked[:10], 1):
        listing, nearby = result.listing, result.nearby
        features = [label for label, present in (
            ("Power Backup", listing.has_power_backup), ("Gated", listing.is_gated_community),
            ("Parking", listing.has_car_parking), ("Security", listing.has_security),
        ) if present]
        print(f"\n{rank}. Score: {result.total_score}/100")
        print(f"   {listing.bhk} | {listing.sqft} sqft | Rs.{listing.rent:,}/mo | Deposit: Rs.{listing.deposit:,}")
        print(f"   {listing.locality} -- {listing.society}")
        print(f"   Floor: {listing.floor}/{listing.total_floors} | Parking: {listing.parking}")
        print(f"   Metro: {_format_metres(nearby.nearest_metro_m)} | Park: {_format_metres(nearby.nearest_park_m)}"
              f" | Lake: {_format_metres(nearby.nearest_lake_m)}")
        print(f"   {' | '.join(features)}")
        print(f"   {listing.url}")
