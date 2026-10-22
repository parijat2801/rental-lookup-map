// --- Drive times from OSRM ------------------------------------------------------------
// One table request routes up to 100 - areas unique listing coordinates to every area,
// spaced about a second apart (OSRM demo server policy). Filtered listings in view go first.
var routingTimer = null, routingInFlight = false, lastRoutingRequest = 0, routingFailures = 0;
function routingWork() {
    var bounds = map.getBounds(), inView = [], elsewhere = [], seen = {}, total = 0;
    filteredListings.forEach(function(d) {
        var key = coordKey(d.lat, d.lng);
        if (seen[key]) return;
        seen[key] = true;
        total++;
        if (areasOfInterest.every(function(a) { return driveCache[key + '|' + a.id]; })) return;
        (bounds.contains([d.lat, d.lng]) ? inView : elsewhere).push({key: key, lat: d.lat, lng: d.lng});
    });
    return {pending: inView.concat(elsewhere), total: total};
}
function scheduleRouting() {
    updateAreasStatus();
    if (!areasOfInterest.length || routingTimer || routingInFlight || routingFailures >= OSRM_MAX_FAILURES) return;
    var gap = OSRM_REQUEST_GAP_MS * Math.pow(2, routingFailures);
    routingTimer = setTimeout(runRoutingBatch, Math.max(0, gap - (Date.now() - lastRoutingRequest)));
}
function runRoutingBatch() {
    routingTimer = null;
    var pending = routingWork().pending;
    if (!areasOfInterest.length || !pending.length) return updateAreasStatus();
    var areas = areasOfInterest.slice(), batch = pending.slice(0, OSRM_MAX_COORDINATES - areas.length);
    var points = batch.concat(areas).map(function(p) { return p.lng.toFixed(5) + ',' + p.lat.toFixed(5); }).join(';');
    var sources = batch.map(function(_, i) { return i; }).join(';');
    var destinations = areas.map(function(_, j) { return batch.length + j; }).join(';');
    routingInFlight = true;
    lastRoutingRequest = Date.now();
    fetch(OSRM_TABLE_URL + points + '?sources=' + sources + '&destinations=' + destinations + '&annotations=duration,distance')
        .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function(body) {
            if (body.code !== 'Ok') throw new Error(body.code);
            batch.forEach(function(p, i) {
                areas.forEach(function(area, j) {
                    if (areasOfInterest.indexOf(area) < 0) return;  // removed while the request was in flight
                    var seconds = body.durations[i][j], metres = body.distances[i][j];
                    driveCache[p.key + '|' + area.id] = seconds == null ? [-1, -1] : [Math.round(seconds), Math.round(metres)];
                });
            });
            routingFailures = 0;
            saveDriveCacheSoon();
            refreshAfterRouting();
        })
        .catch(function() { routingFailures++; })
        .then(function() { routingInFlight = false; scheduleRouting(); });
}
function updateAreasStatus() {
    var status = byId('areas-status');
    if (!areasOfInterest.length) {
        status.textContent = '';
        return;
    }
    var work = routingWork(), routed = work.total - work.pending.length;
    // Only while routing (or on failure) — idle success copy steals listing space.
    if (!work.pending.length) status.textContent = '';
    else if (routingFailures >= OSRM_MAX_FAILURES) status.textContent = 'Routing server unavailable · using estimated drive times (~)';
    else status.textContent = 'Routing ' + routed.toLocaleString() + ' / ' + work.total.toLocaleString() + '…';
}

