// ===========================================================================
// Filter chips, sliders, the filters sheet and active-filter counts
// ===========================================================================
// One entry per chip (its data-filter attribute); true = filter active.
// All chips start off; last-session choices are restored from localStorage.
var filterChips = {
    bhk1: false,
    bhk2: false,
    bhk3: false,
    furnishedFull: false,
    furnishedSemi: false,
    furnishedNone: false,
    requireLift: false,
    requireCarParking: false,
    requireAnyParking: false,
    excludeWestFacing: false,
    requireBalcony: false,
    excludeStandalone: false,
    excludeIndependentHouses: false,
    requireRealPhoto: false,
    petFriendlyOnly: false,
    poolOnly: false,
    requireGym: false,
    requireClubhouse: false,
    requirePark: false,
    requireGated: false,
    requireSecurity: false,
    requirePowerBackup: false,
    requireIntercom: false,
    brandedBuilderOnly: false,
    excludeFakeLocations: false,
    sourceNoBroker: false,
    sourceMagicBricks: false,
    source99acres: false,
    sourcePropertyAngel: false,
    penthouseOnly: false,
    newTodayOnly: false,
    starredOnly: false,
    hideDismissed: false,
};
var DEFAULT_FILTER_CHIPS = JSON.parse(JSON.stringify(filterChips));
var SLIDER_IDS = [
    "filter-cost-min",
    "filter-cost-max",
    "filter-sqft",
    "filter-photos",
    "filter-deposit",
    "filter-score",
    "filter-days",
];
// Sliders that stop filtering at their max end; the rest stop filtering at their min end.
var SLIDERS_OFF_AT_MAX = ["filter-cost-max", "filter-deposit", "filter-days"];
// Chips shown outside the sheet; they don't count towards the "Filters" badge.
var QUICK_FILTERS = ["starredOnly"];
var FILTERS_STORAGE_KEY = "rental_filters";

function saveFilters() {
    try {
        var sliders = {};
        SLIDER_IDS.forEach(function (id) {
            sliders[id] = byId(id).value;
        });
        localStorage.setItem(
            FILTERS_STORAGE_KEY,
            JSON.stringify({
                chips: filterChips,
                sliders: sliders,
                search: byId("search-input").value,
            }),
        );
    } catch (e) {}
}
function loadFilters() {
    try {
        var saved = JSON.parse(localStorage.getItem(FILTERS_STORAGE_KEY));
        if (!saved) return;
        if (saved.chips) {
            for (var name in filterChips) {
                if (typeof saved.chips[name] === "boolean")
                    filterChips[name] = saved.chips[name];
            }
        }
        if (saved.sliders) {
            SLIDER_IDS.forEach(function (id) {
                if (saved.sliders[id] != null) byId(id).value = saved.sliders[id];
            });
        }
        if (typeof saved.search === "string")
            byId("search-input").value = saved.search;
    } catch (e) {}
}
loadFilters();

function toggleChip(chip) {
    filterChips[chip.dataset.filter] = !filterChips[chip.dataset.filter];
    syncChips();
    refreshMap();
}
function syncChips() {
    document.querySelectorAll("[data-filter]").forEach(function (chip) {
        var on = !!filterChips[chip.dataset.filter];
        chip.classList.toggle("on", on);
        chip.setAttribute("aria-pressed", on);
    });
}
// Clear every filter (chips off, sliders at their no-op end, search empty).
// Page-load defaults stay in DEFAULT_FILTER_CHIPS for the "changed" counts.
function resetFilters() {
    Object.keys(filterChips).forEach(function (name) {
        filterChips[name] = false;
    });
    SLIDER_IDS.forEach(function (id) {
        var el = byId(id);
        el.value = SLIDERS_OFF_AT_MAX.indexOf(id) >= 0 ? el.max : el.min;
    });
    byId("search-input").value = "";
    syncChips();
    refreshMap();
}
function openFilters() {
    byId("filters-sheet").classList.add("open");
    if (MOTION)
        gsap.fromTo(
            "#filters-sheet .filter-section",
            { autoAlpha: 0, y: 8 },
            {
                autoAlpha: 1,
                y: 0,
                duration: 0.25,
                stagger: 0.03,
                delay: 0.08,
                ease: "power2.out",
            },
        );
}
function closeFilters() {
    byId("filters-sheet").classList.remove("open");
}
function filtersOpen() {
    return byId("filters-sheet").classList.contains("open");
}

function onCostInput(slider) {
    var low = byId("filter-cost-min"),
        high = byId("filter-cost-max");
    if (+low.value > +high.value)
        slider.value = slider === low ? high.value : low.value;
    refreshMap();
}
function paintSliders() {
    document
        .querySelectorAll("#filters-sheet input[type=range]")
        .forEach(function (el) {
            el.style.setProperty(
                "--fill",
                ((el.value - el.min) / (el.max - el.min)) * 100 + "%",
            );
        });
    var low = byId("filter-cost-min"),
        high = byId("filter-cost-max"),
        max = +high.max;
    var fill = byId("cost-track-fill");
    fill.style.left = (low.value / max) * 100 + "%";
    fill.style.right = 100 - (high.value / max) * 100 + "%";
}

function isNonDefault(el) {
    if (el.dataset && el.dataset.filter)
        return (
            filterChips[el.dataset.filter] !==
            DEFAULT_FILTER_CHIPS[el.dataset.filter]
        );
    return +el.value !== +el.defaultValue;
}
function sliderApplied(id) {
    var el = byId(id);
    return SLIDERS_OFF_AT_MAX.indexOf(id) >= 0
        ? +el.value < +el.max
        : +el.value > +el.min;
}
// Badge = filters currently narrowing results (the budget range counts once).
// Button highlight and section counts = controls moved off their defaults (HTML value attribute).
function updateActiveFilterCount() {
    var applied = 0,
        changed = 0;
    for (var name in DEFAULT_FILTER_CHIPS) {
        if (QUICK_FILTERS.indexOf(name) >= 0) continue;
        if (filterChips[name]) applied++;
        if (filterChips[name] !== DEFAULT_FILTER_CHIPS[name]) changed++;
    }
    if (sliderApplied("filter-cost-min") || sliderApplied("filter-cost-max"))
        applied++;
    SLIDER_IDS.forEach(function (id) {
        if (
            id !== "filter-cost-min" &&
            id !== "filter-cost-max" &&
            sliderApplied(id)
        )
            applied++;
        if (isNonDefault(byId(id))) changed++;
    });
    var badge = byId("active-filter-count");
    badge.textContent = applied;
    badge.hidden = applied === 0;
    byId("filters-button").classList.toggle("on", changed > 0);
    document.querySelectorAll(".filter-section").forEach(function (section) {
        var changed = [].filter.call(
            section.querySelectorAll("[data-filter], input[type=range]"),
            isNonDefault,
        ).length;
        section.querySelector(".section-count").textContent = changed
            ? "· " + changed + " changed"
            : "";
    });
}
