// --- Adding, removing and showing areas -------------------------------------------------
var areaLayer = L.layerGroup().addTo(map);
map.attributionControl.addAttribution(
    'Routing <a href="https://project-osrm.org">OSRM</a> · Search <a href="https://photon.komoot.io">Photon</a>',
);
function onAreasChanged(showCommuteTab) {
    saveAreas();
    renderAreas();
    routingFailures = 0;
    refreshCommuteScores();
    if (showCommuteTab && activeRankMode !== "commute") setRankMode("commute");
    else refreshMap();
}
function addArea(name, lat, lng) {
    if (areasOfInterest.length >= MAX_AREAS) {
        toast("Up to " + MAX_AREAS + " places of interest");
        return null;
    }
    var area = {
        id:
            "a" +
            Date.now().toString(36) +
            Math.random().toString(36).slice(2, 6),
        name: name,
        lat: lat,
        lng: lng,
        stations: nearestStations(lat, lng),
    };
    areasOfInterest.push(area);
    toast("Added " + name);
    onAreasChanged(true);
    return area;
}
function removeArea(id) {
    areasOfInterest = areasOfInterest.filter(function (a) {
        return a.id !== id;
    });
    var suffix = "|" + id;
    Object.keys(driveCache).forEach(function (key) {
        if (key.slice(-suffix.length) === suffix) delete driveCache[key];
    });
    saveDriveCacheSoon();
    closeAreaContextMenu();
    onAreasChanged();
}
function renameArea(id, name) {
    areasOfInterest.forEach(function (a) {
        if (a.id === id) a.name = name;
    });
    saveAreas();
    renderAreas();
    if (selectedListing) showDetailCard(null, selectedListing);
}
function focusArea(id) {
    var area = areasOfInterest.find(function (a) {
        return a.id === id;
    });
    if (area)
        map.flyTo([area.lat, area.lng], Math.max(map.getZoom(), 14), {
            duration: 0.8,
        });
}
function renderAreas() {
    areaLayer.clearLayers();
    areasOfInterest.forEach(function (area) {
        L.marker([area.lat, area.lng], {
            icon: L.divIcon({
                className: "area-marker",
                html: "<span>" + icon("map-pin") + "</span>",
                iconSize: [28, 28],
                iconAnchor: [14, 28],
            }),
            zIndexOffset: 2000,
            keyboard: false,
        })
            .bindTooltip(escapeHtml(area.name), {
                direction: "top",
                offset: [0, -28],
            })
            .on("click", function (e) {
                L.DomEvent.stopPropagation(e);
                openAreaContextMenu(
                    e.originalEvent.clientX,
                    e.originalEvent.clientY,
                    '<button type="button" class="area-menu-item" role="menuitem">' +
                        icon("map-pin-minus") +
                        "Remove place of interest</button>",
                    function () {
                        removeArea(area.id);
                    },
                );
            })
            .addTo(areaLayer);
    });
    byId("area-list").innerHTML = areasOfInterest
        .map(function (area) {
            return (
                '<span class="area-chip"><button type="button" class="area-name" title="Show on map" onclick="focusArea(\'' +
                area.id +
                "')\">" +
                icon("map-pin") +
                escapeHtml(area.name) +
                '</button><button type="button" aria-label="Remove ' +
                escapeHtml(area.name) +
                '" onclick="removeArea(\'' +
                area.id +
                "')\">" +
                icon("x") +
                "</button></span>"
            );
        })
        .join("");
    byId("area-add-label").textContent = areasOfInterest.length
        ? "Add"
        : "Add place";
    var count = byId("areas-count");
    count.hidden = !areasOfInterest.length;
    count.textContent = areasOfInterest.length
        ? String(areasOfInterest.length)
        : "";
    syncAreaSearchUi();
}
function applyAreasPanelCollapsed() {
    byId("areas-panel").classList.toggle("collapsed", areasPanelCollapsed);
    byId("areas-toggle").setAttribute(
        "aria-expanded",
        areasPanelCollapsed ? "false" : "true",
    );
    if (areasPanelCollapsed) closeAreaSearch();
}
function toggleAreasPanel() {
    areasPanelCollapsed = !areasPanelCollapsed;
    storeValue("rental_areas_panel_collapsed", areasPanelCollapsed);
    applyAreasPanelCollapsed();
}
function syncAreaSearchUi() {
    var searching = !byId("area-search").hidden;
    byId("area-add").hidden = searching || areasOfInterest.length >= MAX_AREAS;
}
function openAreaSearch() {
    if (areasPanelCollapsed) {
        areasPanelCollapsed = false;
        storeValue("rental_areas_panel_collapsed", false);
        applyAreasPanelCollapsed();
    }
    byId("area-search").hidden = false;
    syncAreaSearchUi();
    byId("area-input").focus();
}
function closeAreaSearch() {
    byId("area-input").value = "";
    showAreaSuggestions([]);
    byId("area-search").hidden = true;
    syncAreaSearchUi();
}
applyAreasPanelCollapsed();

