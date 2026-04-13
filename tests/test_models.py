import pytest
from rental_lookup.models import Listing, LocationScore, ScoredListing


def test_listing_from_nobroker_dict():
    raw = {
        "id": "ff808181651e847c016521d2c5e337d0",
        "rent": 45000,
        "deposit": 250000,
        "propertySize": 1100,
        "type": "BHK2",
        "latitude": 12.9718,
        "longitude": 77.6411,
        "locality": "Indiranagar, Bengaluru, Karnataka, India",
        "society": "Independent House",
        "buildingType": "IH",
        "floor": 1,
        "totalFloor": 1,
        "lift": False,
        "parking": "TWO_WHEELER",
        "propertyTitle": "2 BHK House for Rent In Indiranagar",
        "detailUrl": "/property/2-bhk-apartment-abc123",
        "originalImageUrl": "https://img.nobroker.in/abc.jpg",
        "amenitiesMap": {
            "PB": False, "GP": False, "CPA": False, "SECURITY": False,
        },
    }
    listing = Listing.from_nobroker(raw)
    assert listing.id == "ff808181651e847c016521d2c5e337d0"
    assert listing.rent == 45000
    assert listing.deposit == 250000
    assert listing.sqft == 1100
    assert listing.bhk == "BHK2"
    assert listing.lat == 12.9718
    assert listing.lng == 77.6411
    assert listing.society == "Independent House"
    assert listing.has_power_backup is False
    assert listing.has_gated_community is False
    assert listing.has_covered_parking is False
    assert listing.has_security is False
    assert listing.has_car_parking is False
    assert listing.floor == 1
    assert listing.url == "https://www.nobroker.in/property/2-bhk-apartment-abc123"
    assert listing.photo_url == "https://img.nobroker.in/abc.jpg"


def test_listing_from_nobroker_with_amenities():
    raw = {
        "id": "abc123",
        "rent": 55000,
        "deposit": 300000,
        "propertySize": 1450,
        "type": "BHK3",
        "latitude": 12.978,
        "longitude": 77.639,
        "locality": "Indiranagar",
        "society": "Prestige Shantiniketan",
        "buildingType": "AP",
        "floor": 5,
        "totalFloor": 12,
        "lift": True,
        "parking": "BOTH",
        "propertyTitle": "3 BHK Apartment pet friendly",
        "detailUrl": "/property/3-bhk-abc",
        "amenitiesMap": {
            "PB": True, "GP": True, "CPA": True, "SECURITY": True,
        },
    }
    listing = Listing.from_nobroker(raw)
    assert listing.has_power_backup is True
    assert listing.has_gated_community is True
    assert listing.has_covered_parking is True
    assert listing.has_security is True
    assert listing.has_car_parking is True


def test_listing_missing_latlng_returns_none():
    raw = {
        "id": "no-coords", "rent": 30000, "deposit": 100000,
        "propertySize": 800, "type": "BHK2",
        "latitude": None, "longitude": None,
        "locality": "Somewhere", "society": "", "buildingType": "AP",
        "floor": 2, "totalFloor": 5, "lift": False,
        "parking": "NONE", "propertyTitle": "2 BHK Flat",
        "detailUrl": "/property/xyz", "amenitiesMap": {},
    }
    assert Listing.from_nobroker(raw) is None


def test_listing_zero_latlng_returns_none():
    raw = {
        "id": "zero", "rent": 30000, "deposit": 100000, "propertySize": 800,
        "type": "BHK2", "latitude": 0, "longitude": 0,
        "locality": "X", "society": "", "buildingType": "AP",
        "floor": 1, "totalFloor": 1, "lift": False,
        "parking": "NONE", "propertyTitle": "Flat",
        "detailUrl": "/p/x", "amenitiesMap": {},
    }
    assert Listing.from_nobroker(raw) is None


def test_listing_no_photo_url():
    raw = {
        "id": "nophoto", "rent": 30000, "deposit": 100000, "propertySize": 800,
        "type": "BHK2", "latitude": 12.97, "longitude": 77.64,
        "locality": "X", "society": "S", "buildingType": "AP",
        "floor": 1, "totalFloor": 1, "lift": False,
        "parking": "NONE", "propertyTitle": "Flat",
        "detailUrl": "/p/x", "amenitiesMap": {},
    }
    listing = Listing.from_nobroker(raw)
    assert listing.photo_url == ""


def test_location_score_defaults():
    score = LocationScore()
    assert score.nearest_park_m is None
    assert score.nearest_lake_m is None
    assert score.nearest_metro_m is None


def test_scored_listing_combines_listing_and_location():
    raw = {
        "id": "test1", "rent": 40000, "deposit": 200000,
        "propertySize": 1000, "type": "BHK2",
        "latitude": 12.97, "longitude": 77.64,
        "locality": "Test", "society": "Test Society",
        "buildingType": "AP", "floor": 3, "totalFloor": 10,
        "lift": True, "parking": "FOUR_WHEELER",
        "propertyTitle": "Test", "detailUrl": "/p/test",
        "amenitiesMap": {"PB": True, "GP": True, "CPA": True, "SECURITY": True},
    }
    listing = Listing.from_nobroker(raw)
    loc = LocationScore(nearest_park_m=200, nearest_lake_m=1000, nearest_metro_m=500)
    scored = ScoredListing(listing=listing, location=loc, total_score=85)
    assert scored.listing.rent == 40000
    assert scored.location.nearest_park_m == 200
    assert scored.total_score == 85
