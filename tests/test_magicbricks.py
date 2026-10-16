"""MagicBricks normalisation: field parsing is lenient and matches current API labels."""
from rental_lookup.sources import magicbricks as mb

BASE = {"id": "1", "price": "45000", "pmtLat": 12.97, "pmtLong": 77.64, "lmtDName": "Indiranagar"}


def _listing(**fields):
    return mb.normalize_listing({**BASE, **fields})


def test_age_labels():
    assert _listing(acD="New Construction").age_years == 1
    assert _listing(acD="Less than 5 years").age_years == 3
    assert _listing(acD="5 to 10 years").age_years == 7
    assert _listing(acD="10 to 15 years").age_years == 15  # must not match "0 to 1"
    assert _listing(acD="0 to 1 years").age_years == 1
    assert _listing(acD="15 to 20 years").age_years == 15
    assert _listing().age_years == 99


def test_facing_with_spaced_hyphen():
    assert _listing(facingD="North - East").facing == "NE"
    assert _listing(facingD="North-East").facing == "NE"
    assert _listing(facingD="East").facing == "E"


def test_amenity_codes_are_matched_exactly():
    assert mb.amenity_names({"amenities": "12201 12205"}) == {"lift", "pool"}
    assert mb.amenity_names({"amenities": "112205"}) == set()  # no substring false positive
    assert mb.amenity_names({}) == set()


def test_coords_fall_back_to_locality_centroid():
    listing = _listing(pmtLat=None, pmtLong=None, ltcoordGeo="12.9,77.6")
    assert (listing.lat, listing.lng) == (12.9, 77.6)
    assert _listing(pmtLat=None, pmtLong=None) is None


def test_lenient_numbers():
    listing = _listing(price="45000.0", floorNo="Ground", floors="abc", balconiesD=None)
    assert listing.rent == 45000
    assert (listing.floor, listing.total_floors, listing.balconies) == (0, 0, 0)
    assert _listing(price="0") is None


def test_parking_and_water():
    assert _listing(parkingD="1 Covered").parking == "FOUR_WHEELER"
    assert _listing(parkingD="1 Covered").has_car_parking is True
    assert _listing().parking == "NONE"
    assert _listing(waterStatus="Water Availability 24 Hours Available").water_supply == "CORPORATION"
