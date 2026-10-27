// ===========================================================================
// Filtering and rendering
// ===========================================================================
function readSliders() {
    return {
        costMin: +byId("filter-cost-min").value,
        costMax: +byId("filter-cost-max").value,
        minSqft: +byId("filter-sqft").value,
        minPhotos: +byId("filter-photos").value,
        maxDepositMonths: +byId("filter-deposit").value,
        minScore: +byId("filter-score").value,
        maxDaysAgo: +byId("filter-days").value,
        searchTerms: byId("search-input")
            .value.toLowerCase()
            .split(/\s+/)
            .filter(Boolean),
    };
}
var searchDebounce;
function onSearchInput() {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(refreshMap, 150);
}
function passesFilters(d, sliders) {
    if (sliders.searchTerms.length) {
        var haystack = (
            (d.society || "") +
            " " +
            (d.locality || "")
        ).toLowerCase();
        if (
            !sliders.searchTerms.every(function (term) {
                return haystack.indexOf(term) >= 0;
            })
        )
            return false;
    }
    if (d.totalCost < sliders.costMin || d.totalCost > sliders.costMax)
        return false;
    if (d.sqft < sliders.minSqft) return false;
    if (d.photoCount < sliders.minPhotos) return false;
    if (d.rent > 0 && d.deposit / d.rent > sliders.maxDepositMonths)
        return false;
    // BHK chips are an OR-set: none selected = show all
    if (filterChips.bhk1 || filterChips.bhk2 || filterChips.bhk3) {
        if (!(
            (filterChips.bhk1 && d.bhk === "BHK1") ||
            (filterChips.bhk2 && d.bhk === "BHK2") ||
            (filterChips.bhk3 && d.bhk === "BHK3")
        ))
            return false;
    }
    // Furnishing chips are an OR-set too; unknown furnishing only passes when none are selected
    if (
        filterChips.furnishedFull ||
        filterChips.furnishedSemi ||
        filterChips.furnishedNone
    ) {
        if (!(
            (filterChips.furnishedFull && d.furnishing === "FULL") ||
            (filterChips.furnishedSemi && d.furnishing === "SEMI") ||
            (filterChips.furnishedNone && d.furnishing === "NONE")
        ))
            return false;
    }
    // Unknown values pass for these must-haves (null lift, "" parking, -1 balconies)
    if (filterChips.requireLift && d.hasLift === false) return false;
    if (filterChips.requireCarParking && !CAR_PARKING_TYPES.includes(d.parking))
        return false;
    if (filterChips.requireAnyParking && d.parking === "NONE") return false;
    if (filterChips.excludeWestFacing && ["W", "NW"].includes(d.facing))
        return false;
    if (filterChips.requireBalcony && d.balconies === 0) return false;
    if (
        filterChips.excludeStandalone &&
        STANDALONE_SOCIETIES.includes((d.society || "").toLowerCase().trim())
    )
        return false;
    if (filterChips.excludeIndependentHouses && d.buildingType === "IH")
        return false;
    if (filterChips.requireRealPhoto && !d.hasRealPhoto) return false;
    if (filterChips.petFriendlyOnly && !d.isPetFriendly) return false;
    if (filterChips.poolOnly && !d.hasPool) return false;
    if (filterChips.requireGym && !d.hasGym) return false;
    if (filterChips.requireClubhouse && !d.hasClubhouse) return false;
    if (filterChips.requirePark && !d.hasPark) return false;
    if (filterChips.requireGated && !d.isGated) return false;
    if (filterChips.requireSecurity && !d.hasSecurity) return false;
    if (filterChips.requirePowerBackup && !d.hasPowerBackup) return false;
    if (filterChips.requireIntercom && !d.hasIntercom) return false;
    if (filterChips.brandedBuilderOnly && !d.isBrandedBuilder) return false;
    if (filterChips.excludeFakeLocations && d.isFakeLocation) return false;
    // Source chips are an OR-set: none selected = show all
    if (
        filterChips.sourceNoBroker ||
        filterChips.sourceMagicBricks ||
        filterChips.source99acres ||
        filterChips.sourcePropertyAngel
    ) {
        if (!(
            (filterChips.sourceNoBroker && d.source === "nb") ||
            (filterChips.sourceMagicBricks && d.source === "mb") ||
            (filterChips.source99acres && d.source === "9a") ||
            (filterChips.sourcePropertyAngel && d.source === "pa")
        ))
            return false;
    }
    if (
        filterChips.penthouseOnly &&
        (d.totalFloors < 4 || d.floor !== d.totalFloors)
    )
        return false; // top floor of 4+
    if (filterChips.newTodayOnly && d.daysAgo !== 0) return false;
    if (filterChips.starredOnly && !isStarred(d.url)) return false;
    if (filterChips.hideDismissed && isDismissed(d.url)) return false;
    return true;
}

