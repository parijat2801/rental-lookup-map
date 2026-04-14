import csv
import re
from pathlib import Path
from typing import List, Tuple

from rental_lookup.models import Listing, LocationScore, ScoredListing

MAX_RENT = 70000
MIN_RENT = 30000
MIN_SQFT = 700


def passes_hard_filters(listing: Listing) -> bool:
    if listing.rent > MAX_RENT:
        return False
    if listing.rent < MIN_RENT:
        return False
    if listing.sqft < MIN_SQFT:
        return False
    if listing.lat == 0.0 or listing.lng == 0.0:
        return False
    if listing.building_type == "IH":
        return False
    return True


def _has_pet_signal(title: str) -> bool:
    return bool(re.search(r'\bpet\b', title, re.IGNORECASE))


def _score_value(listing: Listing) -> float:
    """0-25: sqft per 1000 rupees — big + cheap = happy."""
    value = listing.sqft / listing.rent * 1000 if listing.rent > 0 else 0
    if value >= 50:
        return 25.0
    elif value >= 40:
        return 20.0
    elif value >= 30:
        return 15.0
    return 10.0


def _score_natural_light(listing: Listing) -> float:
    """0-10: facing + balconies."""
    score = 0.0
    if listing.facing in ("E", "SE", "S", "NE"):
        score += 5.0
    if listing.balconies >= 1:
        score += 5.0
    return score


def _score_freshness(listing: Listing) -> float:
    """0-10: newer property = likely better condition, white walls."""
    if listing.age <= 3:
        return 10.0
    elif listing.age <= 7:
        return 7.0
    elif listing.age <= 15:
        return 3.0
    return 0.0


def _score_amenities(listing: Listing) -> float:
    """0-15: power backup + security + gated + fire safety."""
    score = 0.0
    if listing.has_power_backup:
        score += 5.0
    if listing.has_security:
        score += 5.0
    if listing.has_gated_community:
        score += 3.0
    if listing.has_fire_safety:
        score += 2.0
    return score


def _score_parking(listing: Listing) -> float:
    """0-5: car parking."""
    return 5.0 if listing.has_car_parking else 0.0


def _score_nb_quality(listing: Listing) -> float:
    """0-10: NoBroker's own transit + lifestyle scores."""
    score = 0.0
    if listing.nb_transit >= 8:
        score += 5.0
    elif listing.nb_transit >= 7:
        score += 3.0
    if listing.nb_lifestyle >= 8:
        score += 5.0
    elif listing.nb_lifestyle >= 6:
        score += 3.0
    return score


def _score_water(listing: Listing) -> float:
    """0-5: water supply reliability."""
    if listing.water_supply in ("CORPORATION", "BOREWELL_AND_CORPORATION", "CORP_BORE"):
        return 5.0
    elif listing.water_supply == "BOREWELL":
        return 2.0
    return 0.0


def _score_negotiable(listing: Listing) -> float:
    """0-5: owner willing to negotiate."""
    return 5.0 if listing.negotiable else 0.0


def score_listing(listing: Listing, location: LocationScore) -> ScoredListing:
    total = (
        _score_natural_light(listing)
        + _score_freshness(listing)
        + _score_amenities(listing)
        + _score_parking(listing)
        + _score_nb_quality(listing)
        + _score_water(listing)
        + _score_negotiable(listing)
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
        "floor", "total_floor", "facing", "balconies", "age",
        "metro_dist_m", "park_dist_m", "lake_dist_m",
        "car_parking", "power_backup", "gated_community", "security",
        "nb_transit", "nb_lifestyle", "water_supply", "negotiable",
        "pet_signal", "photo_url", "url",
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
                "facing": s.listing.facing,
                "balconies": s.listing.balconies,
                "age": s.listing.age,
                "metro_dist_m": round(s.location.nearest_metro_m) if s.location.nearest_metro_m is not None else "N/A",
                "park_dist_m": round(s.location.nearest_park_m) if s.location.nearest_park_m is not None else "N/A",
                "lake_dist_m": round(s.location.nearest_lake_m) if s.location.nearest_lake_m is not None else "N/A",
                "car_parking": "Yes" if s.listing.has_car_parking else "No",
                "power_backup": "Yes" if s.listing.has_power_backup else "No",
                "gated_community": "Yes" if s.listing.has_gated_community else "No",
                "security": "Yes" if s.listing.has_security else "No",
                "nb_transit": s.listing.nb_transit,
                "nb_lifestyle": s.listing.nb_lifestyle,
                "water_supply": s.listing.water_supply,
                "negotiable": "Yes" if s.listing.negotiable else "No",
                "pet_signal": "Yes" if _has_pet_signal(s.listing.title) else "",
                "photo_url": s.listing.photo_url,
                "url": s.listing.url,
            })
