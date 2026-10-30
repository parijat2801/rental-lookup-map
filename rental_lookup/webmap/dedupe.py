"""Same-flat cross-platform dedupe for map records.

Drops MagicBricks / 99acres / Property Angel re-listings of a flat already kept
(usually NoBroker). Requires a named society and matching floor so different
units in the same building are not collapsed. Platform IDs and photo URLs are
not comparable across sources.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

# place_key()s of society names that describe a building type rather than a property
GENERIC_SOCIETY_KEYS = {
    "independenthouse", "independentbuilding", "independentfloor", "individualhouse",
    "standalonebuilding", "standalone", "villa", "na", "none",
}

RENT_RELATIVE = 0.05
RENT_ABSOLUTE = 3000  # rupees
DEPOSIT_RELATIVE = 0.10
SQFT_RELATIVE = 0.10
MAX_DISTANCE_M = 100


def coordinate_key(lat: float, lng: float) -> tuple[float, float]:
    return round(lat, 4), round(lng, 4)  # ~11m grid


def place_key(name: str) -> str:
    """Comparable form of a society/locality name: "Delta - The Signature, X" -> "deltasignature"."""
    name = re.sub(r"\bthe\b", "", (name or "").split(",")[0].lower())
    return re.sub(r"[^a-z0-9]", "", name)


def society_keys(record: dict) -> set[str]:
    """Non-generic place keys from society and optional buildingName."""
    keys = set()
    for name in (record.get("society") or "", record.get("buildingName") or ""):
        key = place_key(name)
        if key and key not in GENERIC_SOCIETY_KEYS:
            keys.add(key)
    return keys


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _within_relative_or_abs(a: float, b: float, relative: float, absolute: float = 0) -> bool:
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) <= absolute or abs(a - b) / max(a, b) <= relative


def _within_relative(a: float, b: float, relative: float) -> bool:
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= relative


def _floors_known_and_equal(a: dict, b: dict) -> bool:
    if not a.get("floorKnown", True) or not b.get("floorKnown", True):
        return False
    return a.get("floor") == b.get("floor")


def _total_floors_compatible(a: dict, b: dict) -> bool:
    ta, tb = a.get("totalFloors") or 0, b.get("totalFloors") or 0
    if ta <= 0 or tb <= 0:
        return True  # unknown on either side: do not reject
    if ta == tb:
        return True
    return abs(ta - tb) <= 1 and max(ta, tb) >= 10


def _near(a: dict, b: dict) -> bool:
    lat1, lng1 = a.get("lat"), a.get("lng")
    lat2, lng2 = b.get("lat"), b.get("lng")
    if None in (lat1, lng1, lat2, lng2):
        return False
    if coordinate_key(lat1, lng1) == coordinate_key(lat2, lng2):
        return True
    return _haversine_m(lat1, lng1, lat2, lng2) <= MAX_DISTANCE_M


def _corroborators(a: dict, b: dict) -> int:
    count = 0
    fa, fb = a.get("facing") or "", b.get("facing") or ""
    if fa and fb and fa == fb:
        count += 1
    ba, bb = a.get("balconies", -1), b.get("balconies", -1)
    if ba >= 0 and bb >= 0 and ba == bb:
        count += 1
    if _within_relative(a.get("sqft") or 0, b.get("sqft") or 0, SQFT_RELATIVE):
        count += 1
    return count


def same_flat(a: dict, b: dict) -> bool:
    """True when `b` looks like a re-listing of the same flat as `a`."""
    if not a.get("bhk") or a.get("bhk") != b.get("bhk"):
        return False

    keys_a, keys_b = society_keys(a), society_keys(b)
    if not keys_a or not keys_b or keys_a.isdisjoint(keys_b):
        return False

    if not _floors_known_and_equal(a, b):
        return False

    if not _total_floors_compatible(a, b):
        return False

    centroid = a.get("isCentroidLocation") or b.get("isCentroidLocation")
    if not centroid and not _near(a, b):
        return False

    rent_close = _within_relative_or_abs(
        a.get("rent") or 0, b.get("rent") or 0, RENT_RELATIVE, RENT_ABSOLUTE)
    deposit_close = _within_relative(
        a.get("deposit") or 0, b.get("deposit") or 0, DEPOSIT_RELATIVE)
    if not (rent_close or deposit_close):
        return False

    needed = 2 if centroid else 1
    return _corroborators(a, b) >= needed


class SameFlatIndex:
    """Bucket kept map records for O(bucket) same-flat lookups."""

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str, int], list[dict]] = defaultdict(list)

    def add(self, record: dict) -> None:
        floor = record.get("floor", 0)
        bhk = record.get("bhk") or ""
        for key in society_keys(record):
            self._buckets[(key, bhk, floor)].append(record)

    def has_same_flat(self, record: dict) -> bool:
        floor = record.get("floor", 0)
        bhk = record.get("bhk") or ""
        for key in society_keys(record):
            for other in self._buckets.get((key, bhk, floor), []):
                if same_flat(other, record):
                    return True
        return False
