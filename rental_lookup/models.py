from dataclasses import dataclass
from typing import Optional


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
    photo_url: str
    facing: str
    balconies: int
    age: int
    water_supply: str
    negotiable: bool
    nb_transit: float
    nb_lifestyle: float
    has_power_backup: bool
    has_gated_community: bool
    has_covered_parking: bool
    has_security: bool
    has_fire_safety: bool
    has_car_parking: bool

    @classmethod
    def from_nobroker(cls, raw: dict) -> Optional["Listing"]:
        lat = raw.get("latitude")
        lng = raw.get("longitude")
        if lat is None or lng is None or lat == 0 or lng == 0:
            return None

        amenities = raw.get("amenitiesMap") or {}
        parking_val = raw.get("parking", "NONE")
        detail_url = raw.get("detailUrl", "")
        score_data = raw.get("score") or {}

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
            url="https://www.nobroker.in" + detail_url if detail_url else "",
            photo_url=raw.get("originalImageUrl", ""),
            facing=raw.get("facing", ""),
            balconies=raw.get("balconies", 0) or 0,
            age=raw.get("propertyAge", 99),
            water_supply=raw.get("waterSupply", ""),
            negotiable=raw.get("negotiable", False),
            nb_transit=score_data.get("transit", 0) if isinstance(score_data, dict) else 0,
            nb_lifestyle=score_data.get("lifestyle", 0) if isinstance(score_data, dict) else 0,
            has_power_backup=bool(amenities.get("PB")),
            has_gated_community=bool(amenities.get("GP")),
            has_covered_parking=bool(amenities.get("CPA")),
            has_security=bool(amenities.get("SECURITY")),
            has_fire_safety=bool(amenities.get("FS")),
            has_car_parking=parking_val in ("FOUR_WHEELER", "BOTH"),
        )


@dataclass
class LocationScore:
    nearest_park_m: Optional[float] = None
    nearest_lake_m: Optional[float] = None
    nearest_metro_m: Optional[float] = None


@dataclass
class ScoredListing:
    listing: Listing
    location: LocationScore
    total_score: float
