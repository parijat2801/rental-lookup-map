// ===========================================================================
// Map, metro overlay, legend and marker jitter
// ===========================================================================
var map = L.map('map', {zoomControl: false}).setView([12.9716, 77.60], 12);
L.control.zoom({position: 'bottomright'}).addTo(map);
var ESRI_SERVICES = 'https://server.arcgisonline.com/ArcGIS/rest/services/';
var lightLayer = L.layerGroup();
// CARTO serves "API key required" watermark tiles without a key, so fall back to Esri's keyless light canvas.
if (CARTO_KEY) {
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png?key=' + encodeURIComponent(CARTO_KEY), {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
    }).addTo(lightLayer);
} else {
    L.tileLayer(ESRI_SERVICES + 'Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19, maxNativeZoom: 16,
        attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(lightLayer);
    L.tileLayer(ESRI_SERVICES + 'Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {maxZoom: 19, maxNativeZoom: 16}).addTo(lightLayer);
}
lightLayer.addTo(map);
var satelliteLayer = L.layerGroup([
    L.tileLayer(ESRI_SERVICES + 'World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19, maxNativeZoom: 18,
        attribution: 'Imagery &copy; Esri &mdash; Esri, Maxar, Earthstar Geographics'
    }),
    L.tileLayer(ESRI_SERVICES + 'Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {maxZoom: 19, maxNativeZoom: 18})
]);

map.createPane('metro');
map.getPane('metro').style.zIndex = 640;
var metroLayer = L.layerGroup();
var METRO_LINE_NAMES = {purple: 'Purple Line', green: 'Green Line', yellow: 'Yellow Line'};
Object.keys(METRO_LINES).forEach(function(lineId) {
    var line = METRO_LINES[lineId];
    L.polyline(line.path, {pane: 'metro', color: line.color, weight: 3, opacity: 0.8, interactive: false}).addTo(metroLayer);
    line.stations.forEach(function(station) {
        L.circleMarker([station.lat, station.lng], {pane: 'metro', radius: 3, color: line.color, weight: 1.5, fillColor: '#fff', fillOpacity: 1})
            .bindTooltip(station.name + ' \u00b7 ' + METRO_LINE_NAMES[lineId], {direction: 'top'})
            .addTo(metroLayer);
    });
});
metroLayer.addTo(map);

// Button under the zoom controls opening a panel of map layers (satellite imagery, metro overlay).
var layersControl = L.control({position: 'bottomright'});
layersControl.onAdd = function() {
    var container = L.DomUtil.create('div', 'layers-control');
    var bar = L.DomUtil.create('div', 'leaflet-bar', container);
    var button = L.DomUtil.create('a', '', bar);
    button.href = '#';
    button.title = 'Map layers';
    button.innerHTML = icon('layers');
    var panel = L.DomUtil.create('div', 'layers-panel', container);
    panel.hidden = true;
    var options = [
        {label: 'Satellite', iconName: 'satellite', isOn: function() { return map.hasLayer(satelliteLayer); },
         toggle: function() {
             if (map.hasLayer(satelliteLayer)) { map.removeLayer(satelliteLayer); lightLayer.addTo(map); }
             else { map.removeLayer(lightLayer); satelliteLayer.addTo(map); }
         }},
        {label: 'Metro lines', iconName: 'train-front', isOn: function() { return map.hasLayer(metroLayer); },
         toggle: function() { if (map.hasLayer(metroLayer)) map.removeLayer(metroLayer); else metroLayer.addTo(map); }}
    ];
    options.forEach(function(option) {
        var row = L.DomUtil.create('button', 'layer-option', panel);
        row.type = 'button';
        row.innerHTML = icon(option.iconName) + '<span>' + option.label + '</span>' + icon('check').replace('class="', 'class="check ');
        row.classList.toggle('on', option.isOn());
        row.onclick = function() { option.toggle(); row.classList.toggle('on', option.isOn()); };
    });
    function setOpen(open) { panel.hidden = !open; button.classList.toggle('on', open); }
    button.onclick = function(e) { e.preventDefault(); setOpen(panel.hidden); };
    document.addEventListener('click', function(e) { if (!container.contains(e.target)) setOpen(false); });
    document.addEventListener('keydown', function(e) { if (e.key === 'Escape') setOpen(false); });
    L.DomEvent.disableClickPropagation(container);
    L.DomEvent.disableScrollPropagation(container);
    return container;
};
layersControl.addTo(map);

// Top-left button bringing a collapsed sidebar back.
var sidebarToggle = L.control({position: 'topleft'});
sidebarToggle.onAdd = function() {
    var container = L.DomUtil.create('div', 'leaflet-bar sidebar-open-control');
    var button = L.DomUtil.create('a', '', container);
    button.href = '#';
    button.title = 'Show sidebar';
    button.innerHTML = icon('panel-left-open');
    button.onclick = function(e) { e.preventDefault(); toggleSidebar(false); };
    L.DomEvent.disableClickPropagation(container);
    return container;
};
sidebarToggle.addTo(map);

