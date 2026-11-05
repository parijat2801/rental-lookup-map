// --- State and persistence -------------------------------------------------------
function loadStored(key, fallback) {
    try {
        var value = JSON.parse(localStorage.getItem(key));
        return value == null ? fallback : value;
    } catch (e) {
        return fallback;
    }
}
function storeValue(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {}
}
var areasOfInterest = loadStored("rental_areas_of_interest", []).filter(
    function (a) {
        return a && a.id && isFinite(a.lat) && isFinite(a.lng);
    },
);
var driveCache = loadStored("rental_commute_cache", {}); // "lat,lng|areaId" -> [seconds, metres]; -1 = no route
var areasPanelCollapsed = !!loadStored("rental_areas_panel_collapsed", false);
areasOfInterest.forEach(function (area) {
    area.stations = nearestStations(area.lat, area.lng);
});
function saveAreas() {
    storeValue(
        "rental_areas_of_interest",
        areasOfInterest.map(function (a) {
            return { id: a.id, name: a.name, lat: a.lat, lng: a.lng };
        }),
    );
}
var driveCacheSaveTimer = null;
function saveDriveCacheSoon() {
    clearTimeout(driveCacheSaveTimer);
    driveCacheSaveTimer = setTimeout(function () {
        storeValue("rental_commute_cache", driveCache);
    }, 1000);
}
