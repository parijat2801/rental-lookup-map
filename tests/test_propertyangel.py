"""Property Angel normalisation of /properties/detail payloads."""
import json

from rental_lookup.sources import magicbricks
from rental_lookup.sources import propertyangel as pa
from rental_lookup.webmap import builder

BASE = {
    "PropID": {"ID": "3867124000091539066", "display_value": "10230"},
    "LatLong": {"latitude": "13.13428300", "longitude": "77.74663800"},
    "Projects": {"ID": "1", "display_value": "Krishvi Statura"},
    "Location_Area": {"ID": "2", "display_value": "Budigere"},
    "City_Zone_Classification.City": "Bangalore",
    "Property_Type": "Apartment",
    "Furnishing": "Semi Furnished",
    "No_of_Bedrooms": "2.00",
    "Advertised_Rent": "47000",
    "Advertised_Security_Deposit": "235000",
    "Built_Up_Area_sft": "1226",
    "Total_no_of_Floors": "36",
    "Unit_is_on_Floor_0_for_Ground_floor": "12",
    "No_of_Covered_Car_Parks": "1",
    "No_of_Open_Car_Parks": "0",
    "Main_door_facing_Direction": "East",
}


def _listing(**fields):
    return pa.normalize_listing({**BASE, **fields})


def test_core_fields():
    listing = _listing()
    assert listing.id == "pa_10230"
    assert (listing.rent, listing.deposit, listing.sqft, listing.bhk) == (47000, 235000, 1226, "BHK2")
    assert (listing.lat, listing.lng) == (13.134283, 77.746638)
    assert (listing.society, listing.locality) == ("Krishvi Statura", "Budigere")
    assert (listing.floor, listing.total_floors, listing.facing) == (12, 36, "E")
    assert listing.parking == "FOUR_WHEELER" and listing.has_covered_parking


def test_url_ends_with_property_id():
    url = _listing().url
    assert url.startswith("https://www.propertyangel.in/property/2-bhk-semi-furnished-apartment-for-rent-in-")
    assert url.endswith("-papid-10230")


def test_coords_fall_back_to_new_fields():
    listing = _listing(LatLong="", Latitude_New="12.9", Longitude_New="77.6")
    assert (listing.lat, listing.lng) == (12.9, 77.6)
    assert _listing(LatLong="", Latitude_New="", Longitude_New="") is None


def test_unusable_listings_are_dropped():
    assert _listing(Advertised_Rent="0") is None
    assert _listing(PropID=None) is None


def test_building_types_and_lift():
    assert _listing(Property_Type="Independent House").building_type == "IH"
    assert _listing(Property_Type="Building Unit").building_type == "IF"
    assert _listing().has_lift is True
    assert _listing(Total_no_of_Floors="3").has_lift is False


def test_facing_and_parking_variants():
    assert _listing(Main_door_facing_Direction="North-East").facing == "NE"
    assert _listing(Main_door_facing_Direction="North East").facing == "NE"
    assert _listing(Main_door_facing_Direction="").facing == ""
    assert _listing(No_of_Covered_Car_Parks="0").parking == "NONE"
    unknown = {k: v for k, v in BASE.items() if k not in ("No_of_Covered_Car_Parks", "No_of_Open_Car_Parks")}
    assert pa.normalize_listing(unknown).parking == ""
    assert _listing().balconies == -1  # No_of_Balconies absent
    assert _listing(No_of_Balconies="0").balconies == 0
    assert _listing(No_of_Balconies="2").balconies == 2


def test_maintenance_and_furnishing():
    assert pa.maintenance({"Advertised_Rent_Includes_Mnt": "excluding", "Association_maintenance_amount": "3,500"}) == 3500
    assert pa.maintenance({"Advertised_Rent_Includes_Mnt": "including", "Association_maintenance_amount": "3500"}) == 0
    assert [pa.furnishing({"Furnishing": f}) for f in ("Fully Furnished", "Semi Furnished", "Unfurnished", "")] == \
        ["FULL", "SEMI", "NONE", ""]


