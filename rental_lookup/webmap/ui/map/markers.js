// Listings sharing a (likely fake) coordinate get a deterministic pseudo-random
// offset (~±200m) so they don't hide each other.
LISTINGS.forEach(function(d, i) {
    if (d.isStacked) {
        var r1 = Math.sin(i * 127.1 + 311.7) * 43758.5453;
        var r2 = Math.sin(i * 269.5 + 183.3) * 43758.5453;
        d.mapLat = d.lat + (r1 - Math.floor(r1) - 0.5) * 0.004;
        d.mapLng = d.lng + (r2 - Math.floor(r2) - 0.5) * 0.004;
    } else {
        d.mapLat = d.lat;
        d.mapLng = d.lng;
    }
    d.propertyKey = d.isStacked ? null : d.lat.toFixed(4) + ',' + d.lng.toFixed(4);
});
var markerLayer = L.layerGroup().addTo(map);
// Several listings at one real spot (flats in the same building) fan out in a small ring
// so each marker stays clickable; the ring never strays more than FAN_MAX_METERS from the building.
var FAN_MAX_METERS = 40;
var fannedGroups = [];  // [{lat, lng, members: [{d, marker}]}] from the last renderMarkers()
function layoutFannedGroups() {
    var zoom = map.getZoom();
    fannedGroups.forEach(function(group) {
        var count = group.members.length;
        var center = map.project([group.lat, group.lng], zoom);
        var metersPerPixel = 40075016.686 * Math.cos(group.lat * Math.PI / 180) / Math.pow(2, zoom + 8);
        var radius = Math.min(Math.max(9, count * 14 / (2 * Math.PI)), FAN_MAX_METERS / metersPerPixel);
        group.members.forEach(function(member, i) {
            var angle = 2 * Math.PI * i / count - Math.PI / 2;
            var position = map.unproject(center.add([radius * Math.cos(angle), radius * Math.sin(angle)]), zoom);
            member.d.mapLat = position.lat;
            member.d.mapLng = position.lng;
            member.marker.setLatLng(position);
        });
    });
    if (selectedListing && map.hasLayer(pulseMarker)) pulseMarker.setLatLng([selectedListing.mapLat, selectedListing.mapLng]);
}
map.on('zoomend', layoutFannedGroups);
// Starred listings are drawn as a star (filled with the tier colour) instead of a circle.
var STAR_MARKER_SIZE = 18;
var justStarredUrls = new Set();  // star markers to animate on the next render
function starMarker(d, style) {
    var svgStyle = 'fill:' + style.fillColor + ';fill-opacity:' + style.fillOpacity + ';color:' + style.color +
        ';stroke-width:' + style.weight + (style.dashArray ? ';stroke-dasharray:3 3' : '');
    var marker = L.marker([d.mapLat, d.mapLng], {
        icon: L.divIcon({
            className: 'star-marker', iconSize: [STAR_MARKER_SIZE, STAR_MARKER_SIZE],
            html: '<span class="star-burst"></span>' + icon('star').replace('class="icon"', 'class="icon" style="' + svgStyle + '"')
        }),
        keyboard: false
    });
    if (justStarredUrls.has(d.url) && MOTION) marker.on('add', function() { popStarMarker(marker.getElement()); });
    return marker;
}
function popStarMarker(el) {
    var star = el.querySelector('svg'), burst = el.querySelector('.star-burst');
    gsap.fromTo(star, {scale: 0, rotation: -120}, {scale: 1, rotation: 0, duration: 0.6, ease: 'back.out(3)'});
    gsap.fromTo(star, {filter: 'drop-shadow(0 0 6px rgba(245,158,11,1))'}, {filter: 'drop-shadow(0 1px 1.5px rgba(0,0,0,.4))', duration: 0.9, ease: 'power2.out', clearProps: 'filter'});
    gsap.fromTo(burst, {scale: 0.4, opacity: 1}, {scale: 3, opacity: 0, duration: 0.7, ease: 'power2.out'});
}
// Pops the star toggle buttons (list card, pinned detail card) for a freshly starred listing.
function popStarButtons(url) {
    if (!MOTION) return;
    var buttons = [];
    document.querySelectorAll('#list .listing-card').forEach(function(card) {
        if (card.dataset.url === url) buttons.push(card.querySelector('.star-toggle svg'));
    });
    if (selectedListing && selectedListing.url === url) buttons.push(detailCard.querySelector('.actions button.on svg'));
    buttons = buttons.filter(Boolean);
    if (buttons.length) gsap.fromTo(buttons, {scale: 0.3, rotation: -90}, {scale: 1, rotation: 0, duration: 0.5, ease: 'back.out(3)'});
}
// Selected listing highlight: two expanding rings plus a blinking marker.
var pulseMarker = L.marker([0, 0], {icon: L.divIcon({className: 'pulse-marker', html: '<span>' + icon('star') + '</span><span>' + icon('star') + '</span>', iconSize: [0, 0]}), interactive: false, keyboard: false});
var markerBlink = null, ringPulse = null;
function highlightSelectedMarker(marker, d) {
    if (markerBlink) { markerBlink.kill(); markerBlink = null; }
    if (!marker) {
        if (ringPulse) { ringPulse.kill(); ringPulse = null; }
        pulseMarker.remove();
        return;
    }
    var isNew = !map.hasLayer(pulseMarker);
    pulseMarker.setLatLng([d.mapLat, d.mapLng]).addTo(map);
    var isStar = !marker.getRadius;
    var size = 2 * ((isStar ? STAR_MARKER_SIZE / 2 : marker.getRadius()) + 4);
    pulseMarker.getElement().classList.toggle('pulse-star', isStar);
    var rings = pulseMarker.getElement().querySelectorAll('span');
    rings.forEach(function(ring) {
        ring.style.width = ring.style.height = size + 'px';
        ring.style.margin = (-size / 2) + 'px 0 0 ' + (-size / 2) + 'px';
    });
    if (!MOTION) { rings[0].style.opacity = 1; return; }
    if (isNew) ringPulse = gsap.fromTo(rings, {scale: 1, opacity: 0.9}, {scale: 2.6, opacity: 0, duration: 1.4, ease: 'power1.out', repeat: -1, stagger: 0.7});
    markerBlink = gsap.to(marker.getElement(), {opacity: 0.35, duration: 0.5, ease: 'sine.inOut', repeat: -1, yoyo: true});
}
var detailCard = byId('detail-card');  // hover / pinned listing details
var filteredListings = [];  // result of the last refreshMap(), best-ranked first

