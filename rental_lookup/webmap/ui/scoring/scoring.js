// ===========================================================================
// Scoring. Every score depends only on the listing itself, so it is computed
// once at load into d.scores; filters and colour tiers are applied per render.
// ===========================================================================
// Quality: general desirability (light, age, amenities, platform scores, ...).
function qualityScore(d) {
    var s = 0;
    if (GOOD_FACING.includes(d.facing)) s += 7;
    if (d.balconies > 0) s += Math.min(d.balconies * 5, 15);
    if (d.ageYears <= 3) s += 8; else if (d.ageYears <= 7) s += 4; else if (d.ageYears <= 15) s += 1;
    if (d.hasPowerBackup) s += 8; if (d.hasSecurity) s += 3; if (d.isGated) s += 10; if (d.hasFireSafety) s += 2;
    if (d.hasPool) s += 5; if (d.hasGym) s += 10; if (d.hasClubhouse) s += 5;
    if (d.hasPark) s += 9; if (d.hasIntercom) s += 2;
    if (CAR_PARKING_TYPES.includes(d.parking)) s += 3;
    if (d.nbTransit >= 8) s += 8; else if (d.nbTransit >= 7) s += 5;
    if (d.nbLifestyle >= 8) s += 12; else if (d.nbLifestyle >= 6) s += 6;
    if (RELIABLE_WATER.includes(d.waterSupply)) s += 7;
    if (d.isNegotiable) s += 3;
    if (d.photoCount >= 10) s += 3; else if (d.photoCount >= 5) s += 2;
    if (d.isBrandedBuilder) s += 4;
    if (d.sqft >= 1500) s += 3; else if (d.sqft >= 1200) s += 2;
    // if (d.isPetFriendly) s += 10;
    if (d.cupboards >= 5) s += 5;
    return s;
}
function computeScores(d) {
    try {
        var quality = qualityScore(d);
        d.scores = {
            quality: quality,
            value: d.totalCost > 0 ? Math.round(quality / d.totalCost * 100000) : 0,
            commute: 0  // depends on the places of interest; see refreshCommuteScores()
        };
    } catch (e) {
        d.scores = {quality: 0, value: 0, commute: 0};
    }
}
LISTINGS.forEach(computeScores);
