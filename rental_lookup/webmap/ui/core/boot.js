// ===========================================================================
// Boot
// ===========================================================================
map.on("moveend", renderSidebarList);
map.on("zoomend", renderSidebarList);
syncChips();
refreshMap();
setTimeout(function () {
    map.invalidateSize();
}, 500);
