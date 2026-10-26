"""Must-have chips (building type exclusions, balcony, lift, any parking) are on by default."""
import re

import pytest

from rental_lookup.webmap.builder import load_template

CHIPS = ("excludeStandalone", "excludeIndependentHouses", "requireBalcony", "requireLift", "requireAnyParking")


def _default_state(html):
    return re.search(r"var filterChips = \{(.*?)\};", html, re.S).group(1).replace(" ", "")


def _compact(html):
    return re.sub(r"\s+", " ", html)


@pytest.mark.parametrize("name", CHIPS)
def test_must_have_chip_on_by_default(name):
    assert f"{name}:true" in _default_state(load_template())


@pytest.mark.parametrize("name", CHIPS)
def test_must_have_chip_markup_matches_default(name):
    html = _compact(load_template())
    assert re.search(rf'class="chip on"[^>]*data-filter="{name}"', html)


def test_car_parking_stays_optional_by_default():
    html = load_template()
    assert "requireCarParking:false" in _default_state(html)
    assert not re.search(r'class="chip on"[^>]*data-filter="requireCarParking"', _compact(html))


AMENITY_CHIPS = (
    "poolOnly", "requireGym", "requireClubhouse", "requirePark",
    "requireGated", "requireSecurity", "requirePowerBackup", "requireIntercom",
)


@pytest.mark.parametrize("name", AMENITY_CHIPS)
def test_amenity_must_haves_off_by_default(name):
    html = load_template()
    assert f"{name}:false" in _default_state(html)
    assert f'data-filter="{name}"' in html


def test_must_have_predicates_present():
    html = _compact(load_template())
    assert "filterChips.excludeStandalone && STANDALONE_SOCIETIES.includes(" in html
    assert re.search(r"filterChips\.excludeIndependentHouses && d\.buildingType === ['\"]IH['\"]", html)
    # Known-no only; unknown (-1 / null / "") must still pass
    assert "filterChips.requireBalcony && d.balconies === 0" in html
    assert "filterChips.requireLift && d.hasLift === false" in html
    assert re.search(r"filterChips\.requireAnyParking && d\.parking === ['\"]NONE['\"]", html)
    assert "filterChips.requireLift && !d.hasLift" not in html
    assert not re.search(r"\(!d\.parking \|\| d\.parking === ['\"]NONE['\"]\)", html)
    assert "filterChips.requireGym && !d.hasGym" in html
    assert "filterChips.requireClubhouse && !d.hasClubhouse" in html
    assert "filterChips.requirePark && !d.hasPark" in html
    assert "filterChips.requireGated && !d.isGated" in html
    assert "filterChips.requireSecurity && !d.hasSecurity" in html
    assert "filterChips.requirePowerBackup && !d.hasPowerBackup" in html
    assert "filterChips.requireIntercom && !d.hasIntercom" in html
