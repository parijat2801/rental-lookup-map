import csv
import re
from pathlib import Path
from typing import List, Tuple

from rental_lookup.models import Listing, LocationScore, ScoredListing

MAX_RENT = 60000
MIN_SQFT = 700


def passes_hard_filters(listing: Listing) -> bool:
    if listing.rent > MAX_RENT:
        return False
    if listing.sqft < MIN_SQFT:
        return False
    if listing.lat == 0.0 or listing.lng == 0.0:
        return False
    return True


def _has_pet_signal(title: str) -> bool:
    return bool(re.search(r'\bpet\b', title, re.IGNORECASE))


def _score_pet_compatibility(listing: Listing) -> float:
    score = 0.0
    if _has_pet_signal(listing.title):
        score += 15.0
    if listing.has_gated_community:
        score += 10.0
    return min(score, 25.0)


def _score_greenery(loc: LocationScore) -> float:
    score = 0.0
    if loc.nearest_park_m is not None:
        if loc.nearest_park_m < 500:
            score += 15.0
        elif loc.nearest_park_m < 1000:
            score += 15.0 * (1 - (loc.nearest_park_m - 500) / 500)
    if loc.nearest_lake_m is not None:
        if loc.nearest_lake_m < 1500:
            score += 5.0
        elif loc.nearest_lake_m < 3000:
            score += 5.0 * (1 - (loc.nearest_lake_m - 1500) / 1500)
    return score


def _score_metro(loc: LocationScore) -> float:
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
    if listing.sqft > 1200:
        return 15.0
    elif listing.sqft > 1000:
        return 12.0
    elif listing.sqft > 800:
        return 8.0
    return 5.0


def _score_power_backup(listing: Listing) -> float:
    return 10.0 if listing.has_power_backup else 0.0


def _score_parking(listing: Listing) -> float:
    return 10.0 if listing.has_car_parking else 0.0


def _score_floor_safety(listing: Listing) -> float:
    return 5.0 if listing.floor <= 1 else 0.0


def score_listing(listing: Listing, location: LocationScore) -> ScoredListing:
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
    pairs: List[Tuple[Listing, LocationScore]],
) -> List[ScoredListing]:
    scored = [score_listing(listing, loc) for listing, loc in pairs]
    scored.sort(key=lambda s: (-s.total_score, s.listing.rent))
    return scored


def write_csv(scored: List[ScoredListing], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "score", "rent", "deposit", "sqft", "bhk", "locality", "society",
        "floor", "total_floor", "metro_dist_m", "park_dist_m", "lake_dist_m",
        "car_parking", "power_backup", "gated_community", "security",
        "pet_signal", "wall_color", "balcony_grills", "photo_url", "url",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
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
                "metro_dist_m": round(s.location.nearest_metro_m) if s.location.nearest_metro_m is not None else "N/A",
                "park_dist_m": round(s.location.nearest_park_m) if s.location.nearest_park_m is not None else "N/A",
                "lake_dist_m": round(s.location.nearest_lake_m) if s.location.nearest_lake_m is not None else "N/A",
                "car_parking": "Yes" if s.listing.has_car_parking else "No",
                "power_backup": "Yes" if s.listing.has_power_backup else "No",
                "gated_community": "Yes" if s.listing.has_gated_community else "No",
                "security": "Yes" if s.listing.has_security else "No",
                "pet_signal": "Yes" if _has_pet_signal(s.listing.title) else "",
                "wall_color": "CHECK MANUALLY",
                "balcony_grills": "CHECK MANUALLY",
                "photo_url": s.listing.photo_url,
                "url": s.listing.url,
            })
