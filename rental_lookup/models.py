"""Data models shared by the scrapers, the CLI ranking and the map builder."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

NOBROKER_BASE_URL = "https://www.nobroker.in"
CAR_PARKING_TYPES = ("FOUR_WHEELER", "BOTH")

# Lower-case substrings that identify reputed builders in society names / titles.
BRANDED_BUILDERS = frozenset([
    'prestige', 'brigade', 'sobha', 'mantri', 'puravankara', 'salarpuria',
    'godrej', 'embassy', 'raheja', 'mahaveer', 'nitesh', 'ds max', 'sattva',
    'shriram', 'sjr', 'sumadhura', 'rohan', 'dnr', 'gopalan', 'purva', 'adarsh',
    'century', 'arvind', 'total environment', 'vaishnavi', 'casagrand',
])


def mentions_branded_builder(text: str) -> bool:
    """True if `text` (society name, title, ...) names a branded builder."""
    text = (text or "").lower()
    return any(builder in text for builder in BRANDED_BUILDERS)


def nobroker_platform_scores(raw_listing: dict) -> tuple[float, float]:
    """NoBroker's own (transit, lifestyle) ratings; `score` is sometimes null or not a dict."""
    scores = raw_listing.get("score")
    if not isinstance(scores, dict):
        return 0, 0
    return scores.get("transit", 0), scores.get("lifestyle", 0)


@dataclass
class Listing:
    """A rental listing normalised across platforms (NoBroker, MagicBricks)."""
    id: str
    rent: int
    deposit: int
    sqft: int
    bhk: str  # "BHK1" / "BHK2" / "BHK3" ...
    lat: float
    lng: float
    locality: str
    society: str
    building_type: str  # "AP" apartment, "IH" independent house, ...
    floor: int
    total_floors: int
    has_lift: Optional[bool]  # None = unknown
    parking: str  # "" = unknown; NONE / TWO_WHEELER / FOUR_WHEELER / BOTH
    title: str
    url: str
    photo_url: str
    facing: str  # compass code, e.g. "E", "NE"
    balconies: int
    age_years: int  # 99 = unknown
    water_supply: str
    is_negotiable: bool
    nobroker_transit_score: float
    nobroker_lifestyle_score: float
    has_power_backup: bool
    is_gated_community: bool
    has_covered_parking: bool
    has_security: bool
    has_fire_safety: bool
    has_car_parking: bool

    @classmethod
    def from_nobroker(cls, raw: dict) -> Optional[Listing]:
        """Build from a raw NoBroker API item; None if it has no usable coordinates."""
        lat, lng = raw.get("latitude"), raw.get("longitude")
        if not lat or not lng:
            return None

        amenities = raw.get("amenitiesMap") or {}
        parking = raw["parking"] if raw.get("parking") is not None else ""
        balconies = raw.get("balconies")
        detail_path = raw.get("detailUrl", "")
        transit_score, lifestyle_score = nobroker_platform_scores(raw)

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
            total_floors=raw.get("totalFloor", 0),
            has_lift=raw["lift"] if "lift" in raw else None,
            parking=parking,
            title=raw.get("propertyTitle", ""),
            url=NOBROKER_BASE_URL + detail_path if detail_path else "",
            photo_url=raw.get("originalImageUrl", ""),
            facing=raw.get("facing", ""),
            balconies=balconies if balconies is not None else -1,
            age_years=raw.get("propertyAge", 99),
            water_supply=raw.get("waterSupply", ""),
            is_negotiable=raw.get("negotiable", False),
            nobroker_transit_score=transit_score,
            nobroker_lifestyle_score=lifestyle_score,
            has_power_backup=bool(amenities.get("PB")),
            is_gated_community=bool(amenities.get("GP")),
            has_covered_parking=bool(amenities.get("CPA")),
            has_security=bool(amenities.get("SECURITY")),
            has_fire_safety=bool(amenities.get("FS")),
            has_car_parking=parking in CAR_PARKING_TYPES,
        )


@dataclass
class NearbyDistances:
    """Metres to the nearest park / lake / metro station; None when there is no data."""
    nearest_park_m: Optional[float] = None
    nearest_lake_m: Optional[float] = None
    nearest_metro_m: Optional[float] = None


@dataclass
class ScoredListing:
    listing: Listing
    nearby: NearbyDistances
    total_score: float
