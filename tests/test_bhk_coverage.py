"""BHK coverage: scrapers must request 1, 2 and 3 BHK from both sources."""
import re

from rental_lookup.sources import magicbricks, nobroker
from rental_lookup.webmap.builder import load_template


def test_nobroker_requests_1bhk():
    assert set(nobroker.BHK_TYPES.split(",")) == {"BHK1", "BHK2", "BHK3"}


def test_magicbricks_requests_1bhk():
    assert set(magicbricks.BHK_TYPES.split(",")) == {"1", "2", "3"}


def test_magicbricks_normalizes_1bhk():
    listing = magicbricks.normalize_listing({
        "id": "mb-1bhk",
        "bedroomD": "1 BHK",
        "price": 20000,
        "pmtLat": "12.9716",
        "pmtLong": "77.6412",
        "propertyTypeD": "Apartment",
        "lmtDName": "Indiranagar",
        "pdUrl": "/propertyDetails/mb-1bhk",
    })
    assert listing is not None
    assert listing.bhk == "BHK1"


def test_map_template_has_1bhk_chip():
    html = load_template()
    assert 'data-filter="bhk1"' in html, "map template is missing the 1 BHK filter chip"


def test_map_template_bhk1_chip_off_by_default():
    html = load_template()
    state = re.search(r"var filterChips = \{(.*?)\};", html, re.S).group(1)
    assert "bhk1:false" in state.replace(" ", ""), (
        "bhk1 must default to false so 1 BHK listings show without hiding 2/3 BHK"
    )


def test_map_template_filter_predicate_handles_bhk1():
    html = load_template()
    assert "filterChips.bhk1 && d.bhk === 'BHK1'" in html, (
        "filter predicate must match BHK1 when the 1 BHK chip is on"
    )
    assert "filterChips.bhk1 || filterChips.bhk2 || filterChips.bhk3" in html, (
        "the OR-set guard must include bhk1"
    )
