"""No chips or sliders narrow results by default; last-session filters are restored from localStorage."""
import re

import pytest

from rental_lookup.webmap.builder import load_template

MUST_HAVE_CHIPS = (
    "excludeStandalone",
    "excludeIndependentHouses",
    "requireBalcony",
    "requireLift",
    "requireAnyParking",
    "requireCarParking",
    "requireRealPhoto",
    "hideDismissed",
    "bhk1",
    "bhk2",
    "furnishedFull",
    "furnishedSemi",
)

AMENITY_CHIPS = (
    "poolOnly",
    "requireGym",
    "requireClubhouse",
    "requirePark",
    "requireGated",
    "requireSecurity",
    "requirePowerBackup",
    "requireIntercom",
)

# Sliders that stop filtering at max / min; HTML defaults must sit at that end.
SLIDER_DEFAULTS = (
    ("filter-cost-min", "0"),
    ("filter-cost-max", "150000"),
    ("filter-deposit", "20"),
    ("filter-sqft", "500"),
    ("filter-photos", "0"),
    ("filter-score", "0"),
    ("filter-days", "90"),
)


def _default_state(html):
    return re.search(r"var filterChips = \{(.*?)\};", html, re.S).group(1).replace(" ", "")


def _compact(html):
    return re.sub(r"\s+", " ", html)


@pytest.mark.parametrize("name", MUST_HAVE_CHIPS + AMENITY_CHIPS)
def test_chip_off_by_default(name):
    assert f"{name}:false" in _default_state(load_template())


@pytest.mark.parametrize("name", MUST_HAVE_CHIPS + AMENITY_CHIPS)
def test_chip_markup_matches_default(name):
    html = _compact(load_template())
    assert f'data-filter="{name}"' in html
    assert not re.search(rf'class="chip on"[^>]*data-filter="{name}"', html)


@pytest.mark.parametrize("slider_id,value", SLIDER_DEFAULTS)
def test_slider_at_noop_by_default(slider_id, value):
    html = _compact(load_template())
    tag = re.search(rf'<input[^>]*id="{slider_id}"[^>]*>', html)
    assert tag, f"missing slider {slider_id}"
    assert f'value="{value}"' in tag.group(0)


def test_filters_persisted_to_local_storage():
    html = load_template()
    assert 'FILTERS_STORAGE_KEY = "rental_filters"' in html
    assert "function saveFilters()" in html
    assert "function loadFilters()" in html
    assert "loadFilters();" in html
    assert "saveFilters();" in html


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
