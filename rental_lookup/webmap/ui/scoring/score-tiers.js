// Commute bonus for the other rank modes. At 0 they ignore the areas of interest; to blend,
// raise the weight (0-1) and wrap their scores with this in computeScores / refreshCommuteScores.
var COMMUTE_BLEND_WEIGHT = 0;
function withCommuteBlend(score, d) {
    if (!COMMUTE_BLEND_WEIGHT || !d.commute) return score;
    return Math.round(score * (1 - COMMUTE_BLEND_WEIGHT + COMMUTE_BLEND_WEIGHT * d.commute.score / 100));
}

// Marker colours, red -> dark green. Quality uses fixed cut-offs; the other modes
// use percentiles (50/65/80/90/95th) of the currently visible listings.
var TIER_COLORS = ['#ef4444','#f97316','#eab308','#84cc16','#22c55e','#166534'];
var QUALITY_TIERS = [55, 65, 75, 85, 95];
// Score pills: [background, text] tints matching TIER_COLORS.
var TIER_PILLS = [['#fef2f2','#b91c1c'],['#fff7ed','#c2410c'],['#fefce8','#a16207'],['#f7fee7','#4d7c0f'],['#f0fdf4','#15803d'],['#dcfce7','#14532d']];
var currentTiers = QUALITY_TIERS;
function percentileTiers(values) {
    values = values.slice().sort(function(a, b) { return a - b; });
    var n = values.length;
    if (n < 5) return [0, 0, 0, 0, 0];
    return [0.5, 0.65, 0.8, 0.9, 0.95].map(function(p) { return values[Math.floor(n * p)]; });
}
function tierIndex(value, tiers) {
    var i = 0;
    while (i < tiers.length && value >= tiers[i]) i++;
    return i;
}
function tierColor(value, tiers) { return TIER_COLORS[tierIndex(value, tiers)]; }
// Pill showing listing d's score in the active rank mode, tinted like its marker.
function scorePillHtml(d) {
    var mode = RANK_MODES[effectiveRankMode()], value = d.scores[mode.score];
    if (d.isDelisted) return '<span class="score-badge" title="Delisted">' + value + '</span>';
    var i = tierIndex(value, currentTiers), pill = TIER_PILLS[i];
    return '<span class="score-badge" title="' + mode.label.charAt(0).toUpperCase() + mode.label.slice(1) + '" style="--pill-bg:' + pill[0] +
        ';--pill-fg:' + pill[1] + ';--pill-dot:' + TIER_COLORS[i] + '">' + value + '</span>';
}
legend.addTo(map);

