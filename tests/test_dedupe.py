"""Same-flat cross-platform matching for the map builder."""
from rental_lookup.webmap.dedupe import SameFlatIndex, same_flat


def _listing(**overrides):
    base = {
        "lat": 12.9716, "lng": 77.6412,
        "rent": 45000, "deposit": 200000, "sqft": 1200,
        "bhk": "BHK2", "society": "Brigade Gateway", "buildingName": "",
        "facing": "E", "balconies": 1,
        "floor": 5, "totalFloors": 20,
        "floorKnown": True, "isCentroidLocation": False,
    }
    base.update(overrides)
    return base


def test_same_society_floor_and_close_rent_is_duplicate():
    nb = _listing()
    mb = _listing(rent=46000, lat=12.97165, lng=77.64125, source="mb")
    assert same_flat(nb, mb)


def test_same_society_different_floor_is_not_duplicate():
    nb = _listing(floor=5)
    other = _listing(floor=8, rent=45000, sqft=1200)
    assert not same_flat(nb, other)


def test_generic_society_never_duplicates():
    nb = _listing(society="Independent House")
    mb = _listing(society="Independent House", rent=45000)
    assert not same_flat(nb, mb)


def test_unknown_floor_never_duplicates():
    nb = _listing(floorKnown=True)
    mb = _listing(floorKnown=False, rent=45000)
    assert not same_flat(nb, mb)


def test_rent_close_needs_corroborator():
    nb = _listing(facing="", balconies=-1, sqft=0)
    mb = _listing(facing="", balconies=-1, sqft=0, rent=45000)
    assert not same_flat(nb, mb)


def test_facing_corroborates_close_rent():
    nb = _listing(facing="NE", balconies=-1, sqft=0)
    mb = _listing(facing="NE", balconies=-1, sqft=0, rent=46000)
    assert same_flat(nb, mb)


def test_balcony_corroborates_close_rent():
    nb = _listing(facing="", balconies=2, sqft=0)
    mb = _listing(facing="", balconies=2, sqft=0, rent=45500)
    assert same_flat(nb, mb)


def test_building_name_can_match_society():
    nb = _listing(society="Something Else", buildingName="Brigade Gateway")
    mb = _listing(society="Brigade Gateway")
    assert same_flat(nb, mb)


def test_far_apart_not_duplicate():
    nb = _listing()
    mb = _listing(lat=12.95, lng=77.60)  # well over 100 m
    assert not same_flat(nb, mb)


def test_centroid_needs_two_corroborators():
    nb = _listing(facing="E", balconies=1, sqft=0)
    mb = _listing(isCentroidLocation=True, facing="E", balconies=-1, sqft=0, rent=45000)
    assert not same_flat(nb, mb)
    mb["balconies"] = 1
    assert same_flat(nb, mb)


def test_total_floors_mismatch_rejects():
    nb = _listing(totalFloors=12)
    mb = _listing(totalFloors=5, rent=45000)
    assert not same_flat(nb, mb)


def test_index_finds_same_flat_across_buckets():
    index = SameFlatIndex()
    index.add(_listing())
    assert index.has_same_flat(_listing(rent=44800, facing="E"))
    assert not index.has_same_flat(_listing(floor=9, rent=45000))