// Re-apply filters and ranking, then redraw markers and the sidebar list.
function refreshMap() {
    updateActiveFilterCount();
    paintSliders();
    saveFilters();
    var sliders = readSliders();
    var rankMode = effectiveRankMode(),
        mode = RANK_MODES[rankMode];

    byId("value-cost").textContent =
        formatRupeesShort(sliders.costMin) +
        " – " +
        formatRupeesShort(sliders.costMax) +
        (sliders.costMax >= +byId("filter-cost-max").max ? "+" : "");
    byId("value-sqft").textContent = sliders.minSqft.toLocaleString() + " sqft";
    byId("value-photos").textContent = sliders.minPhotos || "Any";
    byId("value-deposit").textContent =
        sliders.maxDepositMonths >= 20
            ? "Any"
            : sliders.maxDepositMonths + "× rent";
    byId("value-score").textContent = sliders.minScore || "Any";
    byId("score-label").textContent = mode.label;
    byId("value-days").textContent =
        sliders.maxDaysAgo >= 90
            ? "Any time"
            : sliders.maxDaysAgo === 0
              ? "Today"
              : sliders.maxDaysAgo + " days";

    var matches = LISTINGS.filter(function (d) {
        if (
            !passesFilters(d, sliders) ||
            d.scores[mode.score] < sliders.minScore
        )
            return false;
        // 90 = "Any"; otherwise listings with unknown age (delisted, -1) are hidden
        return (
            sliders.maxDaysAgo >= 90 ||
            (d.daysAgo >= 0 && d.daysAgo <= sliders.maxDaysAgo)
        );
    });
    var tiers = (currentTiers = tiersForScore(mode.score));
    matches.sort(mode.sort);
    filteredListings = matches;

    byId("result-summary").textContent =
        matches.length.toLocaleString() +
        " of " +
        LISTINGS.length.toLocaleString() +
        " listings match";
    byId("show-results-button").textContent =
        "Show " + matches.length.toLocaleString() + " listings";
    byId("sort-hint").textContent = "Sorted by " + mode.sortedBy;
    renderMarkers(matches, tiers, mode.score);
    renderSidebarList();
    renderSelectionBar();
    if (selectedListing) showDetailCard(null, selectedListing);
    scheduleRouting();
}

function renderMarkers(listings, tiers, scoreName) {
    var boxSelectedUrls = new Set(
        boxSelection.map(function (d) {
            return d.url;
        }),
    );
    markerLayer.clearLayers();
    var selectedMarker = null;
    var listingsByProperty = {},
        markersByUrl = {};
    listings.forEach(function (d) {
        if (!d.propertyKey) return;
        d.mapLat = d.lat;
        d.mapLng = d.lng;
        (listingsByProperty[d.propertyKey] =
            listingsByProperty[d.propertyKey] || []).push(d);
    });
    listings.forEach(function (d, index) {
        d.rank = index + 1;
        var isSelected = selectedListing && selectedListing.url === d.url;
        var isBoxSelected = boxSelectedUrls.has(d.url);
        var fill = d.isDelisted
            ? "#d1d5db"
            : tierColor(d.scores[scoreName], tiers);
        // Outline: box-selected > plain (the selected listing is shown by the pulsing rings)
        var outline = isBoxSelected ? "#2563eb" : fill;
        var outlineWidth = isBoxSelected ? 5 : 2;
        var fillOpacity = d.isDelisted ? 0.25 : d.isStacked ? 0.4 : 0.65;
        var dashArray = d.isStacked ? "4 4" : null;
        var marker = isStarred(d.url)
            ? starMarker(d, {
                  color: isBoxSelected ? outline : "#fff",
                  weight: isBoxSelected ? 3 : 2,
                  fillColor: fill,
                  fillOpacity: d.isDelisted ? 0.25 : d.isStacked ? 0.5 : 0.95,
                  dashArray: dashArray,
              })
            : L.circleMarker([d.mapLat, d.mapLng], {
                  radius: 5,
                  color: outline,
                  weight: outlineWidth,
                  fillColor: fill,
                  fillOpacity: fillOpacity,
                  dashArray: dashArray,
              });
        marker.on("mouseover", function (e) {
            if (!selectedListing) showDetailCard(e, d);
        });
        marker.on("mouseout", function () {
            if (!selectedListing || selectedListing.url !== d.url) {
                detailCard.style.display = "none";
                detailCard.style.pointerEvents = "none";
            }
        });
        marker.on("click", function (e) {
            e.originalEvent.handledByMarker = true;
            selectListing(d, e);
        });
        markerLayer.addLayer(marker);
        markersByUrl[d.url] = marker;
        if (isSelected) selectedMarker = marker;
    });
    // Sorted by URL so a listing keeps its place in the ring when the ranking changes.
    fannedGroups = Object.keys(listingsByProperty)
        .map(function (key) {
            return listingsByProperty[key];
        })
        .filter(function (group) {
            return group.length > 1;
        })
        .map(function (group) {
            group.sort(function (a, b) {
                return a.url < b.url ? -1 : 1;
            });
            return {
                lat: group[0].lat,
                lng: group[0].lng,
                members: group.map(function (d) {
                    return { d: d, marker: markersByUrl[d.url] };
                }),
            };
        });
    layoutFannedGroups();
    justStarredUrls.clear();
    highlightSelectedMarker(selectedMarker, selectedListing);
}
