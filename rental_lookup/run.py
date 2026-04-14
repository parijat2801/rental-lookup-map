from pathlib import Path
from typing import List, Tuple

from tqdm import tqdm

from rental_lookup.geo import compute_location_scores, fetch_osm_features
from rental_lookup.models import Listing, LocationScore
from rental_lookup.nobroker import fetch_all, load_from_raw
from rental_lookup.scorer import passes_hard_filters, rank_listings, write_csv

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")


def main(cookie: str = "") -> None:
    print("=" * 60)
    print("STEP 1: Loading listings")
    print("=" * 60)
    raw_dir = DATA_DIR / "raw"
    listings = fetch_all(cookie=cookie, raw_dir=raw_dir)

    print(f"\nApplying hard filters (rent <= 60K, sqft >= 700)...")
    filtered = [l for l in listings if passes_hard_filters(l)]
    print(f"  {len(listings)} -> {len(filtered)} after filters")

    if not filtered:
        print("No listings passed filters. Try adjusting budget or area.")
        return

    print("\n" + "=" * 60)
    print("STEP 2: Loading geospatial data (parks, lakes, metro)")
    print("=" * 60)
    parks, lakes, metro = fetch_osm_features(cache_dir=DATA_DIR / "cache")
    print(f"  Parks: {len(parks)}, Lakes: {len(lakes)}, Metro stations: {len(metro)}")

    print("\n" + "=" * 60)
    print("STEP 3: Scoring listings")
    print("=" * 60)
    pairs = []
    for listing in tqdm(filtered, desc="Scoring"):
        loc = compute_location_scores(listing.lat, listing.lng, parks, lakes, metro)
        pairs.append((listing, loc))

    ranked = rank_listings(pairs)

    output_path = OUTPUT_DIR / "results.csv"
    write_csv(ranked, output_path)
    print(f"\nResults written to {output_path}")

    print("\n" + "=" * 60)
    print("TOP 10 LISTINGS")
    print("=" * 60)
    for i, s in enumerate(ranked[:10], 1):
        l = s.listing
        loc = s.location
        print(f"\n{i}. Score: {s.total_score}/100")
        print(f"   {l.bhk} | {l.sqft} sqft | Rs.{l.rent:,}/mo | Deposit: Rs.{l.deposit:,}")
        print(f"   {l.locality} -- {l.society}")
        print(f"   Floor: {l.floor}/{l.total_floor} | Parking: {l.parking}")
        metro_str = f"{round(loc.nearest_metro_m)}m" if loc.nearest_metro_m is not None else "N/A"
        park_str = f"{round(loc.nearest_park_m)}m" if loc.nearest_park_m is not None else "N/A"
        lake_str = f"{round(loc.nearest_lake_m)}m" if loc.nearest_lake_m is not None else "N/A"
        print(f"   Metro: {metro_str} | Park: {park_str} | Lake: {lake_str}")
        flags = []
        if l.has_power_backup: flags.append("Power Backup")
        if l.has_gated_community: flags.append("Gated")
        if l.has_car_parking: flags.append("Parking")
        if l.has_security: flags.append("Security")
        print(f"   {' | '.join(flags)}")
        print(f"   {l.url}")
