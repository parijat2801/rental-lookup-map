// ===========================================================================
// Box selection (shift + drag) and bulk actions
// ===========================================================================
var boxStart = null;
var boxOutline = null;

map.on("mousedown", function (e) {
    if (!e.originalEvent.shiftKey) return;
    boxStart = e.latlng;
    map.dragging.disable();
    if (boxOutline) map.removeLayer(boxOutline);
});
map.on("mousemove", function (e) {
    if (!boxStart || !e.originalEvent.shiftKey) return;
    if (boxOutline) map.removeLayer(boxOutline);
    boxOutline = L.rectangle([boxStart, e.latlng], {
        color: "#18181b",
        weight: 1.5,
        fillOpacity: 0.06,
        dashArray: "6 4",
    }).addTo(map);
});
map.on("mouseup", function (e) {
    if (!boxStart) return;
    map.dragging.enable();
    var bounds = L.latLngBounds(boxStart, e.latlng);
    if (boxOutline) map.removeLayer(boxOutline);
    boxOutline = null;
    boxStart = null;

    boxSelection = filteredListings.filter(function (d) {
        return bounds.contains([d.mapLat, d.mapLng]);
    });
    if (boxSelection.length === 0) return;
    refreshMap(); // highlight the selection
});
function renderSelectionBar() {
    var bar = byId("selection-bar"),
        wasHidden = bar.hidden;
    bar.hidden = boxSelection.length === 0;
    if (bar.hidden) return;
    if (wasHidden) animateIn(bar, { y: 16 }, 0.25);
    var unstarred = boxSelection.filter(function (d) {
        return !isStarred(d.url);
    }).length;
    byId("selection-count").textContent = boxSelection.length + " selected";
    byId("selection-star-label").textContent = "Star " + unstarred;
}

function starBoxSelection() {
    var urls = boxSelection
        .filter(function (d) {
            return !isStarred(d.url);
        })
        .map(function (d) {
            return d.url;
        });
    urls.forEach(function (url) {
        markStarred(url);
        justStarredUrls.add(url);
    });
    recordUndo("star", urls);
    clearBoxSelection();
    saveStars();
    toast(
        urls.length
            ? "Starred " + urls.length + " listings"
            : "Already starred",
    );
}
function dismissBoxSelection() {
    var urls = boxSelection.map(function (d) {
        return d.url;
    });
    urls.forEach(markDismissed);
    recordUndo("dismiss", urls);
    clearBoxSelection();
    saveStars();
    toast("Dismissed " + urls.length + " listings · Ctrl+Z to undo");
}
function clearBoxSelection() {
    boxSelection = [];
    refreshMap();
}
