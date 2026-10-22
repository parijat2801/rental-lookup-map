// ===========================================================================
// Scoring. Every score depends only on the listing itself, so it is computed
// once at load into d.scores; filters and colour tiers are applied per render.
// ===========================================================================
// Quality: general desirability (light, age, amenities, platform scores, ...).
function qualityScore(d) {
    var s = 0;
    if (GOOD_FACING.includes(d.facing)) s += 10;
    if (d.balconies > 0) s += Math.min(d.balconies * 4, 12);
    if (d.ageYears <= 3) s += 10; else if (d.ageYears <= 7) s += 7; else if (d.ageYears <= 15) s += 3;
    if (d.hasPowerBackup) s += 5; if (d.hasSecurity) s += 5; if (d.isGated) s += 4; if (d.hasFireSafety) s += 2;
    if (d.hasPool) s += 8; if (d.hasGym) s += 5; if (d.hasClubhouse) s += 5;
    if (d.hasPark) s += 3; if (d.hasIntercom) s += 2;
    if (CAR_PARKING_TYPES.includes(d.parking)) s += 5;
    if (d.nbTransit >= 8) s += 5; else if (d.nbTransit >= 7) s += 3;
    if (d.nbLifestyle >= 8) s += 8; else if (d.nbLifestyle >= 6) s += 4;
    if (RELIABLE_WATER.includes(d.waterSupply)) s += 5;
    if (d.isNegotiable) s += 3;
    if (d.photoCount >= 10) s += 5; else if (d.photoCount >= 5) s += 3;
    if (d.isBrandedBuilder) s += 8;
    if (d.sqft >= 1500) s += 5; else if (d.sqft >= 1200) s += 3;
    if (d.isPetFriendly) s += 10;
    if (d.cupboards >= 5) s += 5;
    return s;
}
// Deal quality: amenities + brand + location + low deposit (squared / cost = deal score).
function dealQualityScore(d) {
    var q = 0;
    if (d.hasPool) q += 6; if (d.hasGym) q += 4; if (d.hasClubhouse) q += 4;
    if (d.isGated) q += 3; if (d.hasSecurity) q += 3;
    if (d.isBrandedBuilder) q += 8;
    if (d.nbLifestyle >= 8) q += 6; else if (d.nbLifestyle >= 6) q += 3;
    if (d.nbTransit >= 8) q += 4; else if (d.nbTransit >= 7) q += 2;
    if (d.sqft >= 1500) q += 5; else if (d.sqft >= 1200) q += 3;
    if (mentionsAnyArea(d, CENTRAL_AREAS)) q += 10;
    if (d.deposit > 0 && d.rent > 0 && d.deposit / d.rent <= 3) q += 5;
    return q;
}
function computeScores(d) {
    try {
        var quality = qualityScore(d), dealQuality = dealQualityScore(d);
        d.scores = {
            quality: quality,
            value: d.totalCost > 0 ? Math.round(quality / d.totalCost * 100000) : 0,
            dealQuality: dealQuality,
            deal: d.totalCost > 0 ? Math.round(dealQuality * dealQuality / d.totalCost * 1000) : 0,
            commute: 0  // depends on the places of interest; see refreshCommuteScores()
        };
    } catch (e) {
        d.scores = {quality: 0, value: 0, dealQuality: 0, deal: 0, commute: 0};
    }
}
LISTINGS.forEach(computeScores);

