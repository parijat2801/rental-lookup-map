// The user's position (browser geolocation): a blue dot plus an accuracy circle.
// Tracking starts on load; the button above the layers button centres the map on it.
var userLocation = null;
var userMarker = L.marker([0, 0], {
    icon: L.divIcon({
        className: "user-location",
        html: "<span></span>",
        iconSize: [18, 18],
    }),
    interactive: false,
    keyboard: false,
    zIndexOffset: 1000,
});
var userAccuracy = L.circle([0, 0], {
    radius: 0,
    stroke: false,
    fillColor: "#2563eb",
    fillOpacity: 0.08,
    interactive: false,
});
var locateButton = null,
    centerOnNextFix = false,
    locationWatch = null;
function onPosition(position) {
    userLocation = L.latLng(
        position.coords.latitude,
        position.coords.longitude,
    );
    userMarker.setLatLng(userLocation).addTo(map);
    userAccuracy
        .setLatLng(userLocation)
        .setRadius(position.coords.accuracy)
        .addTo(map);
    locateButton.innerHTML = icon("locate-fixed");
    locateButton.classList.add("locating");
    if (centerOnNextFix) {
        centerOnNextFix = false;
        map.flyTo(userLocation, Math.max(map.getZoom(), 15), { duration: 0.8 });
    }
}
function onPositionError(error) {
    var requestedByUser = centerOnNextFix;
    centerOnNextFix = false;
    if (locationWatch !== null) navigator.geolocation.clearWatch(locationWatch);
    locationWatch = null;
    locateButton.innerHTML = icon("locate-off");
    locateButton.classList.remove("locating");
    if (!requestedByUser) return; // stay quiet about the automatic attempt on load
    if (error.code === error.PERMISSION_DENIED)
        toast("Location access is blocked for this page");
    else toast("Could not get your location");
}
function startLocating() {
    if (!navigator.geolocation) {
        toast("Location is not supported in this browser");
        return;
    }
    if (locationWatch === null)
        locationWatch = navigator.geolocation.watchPosition(
            onPosition,
            onPositionError,
            { enableHighAccuracy: true, maximumAge: 30000 },
        );
}
function locateUser() {
    if (userLocation)
        map.flyTo(userLocation, Math.max(map.getZoom(), 15), { duration: 0.8 });
    else {
        centerOnNextFix = true;
        startLocating();
    }
}
var locateControl = L.control({ position: "bottomright" });
locateControl.onAdd = function () {
    var container = L.DomUtil.create("div", "leaflet-bar");
    locateButton = L.DomUtil.create("a", "", container);
    locateButton.href = "#";
    locateButton.title = "Show my location";
    locateButton.innerHTML = icon("locate");
    locateButton.onclick = function (e) {
        e.preventDefault();
        locateUser();
    };
    L.DomEvent.disableClickPropagation(container);
    return container;
};
locateControl.addTo(map);
startLocating();