// Coordinates from a Google Maps URL (place pin, query or viewport) or a bare "lat, lng".
function parseLatLng(text) {
    try {
        text = decodeURIComponent(text);
    } catch (e) {}
    var patterns = [
        /!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)/,
        /[?&](?:q|query|ll|destination|center)=(-?\d+\.\d+),\s*(-?\d+\.\d+)/,
        /@(-?\d+\.\d+),(-?\d+\.\d+)/,
        /^\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*$/,
    ];
    for (var i = 0; i < patterns.length; i++) {
        var m = text.match(patterns[i]);
        if (m && Math.abs(+m[1]) <= 90 && Math.abs(+m[2]) <= 180)
            return { lat: +m[1], lng: +m[2] };
    }
    return null;
}
function placeNameFromMapsUrl(text) {
    var m = text.match(/\/place\/([^\/@?]+)/);
    if (!m) return "";
    try {
        return decodeURIComponent(m[1].replace(/\+/g, " "))
            .split(",")[0]
            .trim();
    } catch (e) {
        return "";
    }
}
function isShortMapsLink(text) {
    return /maps\.app\.goo\.gl|goo\.gl\/maps/.test(text);
}
function photonPlace(feature) {
    var p = feature.properties || {},
        c = feature.geometry.coordinates;
    var name =
        p.name ||
        [p.housenumber, p.street].filter(Boolean).join(" ") ||
        p.district ||
        p.city ||
        "Pinned location";
    var detail = [p.name ? p.street : "", p.locality, p.district, p.city]
        .filter(function (part, i, all) {
            return part && part !== name && all.indexOf(part) === i;
        })
        .join(", ");
    return { name: name, detail: detail, lat: c[1], lng: c[0] };
}

var areaSuggestions = [],
    areaSuggestionIndex = 0,
    areaSearchDebounce = null,
    areaSearchSequence = 0;
