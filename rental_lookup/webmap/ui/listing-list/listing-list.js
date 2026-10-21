// Sidebar list: the first 100 filtered listings inside the current map view.
function renderSidebarList() {
    var bounds = map.getBounds();
    var inView = filteredListings.filter(function(d) { return bounds.contains([d.lat, d.lng]); });
    byId('stats').innerHTML = '<b>' + inView.length.toLocaleString() + '</b> in view' + (inView.length > 100 ? ' · showing top 100' : '');

    if (inView.length === 0) {
        byId('list').innerHTML = '<div class="empty-state">' + icon('search-x') +
            '<div>No listings here</div><div class="hint">Zoom out or loosen your filters.</div></div>';
        return;
    }
    byId('list').innerHTML = inView.slice(0, 100).map(function(d) {
        var starred = isStarred(d.url);
        var tags = amenityLabels(d).slice(0, 3);
        if (d.isBrandedBuilder) tags.unshift('Branded');
        var extraPhotos = d.coverPhoto ? d.photoCount - 1 : 0;
        var thumb = '<div class="thumb">' + (d.coverPhoto
            ? '<img src="' + escapeHtml(d.coverPhoto) + '" alt="" loading="lazy" onerror="this.outerHTML=\'<div class=&quot;thumb-placeholder&quot;></div>\'">'
            : '<div class="thumb-placeholder">' + icon('image-off') + '</div>') +
            (extraPhotos > 0 ? '<span class="photo-count">+' + extraPhotos + '</span>' : '') + '</div>';
        return '<div class="listing-card' + (selectedListing && selectedListing.url === d.url ? ' active' : '') + '" data-url="' + escapeHtml(d.url) + '">' + thumb +
            '<div class="info">' +
            '<div class="price-row"><span class="price">' + formatRupees(d.totalCost) + '</span>' +
            (d.maintenance > 0 ? '<span class="maintenance-note">incl. ' + formatRupeesShort(d.maintenance) + ' maint.</span>' : '') + '</div>' +
            '<div class="name">' + escapeHtml(d.society) + '</div>' +
            '<div class="details-line">' + bhkLabel(d) + ' · ' + (FURNISHING_LABELS[d.furnishing] ? FURNISHING_LABELS[d.furnishing] + ' · ' : '') + d.sqft.toLocaleString() + ' sqft</div>' +
            (d.availableFrom ? '<div class="details-line secondary">Avail. ' + escapeHtml(d.availableFrom) + '</div>' : '') +
            commuteLineHtml(d) +
            '<div class="tags">' + (d.source !== 'nb' && SOURCE_LABELS[d.source] ? '<span class="tag">' + SOURCE_LABELS[d.source] + '</span>' : '') + (d.isPetFriendly ? '<span class="tag positive">' + icon('paw-print') + 'Pets OK</span>' : '') +
            tagsHtml(tags) + '</div>' +
            '</div><div class="card-corner">' + scorePillHtml(d) +
            '<button class="star-toggle' + (starred ? ' on' : '') + '" aria-label="' + (starred ? 'Unstar' : 'Star') + '">' + icon('star') + '</button></div></div>';
    }).join('');
}
// Pan to listing d, then pin its detail card next to the marker.
function focusListing(d) {
    var target = L.latLng(d.mapLat, d.mapLng);
    map.once('moveend', function() {
        var point = map.latLngToContainerPoint(target), rect = map.getContainer().getBoundingClientRect();
        selectListing(d, {originalEvent: {clientX: rect.left + point.x, clientY: rect.top + point.y}});
    });
    map.setView(target, Math.max(map.getZoom(), 15));
}
// List cards: the star toggles, Ctrl/Cmd-click opens the listing, anywhere else focuses it on the map.
byId('list').addEventListener('click', function(e) {
    var card = e.target.closest('.listing-card');
    if (!card) return;
    if (e.target.closest('.star-toggle')) return toggleStar(card.dataset.url);
    if (e.metaKey || e.ctrlKey) return window.open(card.dataset.url, '_blank');
    var d = filteredListings.find(function(x) { return x.url === card.dataset.url; });
    if (d) focusListing(d);
});

map.on('click', function(e) {
    if (e.originalEvent.handledByMarker) return;
    boxSelection = [];
    deselectListing();
});

