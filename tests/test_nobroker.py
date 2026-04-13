import copy

from rental_lookup.nobroker import parse_listings, deduplicate, make_search_param


def test_parse_listings_from_sample_response(sample_nobroker_response):
    listings = parse_listings(sample_nobroker_response)
    assert len(listings) == 2
    assert listings[0].id == "ff808181651e847c016521d2c5e337d0"
    assert listings[0].rent == 45000
    assert listings[1].rent == 55000
    assert listings[1].has_power_backup is True


def test_parse_listings_skips_missing_coords(sample_nobroker_response):
    data = copy.deepcopy(sample_nobroker_response)
    data["data"].append({
        "id": "no-coords", "rent": 30000, "deposit": 100000,
        "propertySize": 800, "type": "BHK2",
        "latitude": None, "longitude": None,
        "locality": "X", "society": "", "buildingType": "AP",
        "floor": 1, "totalFloor": 1, "lift": False,
        "parking": "NONE", "propertyTitle": "Flat",
        "detailUrl": "/p/x", "amenitiesMap": {},
    })
    listings = parse_listings(data)
    assert len(listings) == 2


def test_parse_listings_empty_data():
    listings = parse_listings({"status": "success", "data": []})
    assert listings == []


def test_parse_listings_failed_response():
    listings = parse_listings({"status": "error", "data": []})
    assert listings == []


def test_deduplicate_by_id():
    from rental_lookup.models import Listing

    raw1 = {
        "id": "dup1", "rent": 40000, "deposit": 200000,
        "propertySize": 1000, "type": "BHK2",
        "latitude": 12.97, "longitude": 77.64,
        "locality": "A", "society": "S", "buildingType": "AP",
        "floor": 1, "totalFloor": 5, "lift": False,
        "parking": "BOTH", "propertyTitle": "T",
        "detailUrl": "/p/1", "amenitiesMap": {},
    }
    raw2 = {**raw1, "rent": 45000}
    raw3 = {**raw1, "id": "unique1"}

    l1 = Listing.from_nobroker(raw1)
    l2 = Listing.from_nobroker(raw2)
    l3 = Listing.from_nobroker(raw3)

    result = deduplicate([l1, l2, l3])
    assert len(result) == 2
    assert result[0].id == "dup1"
    assert result[0].rent == 40000
    assert result[1].id == "unique1"


def test_make_search_param():
    import base64, json
    param = make_search_param("Indiranagar", 12.9716, 77.6412, "ChIJ123")
    decoded = json.loads(base64.b64decode(param))
    assert decoded == [{"lat": 12.9716, "lon": 77.6412, "placeId": "ChIJ123", "placeName": "Indiranagar"}]
