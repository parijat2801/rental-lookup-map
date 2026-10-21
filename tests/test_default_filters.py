"""Must-have chips (building type exclusions, balcony, lift, any parking) are on by default."""
import re

import pytest

from rental_lookup.webmap.builder import load_template

CHIPS = ("excludeStandalone", "excludeIndependentHouses", "requireBalcony", "requireLift", "requireAnyParking")


def _default_state(html):
    return re.search(r"var filterChips = \{(.*?)\};", html, re.S).group(1).replace(" ", "")


@pytest.mark.parametrize("name", CHIPS)
def test_must_have_chip_on_by_default(name):
    assert f"{name}:true" in _default_state(load_template())


@pytest.mark.parametrize("name", CHIPS)
def test_must_have_chip_markup_matches_default(name):
    assert f'class="chip on" data-filter="{name}"' in load_template()


def test_car_parking_stays_optional_by_default():
    html = load_template()
    assert "requireCarParking:false" in _default_state(html)
    assert 'class="chip on" data-filter="requireCarParking"' not in html


def test_must_have_predicates_present():
    html = load_template()
    assert "filterChips.excludeStandalone && STANDALONE_SOCIETIES.includes(" in html
    assert "filterChips.excludeIndependentHouses && d.buildingType === 'IH'" in html
    # Known-no only; unknown (-1 / null / "") must still pass
    assert "filterChips.requireBalcony && d.balconies === 0" in html
    assert "filterChips.requireLift && d.hasLift === false" in html
    assert "filterChips.requireAnyParking && d.parking === 'NONE'" in html
    assert "filterChips.requireLift && !d.hasLift" not in html
    assert "(!d.parking || d.parking === 'NONE')" not in html
