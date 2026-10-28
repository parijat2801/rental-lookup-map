// ===========================================================================
// Scoring. Every score depends only on the listing itself, so it is computed
// once at load into d.scores; filters and colour tiers are applied per render.
// Quality point weights are user-editable (localStorage) so rankings can be
// personalised; value is derived from quality / cost.
// ===========================================================================
// Full points up to fullUntil metres, then linearly down to 0 at zeroAt.
function linearFalloff(metres, fullUntil, zeroAt, points) {
    if (metres == null || metres >= zeroAt) return 0;
    if (metres < fullUntil) return points;
    return points * (1 - (metres - fullUntil) / (zeroAt - fullUntil));
}
// Default quality points. Keys match the editable rows in the quality-weights dialog.
var DEFAULT_QUALITY_POINTS = {
    goodFacing: 7,
    balconyEach: 5,
    balconyCap: 15,
    ageNew: 8,
    ageMid: 4,
    ageOld: 1,
    powerBackup: 8,
    security: 3,
    gated: 10,
    fireSafety: 2,
    pool: 5,
    gym: 10,
    clubhouse: 5,
    park: 9,
    intercom: 2,
    carParking: 3,
    transitHigh: 8,
    transitMid: 5,
    lifestyleHigh: 12,
    lifestyleMid: 6,
    reliableWater: 7,
    negotiable: 3,
    photosMany: 3,
    photosSome: 2,
    brandedBuilder: 4,
    sqftLarge: 3,
    sqftMid: 2,
    cupboards: 5,
};
var QUALITY_POINTS_KEY = "rental_quality_points";
var qualityPoints = Object.assign({}, DEFAULT_QUALITY_POINTS);

function loadQualityPoints() {
    try {
        var saved = JSON.parse(localStorage.getItem(QUALITY_POINTS_KEY));
        if (!saved || typeof saved !== "object") return;
        for (var key in DEFAULT_QUALITY_POINTS) {
            var n = +saved[key];
            if (isFinite(n))
                qualityPoints[key] = Math.max(-99, Math.min(99, Math.round(n)));
        }
    } catch (e) {}
}
function saveQualityPoints() {
    try {
        localStorage.setItem(QUALITY_POINTS_KEY, JSON.stringify(qualityPoints));
    } catch (e) {}
}
function qualityPointsCustomized() {
    for (var key in DEFAULT_QUALITY_POINTS) {
        if (qualityPoints[key] !== DEFAULT_QUALITY_POINTS[key]) return true;
    }
    return false;
}
function resetQualityPoints() {
    qualityPoints = Object.assign({}, DEFAULT_QUALITY_POINTS);
    try {
        localStorage.removeItem(QUALITY_POINTS_KEY);
    } catch (e) {}
}
loadQualityPoints();

// Quality: general desirability (light, age, amenities, platform scores, ...).
function qualityScore(d) {
    var p = qualityPoints,
        s = 0;
    if (GOOD_FACING.includes(d.facing)) s += p.goodFacing;
    if (d.balconies > 0) s += Math.min(d.balconies * p.balconyEach, p.balconyCap);
    if (d.ageYears <= 3) s += p.ageNew;
    else if (d.ageYears <= 7) s += p.ageMid;
    else if (d.ageYears <= 15) s += p.ageOld;
    if (d.hasPowerBackup) s += p.powerBackup;
    if (d.hasSecurity) s += p.security;
    if (d.isGated) s += p.gated;
    if (d.hasFireSafety) s += p.fireSafety;
    if (d.hasPool) s += p.pool;
    if (d.hasGym) s += p.gym;
    if (d.hasClubhouse) s += p.clubhouse;
    if (d.hasPark) s += p.park;
    if (d.hasIntercom) s += p.intercom;
    if (CAR_PARKING_TYPES.includes(d.parking)) s += p.carParking;
    if (d.nbTransit >= 8) s += p.transitHigh;
    else if (d.nbTransit >= 7) s += p.transitMid;
    if (d.nbLifestyle >= 8) s += p.lifestyleHigh;
    else if (d.nbLifestyle >= 6) s += p.lifestyleMid;
    if (RELIABLE_WATER.includes(d.waterSupply)) s += p.reliableWater;
    if (d.isNegotiable) s += p.negotiable;
    if (d.photoCount >= 10) s += p.photosMany;
    else if (d.photoCount >= 5) s += p.photosSome;
    if (d.isBrandedBuilder) s += p.brandedBuilder;
    if (d.sqft >= 1500) s += p.sqftLarge;
    else if (d.sqft >= 1200) s += p.sqftMid;
    // if (d.isPetFriendly) s += 10;
    if (d.cupboards >= 5) s += p.cupboards;
    return s;
}
// Vibe: greenery near the listing. Distances are to neighbourhood-scale OSM parks /
// woods / lakes only (tiny gardens and scrub are filtered out at build time).
// Society "park" amenity only counts in gated communities — the flag is noisy otherwise.
function vibeScore(d) {
    return Math.round(
        linearFalloff(d.parkM, 250, 800, 45) +
            linearFalloff(d.woodsM, 300, 1000, 30) +
            linearFalloff(d.lakeM, 600, 1800, 20) +
            (d.hasPark && d.isGated ? 5 : 0),
    );
}
function applyQualityScores(d) {
    var quality = qualityScore(d);
    d.scores.quality = quality;
    d.scores.value =
        d.totalCost > 0 ? Math.round((quality / d.totalCost) * 100000) : 0;
}
function computeScores(d) {
    try {
        d.scores = { quality: 0, value: 0, commute: 0, vibe: vibeScore(d) };
        applyQualityScores(d);
    } catch (e) {
        d.scores = { quality: 0, value: 0, commute: 0, vibe: 0 };
    }
}
// Re-rank after the user edits quality point weights. Preserves commute scores.
function recomputeQualityScores() {
    LISTINGS.forEach(function (d) {
        try {
            applyQualityScores(d);
        } catch (e) {
            d.scores.quality = 0;
            d.scores.value = 0;
        }
    });
    // Economy colours are percentiles of the dataset; wipe the cache so they refresh.
    if (typeof SCORE_TIERS !== "undefined") delete SCORE_TIERS.value;
    if (typeof refreshMap === "function") refreshMap();
}
LISTINGS.forEach(computeScores);
