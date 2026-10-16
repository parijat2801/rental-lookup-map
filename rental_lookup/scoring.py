"""Hard filters and a 0-100+ suitability score for the CLI ranking (results.csv).

The interactive map has its own (client-side) scoring in webmap/template.html.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

from rental_lookup.models import Listing, NearbyDistances, ScoredListing

MAX_RENT = 70000
MIN_RENT = 30000
MIN_SQFT = 700

_PET_WORD = re.compile(r"\bpet\b", re.IGNORECASE)  # word boundary: "carpet" must not match


def passes_hard_filters(listing: Listing) -> bool:
    return (
        MIN_RENT <= listing.rent <= MAX_RENT
        and listing.sqft >= MIN_SQFT
        and listing.lat != 0.0 and listing.lng != 0.0
        and listing.building_type != "IH"  # independent houses excluded
    )


def _mentions_pets(title: str) -> bool:
    return bool(_PET_WORD.search(title))


def _score_pet_compatibility(listing: Listing) -> float:
    """0-15: pet-friendly signals (text mention + gated community)."""
    points = (10.0 if _mentions_pets(listing.title) else 0.0) + (5.0 if listing.is_gated_community else 0.0)
    return min(points, 15.0)


def _linear_falloff(distance: Optional[float], full_until: float, zero_at: float, points: float) -> float:
    """`points` up to `full_until` metres, then linearly down to 0 at `zero_at`."""
    if distance is None or distance >= zero_at:
        return 0.0
    if distance < full_until:
        return points
    return points * (1 - (distance - full_until) / (zero_at - full_until))


def _score_greenery(nearby: NearbyDistances) -> float:
    """0-15: proximity to parks (10) and lakes (5)."""
    return (_linear_falloff(nearby.nearest_park_m, 500, 1000, 10.0)
            + _linear_falloff(nearby.nearest_lake_m, 1500, 3000, 5.0))


def _score_metro(nearby: NearbyDistances) -> float:
    """0-15: proximity to a metro station."""
    distance = nearby.nearest_metro_m
    if distance is None:
        return 0.0
    return 15.0 if distance < 500 else 12.0 if distance < 1000 else 8.0 if distance < 1500 else 0.0


def _score_space(listing: Listing) -> float:
    """0-10: bigger apartment = more room for cat + humans."""
    sqft = listing.sqft
    return 10.0 if sqft > 1200 else 8.0 if sqft > 1000 else 5.0 if sqft > 800 else 0.0


def _score_floor_safety(listing: Listing) -> float:
    """0-5: lower floors are safer for cats near windows/balconies."""
    return 5.0 if listing.floor <= 3 else 0.0


def _score_natural_light(listing: Listing) -> float:
    """0-10: good facing + at least one balcony."""
    return ((5.0 if listing.facing in ("E", "SE", "S", "NE") else 0.0)
            + (5.0 if listing.balconies >= 1 else 0.0))


def _score_freshness(listing: Listing) -> float:
    """0-10: newer property = likely better condition, white walls."""
    age = listing.age_years
    return 10.0 if age <= 3 else 7.0 if age <= 7 else 3.0 if age <= 15 else 0.0


def _score_amenities(listing: Listing) -> float:
    """0-15: power backup + security + gated + fire safety."""
    return ((5.0 if listing.has_power_backup else 0.0)
            + (5.0 if listing.has_security else 0.0)
            + (3.0 if listing.is_gated_community else 0.0)
            + (2.0 if listing.has_fire_safety else 0.0))


def _score_parking(listing: Listing) -> float:
    """0-5: car parking."""
    return 5.0 if listing.has_car_parking else 0.0


def _score_nobroker_ratings(listing: Listing) -> float:
    """0-10: NoBroker's own transit + lifestyle scores."""
    transit, lifestyle = listing.nobroker_transit_score, listing.nobroker_lifestyle_score
    return ((5.0 if transit >= 8 else 3.0 if transit >= 7 else 0.0)
            + (5.0 if lifestyle >= 8 else 3.0 if lifestyle >= 6 else 0.0))


def _score_water(listing: Listing) -> float:
    """0-5: water supply reliability."""
    if listing.water_supply in ("CORPORATION", "BOREWELL_AND_CORPORATION", "CORP_BORE"):
        return 5.0
    return 2.0 if listing.water_supply == "BOREWELL" else 0.0


def _score_negotiable(listing: Listing) -> float:
    """0-5: owner willing to negotiate."""
    return 5.0 if listing.is_negotiable else 0.0


_LISTING_CRITERIA = (
    _score_pet_compatibility, _score_space, _score_floor_safety, _score_natural_light,
    _score_freshness, _score_amenities, _score_parking, _score_nobroker_ratings,
    _score_water, _score_negotiable,
)
_LOCATION_CRITERIA = (_score_greenery, _score_metro)


def score_listing(listing: Listing, nearby: NearbyDistances) -> ScoredListing:
    total = (sum(criterion(listing) for criterion in _LISTING_CRITERIA)
             + sum(criterion(nearby) for criterion in _LOCATION_CRITERIA))
    return ScoredListing(listing=listing, nearby=nearby, total_score=round(total, 1))


def rank_listings(listings_with_distances: list[tuple[Listing, NearbyDistances]]) -> list[ScoredListing]:
    """Score and sort best-first; ties go to the cheaper listing."""
    scored = [score_listing(listing, nearby) for listing, nearby in listings_with_distances]
    scored.sort(key=lambda result: (-result.total_score, result.listing.rent))
    return scored


def _yes_no(flag: bool) -> str:
    return "Yes" if flag else "No"


def _whole_metres(distance: Optional[float]):
    return round(distance) if distance is not None else "N/A"


CSV_FIELDS = (
    "score", "rent", "deposit", "sqft", "bhk", "locality", "society",
    "floor", "total_floor", "facing", "balconies", "age",
    "metro_dist_m", "park_dist_m", "lake_dist_m",
    "car_parking", "power_backup", "gated_community", "security",
    "nb_transit", "nb_lifestyle", "water_supply", "negotiable",
    "pet_signal", "photo_url", "url",
)


def write_csv(ranked: list[ScoredListing], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for result in ranked:
        listing, nearby = result.listing, result.nearby
        rows.append({
            "score": result.total_score,
            "rent": listing.rent,
            "deposit": listing.deposit,
            "sqft": listing.sqft,
            "bhk": listing.bhk,
            "locality": listing.locality,
            "society": listing.society,
            "floor": listing.floor,
            "total_floor": listing.total_floors,
            "facing": listing.facing,
            "balconies": listing.balconies,
            "age": listing.age_years,
            "metro_dist_m": _whole_metres(nearby.nearest_metro_m),
            "park_dist_m": _whole_metres(nearby.nearest_park_m),
            "lake_dist_m": _whole_metres(nearby.nearest_lake_m),
            "car_parking": _yes_no(listing.has_car_parking),
            "power_backup": _yes_no(listing.has_power_backup),
            "gated_community": _yes_no(listing.is_gated_community),
            "security": _yes_no(listing.has_security),
            "nb_transit": listing.nobroker_transit_score,
            "nb_lifestyle": listing.nobroker_lifestyle_score,
            "water_supply": listing.water_supply,
            "negotiable": _yes_no(listing.is_negotiable),
            "pet_signal": "Yes" if _mentions_pets(listing.title) else "",
            "photo_url": listing.photo_url,
            "url": listing.url,
        })
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