def test_photos_primary_first_and_resized():
    raw = {"ImageList": [{"image": "https://img/a.png", "isPrimary": False},
                         {"image": "https://img/b.png", "isPrimary": True},
                         {"image": "https://img/c.png?w=1"}]}
    assert pa.photo_urls(raw) == [f"https://img/b.png?{pa.IMAGE_RESIZE_QUERY}",
                                  f"https://img/a.png?{pa.IMAGE_RESIZE_QUERY}", "https://img/c.png?w=1"]


def test_iter_saved_listings_dedupes(tmp_path):
    (tmp_path / "a.json").write_text('{"PropID": {"display_value": "1"}}')
    (tmp_path / "b.json").write_text('{"PropID": {"display_value": "1"}}')
    (tmp_path / "c.json").write_text('{"PropID": {"display_value": "2"}}')
    assert [pa.prop_id(raw) for raw in pa.iter_saved_listings(tmp_path)] == ["1", "2"]


def test_fetch_all_reuses_saved_details(tmp_path, monkeypatch):
    def summary(property_id, rent):
        return {"PropID": {"display_value": property_id}, "Advertised_Rent": rent}

    (tmp_path / "propertyangel_1.json").write_text(json.dumps({**summary("1", "40000"), "LatLong": "kept"}))
    (tmp_path / "propertyangel_9.json").write_text(json.dumps(summary("9", "10000")))
    fetched = []
    monkeypatch.setattr(pa, "fetch_summaries", lambda client: [summary("1", "45000"), summary("2", "50000")])
    monkeypatch.setattr(pa, "fetch_detail", lambda client, property_id: fetched.append(property_id) or
                        {**summary(property_id, "0"), "LatLong": "fetched"})
    monkeypatch.setattr(pa.time, "sleep", lambda seconds: None)

    raws = {pa.prop_id(raw): raw for raw in pa.fetch_all(pages_dir=tmp_path)}

    assert fetched == ["2"]
    assert (raws["1"]["Advertised_Rent"], raws["1"]["LatLong"]) == ("45000", "kept")
    assert (raws["2"]["Advertised_Rent"], raws["2"]["LatLong"]) == ("50000", "fetched")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["propertyangel_1.json", "propertyangel_2.json"]


def _fake_api(monkeypatch, property_ids, rate_limited_after=None):
    fetched = []

    def fetch_detail(client, property_id):
        if rate_limited_after is not None and len(fetched) >= rate_limited_after:
            raise pa.RateLimited
        fetched.append(property_id)
        return {"PropID": {"display_value": property_id}}

    monkeypatch.setattr(pa, "fetch_summaries",
                        lambda client: [{"PropID": {"display_value": p}} for p in property_ids])
    monkeypatch.setattr(pa, "fetch_detail", fetch_detail)
    monkeypatch.setattr(pa.time, "sleep", lambda seconds: None)
    return fetched


def test_fetch_all_caps_new_details_per_run(tmp_path, monkeypatch):
    fetched = _fake_api(monkeypatch, ["1", "2", "3"])
    assert len(pa.fetch_all(pages_dir=tmp_path, max_new_details=2)) == 2
    assert fetched == ["1", "2"]
    assert len(pa.fetch_all(pages_dir=tmp_path, max_new_details=2)) == 3  # next run picks up the rest
    assert fetched == ["1", "2", "3"]


def test_fetch_all_stops_fetching_when_rate_limited(tmp_path, monkeypatch):
    fetched = _fake_api(monkeypatch, ["1", "2", "3"], rate_limited_after=1)
    assert len(pa.fetch_all(pages_dir=tmp_path)) == 1
    assert fetched == ["1"]


def test_map_record_has_same_keys_as_other_sources():
    context = builder.BuildContext(fake_location_ids=set(), stacked_coordinates=set(), platform_scores={})
    raw = {**BASE, "PropID.TenancyStatus": "Tenanted"}
    record = builder.propertyangel_record(pa.normalize_listing(raw), raw, context)
    mb_raw = {"id": "1", "price": "45000", "pmtLat": 12.97, "pmtLong": 77.64}
    mb_record = builder.magicbricks_record(magicbricks.normalize_listing(mb_raw), mb_raw, context)
    assert record.keys() == mb_record.keys()
    assert record["source"] == "pa"
    assert record["availableFrom"] == "After current tenant"