function showAreaSuggestions(places) {
    areaSuggestions = places;
    areaSuggestionIndex = 0;
    var box = byId("area-suggestions");
    box.hidden = places.length === 0;
    box.innerHTML = places
        .map(function (place, i) {
            return (
                '<button type="button" class="area-suggestion' +
                (i === 0 ? " on" : "") +
                '" role="option" data-index="' +
                i +
                '">' +
                escapeHtml(place.name) +
                (place.detail
                    ? "<small>" + escapeHtml(place.detail) + "</small>"
                    : "") +
                "</button>"
            );
        })
        .join("");
}
function pickAreaSuggestion(index) {
    var place = areaSuggestions[index];
    if (!place) return;
    closeAreaSearch();
    addArea(place.name, place.lat, place.lng);
}
function onAreaInput() {
    clearTimeout(areaSearchDebounce);
    areaSearchSequence++;
    var text = byId("area-input").value.trim(),
        pasted = parseLatLng(text);
    if (pasted) {
        var name = placeNameFromMapsUrl(text) || "Pinned location";
        return showAreaSuggestions([
            {
                name: name,
                detail: pasted.lat.toFixed(5) + ", " + pasted.lng.toFixed(5),
                lat: pasted.lat,
                lng: pasted.lng,
            },
        ]);
    }
    if (text.length < 3 || isShortMapsLink(text) || /^https?:/.test(text))
        return showAreaSuggestions([]);
    var sequence = areaSearchSequence;
    areaSearchDebounce = setTimeout(function () {
        fetch(
            PHOTON_URL +
                "api/?q=" +
                encodeURIComponent(text) +
                "&lat=12.97&lon=77.60&bbox=" +
                BANGALORE_BBOX +
                "&limit=5",
        )
            .then(function (r) {
                return r.json();
            })
            .then(function (body) {
                if (sequence === areaSearchSequence)
                    showAreaSuggestions((body.features || []).map(photonPlace));
            })
            .catch(function () {
                if (sequence === areaSearchSequence)
                    toast("Place search is unavailable right now");
            });
    }, 300);
}
function onAreaKeydown(e) {
    var text = e.target.value.trim();
    if (e.key === "Escape") {
        e.preventDefault();
        if (areaSuggestions.length) showAreaSuggestions([]);
        else closeAreaSearch();
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (!areaSuggestions.length) return;
        e.preventDefault();
        areaSuggestionIndex =
            (areaSuggestionIndex +
                (e.key === "ArrowDown" ? 1 : -1) +
                areaSuggestions.length) %
            areaSuggestions.length;
        byId("area-suggestions")
            .querySelectorAll(".area-suggestion")
            .forEach(function (el, i) {
                el.classList.toggle("on", i === areaSuggestionIndex);
            });
    } else if (e.key === "Enter") {
        e.preventDefault();
        if (areaSuggestions.length) pickAreaSuggestion(areaSuggestionIndex);
        else if (isShortMapsLink(text))
            toast(
                "Short links can't be read here: open it and paste the full Google Maps URL",
            );
        else if (/^https?:/.test(text))
            toast(
                "No coordinates in that link: copy the URL from the address bar after the map loads",
            );
    }
}
byId("area-suggestions").addEventListener("mousedown", function (e) {
    var option = e.target.closest(".area-suggestion");
    if (option) {
        e.preventDefault();
        pickAreaSuggestion(+option.dataset.index);
    }
});
byId("area-input").addEventListener("blur", function () {
    // Defer so suggestion mousedown can run first.
    setTimeout(function () {
        if (document.activeElement === byId("area-input")) return;
        showAreaSuggestions([]);
        if (!byId("area-input").value.trim()) closeAreaSearch();
    }, 0);
});

// Context menu for adding (right-click map) or removing (click pin) a place.
var areaContextMenu = null;
function closeAreaContextMenu() {
    if (!areaContextMenu) return;
    areaContextMenu.remove();
    areaContextMenu = null;
}
function placeAreaContextMenu(menu, x, y) {
    // Cursor is the top-left corner; flip if that would clip the viewport.
    var pad = 8,
        w = menu.offsetWidth,
        h = menu.offsetHeight,
        vw = window.innerWidth,
        vh = window.innerHeight;
    if (x + w + pad > vw) x = Math.max(pad, x - w);
    if (y + h + pad > vh) y = Math.max(pad, y - h);
    menu.style.left = x + "px";
    menu.style.top = y + "px";
}
function openAreaContextMenu(x, y, html, onPick) {
    closeAreaContextMenu();
    var menu = L.DomUtil.create("div", "area-context-menu", document.body);
    menu.setAttribute("role", "menu");
    menu.innerHTML = html;
    menu.querySelector("button").onclick = function () {
        closeAreaContextMenu();
        onPick();
    };
    placeAreaContextMenu(menu, x, y);
    areaContextMenu = menu;
}
map.on("contextmenu", function (e) {
    L.DomEvent.preventDefault(e.originalEvent);
    var lat = e.latlng.lat,
        lng = e.latlng.lng;
    openAreaContextMenu(
        e.originalEvent.clientX,
        e.originalEvent.clientY,
        '<button type="button" class="area-menu-item" role="menuitem">' +
            icon("map-pin-plus") +
            "Add as place of interest</button>",
        function () {
            var area = addArea("Pinned location", lat, lng);
            if (!area) return;
            fetch(PHOTON_URL + "reverse?lat=" + lat + "&lon=" + lng)
                .then(function (r) {
                    return r.json();
                })
                .then(function (body) {
                    if (body.features && body.features.length)
                        renameArea(area.id, photonPlace(body.features[0]).name);
                })
                .catch(function () {});
        },
    );
});
map.on("mousedown zoomstart movestart", closeAreaContextMenu);
document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAreaContextMenu();
});
document.addEventListener(
    "mousedown",
    function (e) {
        if (areaContextMenu && !areaContextMenu.contains(e.target))
            closeAreaContextMenu();
    },
    true,
);
