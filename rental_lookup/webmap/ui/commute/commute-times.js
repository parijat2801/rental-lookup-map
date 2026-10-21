// --- Commute per listing -----------------------------------------------------------
function commutePoints(minutes) {
    if (minutes <= COMMUTE_FULL_POINTS_MIN) return 100;
    if (minutes >= COMMUTE_ZERO_POINTS_MIN) return 0;
    return 100 * (COMMUTE_ZERO_POINTS_MIN - minutes) / (COMMUTE_ZERO_POINTS_MIN - COMMUTE_FULL_POINTS_MIN);
}
function updateCommute(d) {
    if (!areasOfInterest.length) { d.commute = null; d.scores.commute = 0; return; }
    if (!d.nearStations) d.nearStations = nearestStations(d.lat, d.lng);
    var key = coordKey(d.lat, d.lng), totalMinutes = 0, worstMinutes = 0;
    var perArea = areasOfInterest.map(function(area) {
        var km = haversineKm(d.lat, d.lng, area.lat, area.lng);
        var route = driveCache[key + '|' + area.id], routed = !!route && route[0] >= 0;
        var drive = routed ? route[0] / 60 * DRIVE_TRAFFIC_FACTOR : estimateDriveMinutes(km);
        var metro = metroTrip(d.nearStations, area.stations);
        var bestMode = commuteMode === 'drive' || !metro ? 'drive'
            : commuteMode === 'metro' ? 'metro' : metro.minutes < drive ? 'metro' : 'drive';
        var best = bestMode === 'metro' ? metro.minutes : drive;
        totalMinutes += best;
        worstMinutes = Math.max(worstMinutes, best);
        return {area: area, drive: drive, driveKm: routed ? route[1] / 1000 : km * ROAD_DETOUR, estimated: !routed,
                metro: metro, metroUseful: !!metro && metro.minutes < drive, best: best, bestMode: bestMode};
    });
    // AND over the areas: a listing is only as good as its longest commute, so being next to one
    // area can't make up for being far from another.
    var score = Math.round(commutePoints(worstMinutes));
    d.commute = {perArea: perArea, score: score, averageMinutes: totalMinutes / perArea.length, worstMinutes: worstMinutes};
    d.scores.commute = score;
}
function refreshCommuteScores() { LISTINGS.forEach(updateCommute); }

// After new drive times arrive: re-rank at most every few seconds so routing doesn't make the map stutter.
var lastRoutingRefresh = 0, routingRefreshTimer = null;
function refreshAfterRouting() {
    refreshCommuteScores();
    clearTimeout(routingRefreshTimer);
    var wait = 3000 - (Date.now() - lastRoutingRefresh);
    if (activeRankMode === 'commute' && wait > 0) { routingRefreshTimer = setTimeout(refreshAfterRouting, wait); return; }
    lastRoutingRefresh = Date.now();
    if (activeRankMode === 'commute') refreshMap();
    else if (selectedListing) showDetailCard(null, selectedListing);
}

