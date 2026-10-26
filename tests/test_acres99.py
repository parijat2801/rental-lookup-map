"""99acres normalisation: field parsing is lenient and matches current API labels."""
import json

from rental_lookup.sources import acres99 as aa
from rental_lookup.sources import magicbricks
from rental_lookup.webmap import builder

BASE = {
    "PROP_ID": "R12345678",
    "MIN_PRICE": "45000",
    "BEDROOM_NUM": "2",
    "SOCIETY_NAME": "Prestige Oaks",
    "LOCALITY": "Indiranagar, Bangalore",
    "MAP_DETAILS": {"LATITUDE": "12.9784", "LONGITUDE": "77.6408", "SOURCE": "PROJECT", "MAP_ACCURACY": "1"},
    "AREA": "1,200 sq.ft.",
    "FLOOR_NUM": "5",
    "TOTAL_FLOOR": "12",
    "FACING": "3",
    "FURNISH": "4",
    "AGE": "5",
    "BALCONY_NUM": "2",
    "GATED": "Y",
    "AMENITIES": "1,3,5,6,9,21,40",
    "PD_URL": "/2-bhk-bedroom-apartment-flat-for-rent-in-indiranagar-bangalore-spid-R12345678",
    "PROP_HEADING": "2 BHK Flat for rent in Indiranagar",
    "MEDIUM_PHOTO_URL": "https://imagecdn.99acres.com/media/photo.jpg",
    "POSTING_DATE": 1714000000000,
}


def _listing(**fields):
    return aa.normalize_listing({**BASE, **fields})


def test_core_fields():
    listing = _listing()
    assert listing.id == "9a_R12345678"
    assert (listing.rent, listing.sqft, listing.bhk) == (45000, 1200, "BHK2")
    assert (listing.lat, listing.lng) == (12.9784, 77.6408)
    assert (listing.society, listing.locality) == ("Prestige Oaks", "Indiranagar")
    assert (listing.floor, listing.total_floors, listing.facing) == (5, 12, "E")
    assert listing.parking == "FOUR_WHEELER" and listing.has_covered_parking
    assert listing.url.endswith("spid-R12345678")
    assert listing.url.startswith("https://www.99acres.com/")


def test_coords_recover_swapped_labels():
    listing = _listing(MAP_DETAILS={"LATITUDE": "77.6408", "LONGITUDE": "12.9784", "SOURCE": "PROJECT"})
    assert (listing.lat, listing.lng) == (12.9784, 77.6408)
    assert _listing(MAP_DETAILS={}) is None


def test_unusable_listings_are_dropped():
    assert _listing(MIN_PRICE="0") is None
    assert _listing(PROP_ID="") is None


def test_amenity_codes_and_lift():
    assert "lift" in aa.amenity_names(BASE)
    assert "pool" in aa.amenity_names(BASE)
    assert _listing().has_lift is True
    assert _listing(AMENITIES="5,21").has_lift is False
    assert _listing(AMENITIES="", FEATURES="").has_lift is None


def test_furnishing_facing_floor_age():
    assert aa.furnishing({"FURNISH": "1"}) == "FULL"
    assert aa.furnishing({"FURNISH": "2"}) == "NONE"
    assert aa.furnishing({"FURNISH": "4"}) == "SEMI"
    assert _listing(FACING="North-East").facing == "NE"
    assert _listing(FLOOR_NUM="Ground").floor == 0
    assert _listing(AGE="New Construction").age_years == 1
    assert _listing(AGE="").age_years == 99


def test_centroid_vs_property_pin():
    assert aa.has_property_pin(BASE) is True
    assert aa.has_property_pin({**BASE, "MAP_DETAILS": {
        "LATITUDE": "12.97", "LONGITUDE": "77.64", "SOURCE": "CITY", "MAP_ACCURACY": "0",
    }}) is False


def test_lowercase_keys_are_accepted():
    listing = aa.normalize_listing({
        "prop_id": "R99", "min_price": "30000", "bedroom_num": "1",
        "society_name": "Oak", "locality_wo_city": "HSR",
        "map_details": {"latitude": "12.91", "longitude": "77.64"},
        "area": "850 sq.ft.", "pd_url": "/listing-spid-R99",
    })
    assert listing is not None
    assert listing.id == "9a_R99"
    assert listing.bhk == "BHK1"
    assert listing.locality == "HSR"


def test_page_properties_skips_ads(tmp_path):
    page = {"properties": [
        {"PROP_ID": "R1", "MIN_PRICE": "1"},
        {"tupleType": "AD"},
        {"PROP_ID": "R1", "MIN_PRICE": "2"},
        {"PROP_ID": "R2", "MIN_PRICE": "3"},
    ]}
    (tmp_path / "acres99_page1.json").write_text(json.dumps(page))
    assert [aa.prop_id(raw) for raw in aa.iter_saved_listings(tmp_path)] == ["R1", "R2"]


def test_map_record_has_same_keys_as_other_sources():
    context = builder.BuildContext(fake_location_ids=set(), stacked_coordinates=set(), platform_scores={})
    record = builder.acres99_record(aa.normalize_listing(BASE), BASE, context)
    mb_raw = {"id": "1", "price": "45000", "pmtLat": 12.97, "pmtLong": 77.64}
    mb_record = builder.magicbricks_record(magicbricks.normalize_listing(mb_raw), mb_raw, context)
    assert record.keys() == mb_record.keys()
    assert record["source"] == "9a"
    assert record["hasPool"] is True
    assert record["isCentroidLocation"] is False
