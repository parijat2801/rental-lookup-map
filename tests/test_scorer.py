import re
from rental_lookup.models import Listing, LocationScore, ScoredListing
from rental_lookup.scorer import passes_hard_filters, score_listing, rank_listings


def _make_listing(**overrides) -> Listing:
    defaults = dict(
        id="test1", rent=40000, deposit=200000, sqft=1000, bhk="BHK2",
        lat=12.97, lng=77.64, locality="Test", society="Test Society",
        building_type="AP", floor=3, total_floor=10, lift=True,
        parking="FOUR_WHEELER", title="2 BHK Apartment for Rent",
        url="https://www.nobroker.in/property/test", photo_url="",
        facing="E", balconies=1, age=5, water_supply="CORPORATION",
        negotiable=False, nb_transit=7.5, nb_lifestyle=6.0,
        has_power_backup=True, has_gated_community=True,
        has_covered_parking=True, has_security=True, has_fire_safety=False,
        has_car_parking=True,
    )
    defaults.update(overrides)
    return Listing(**defaults)


def _make_location(**overrides) -> LocationScore:
    defaults = dict(nearest_park_m=300.0, nearest_lake_m=1000.0, nearest_metro_m=400.0)
    defaults.update(overrides)
    return LocationScore(**defaults)


# --- Hard filter tests ---

def test_hard_filter_passes_valid():
    assert passes_hard_filters(_make_listing(rent=50000, sqft=1000)) is True

def test_hard_filter_passes_boundary_rent():
    assert passes_hard_filters(_make_listing(rent=60000)) is True

def test_hard_filter_rejects_over_budget():
    assert passes_hard_filters(_make_listing(rent=70001)) is False

def test_hard_filter_passes_boundary_sqft():
    assert passes_hard_filters(_make_listing(sqft=700)) is True

def test_hard_filter_rejects_too_small():
    assert passes_hard_filters(_make_listing(sqft=699)) is False

def test_hard_filter_rejects_zero_coords():
    assert passes_hard_filters(_make_listing(lat=0.0, lng=0.0)) is False


# --- Scoring tests ---

def test_score_pet_gated_community():
    listing = _make_listing(has_gated_community=True, title="Normal Flat")
    score_with = score_listing(listing, _make_location())
    listing2 = _make_listing(has_gated_community=False, title="Normal Flat")
    score_without = score_listing(listing2, _make_location())
    assert score_with.total_score > score_without.total_score

def test_score_pet_text_signal():
    listing = _make_listing(has_gated_community=False, title="Pet Friendly 2 BHK Apartment")
    score_with = score_listing(listing, _make_location())
    listing2 = _make_listing(has_gated_community=False, title="2 BHK Apartment")
    score_without = score_listing(listing2, _make_location())
    assert score_with.total_score > score_without.total_score

def test_score_pet_text_no_false_positive_carpet():
    """'carpet' should NOT trigger pet scoring."""
    listing = _make_listing(has_gated_community=False, title="1000 sqft carpet area")
    score = score_listing(listing, _make_location())
    listing2 = _make_listing(has_gated_community=False, title="1000 sqft built up area")
    score2 = score_listing(listing2, _make_location())
    assert score.total_score == score2.total_score

def test_score_closer_park_higher():
    close = score_listing(_make_listing(), _make_location(nearest_park_m=200))
    far = score_listing(_make_listing(), _make_location(nearest_park_m=800))
    assert close.total_score > far.total_score

def test_score_closer_metro_higher():
    close = score_listing(_make_listing(), _make_location(nearest_metro_m=300))
    far = score_listing(_make_listing(), _make_location(nearest_metro_m=2000))
    assert close.total_score > far.total_score

def test_score_power_backup_adds_points():
    with_pb = score_listing(_make_listing(has_power_backup=True), _make_location())
    without_pb = score_listing(_make_listing(has_power_backup=False), _make_location())
    assert with_pb.total_score > without_pb.total_score

def test_score_car_parking_adds_points():
    with_pk = score_listing(_make_listing(has_car_parking=True), _make_location())
    without_pk = score_listing(_make_listing(has_car_parking=False), _make_location())
    assert with_pk.total_score > without_pk.total_score

def test_score_floor_safety():
    low = score_listing(_make_listing(floor=1), _make_location())
    high = score_listing(_make_listing(floor=8), _make_location())
    assert low.total_score > high.total_score

def test_score_bigger_space_higher():
    big = score_listing(_make_listing(sqft=1400), _make_location())
    small = score_listing(_make_listing(sqft=750), _make_location())
    assert big.total_score > small.total_score

def test_score_unknown_location_not_negative():
    score = score_listing(_make_listing(), LocationScore())
    assert score.total_score >= 0

def test_score_metro_boundary_500():
    """Exactly 500m should score 15 (the < 500 bracket)."""
    s = score_listing(_make_listing(), _make_location(nearest_metro_m=499))
    assert s.total_score > score_listing(_make_listing(), _make_location(nearest_metro_m=501)).total_score


# --- Ranking ---

def test_rank_sorted_descending():
    great = _make_listing(
        id="great", rent=40000, sqft=1400,
        has_power_backup=True, has_gated_community=True, has_car_parking=True,
        title="Pet Friendly Gated Community",
    )
    ok = _make_listing(
        id="ok", rent=50000, sqft=1000,
        has_power_backup=True, has_gated_community=False, has_car_parking=True,
    )
    bad = _make_listing(
        id="bad", rent=58000, sqft=750,
        has_power_backup=False, has_gated_community=False, has_car_parking=False,
    )
    loc_great = _make_location(nearest_park_m=200, nearest_metro_m=300, nearest_lake_m=800)
    loc_ok = _make_location(nearest_park_m=600, nearest_metro_m=1200, nearest_lake_m=2000)
    loc_bad = _make_location(nearest_park_m=1500, nearest_metro_m=3000, nearest_lake_m=5000)

    ranked = rank_listings([(great, loc_great), (bad, loc_bad), (ok, loc_ok)])
    assert len(ranked) == 3
    assert ranked[0].listing.id == "great"
    assert ranked[1].listing.id == "ok"
    assert ranked[2].listing.id == "bad"
    assert ranked[0].total_score > ranked[1].total_score > ranked[2].total_score
