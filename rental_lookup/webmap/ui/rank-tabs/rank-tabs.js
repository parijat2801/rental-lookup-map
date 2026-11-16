// Rank modes: which d.scores entry drives the min-score slider, colours and sort order.
var RANK_MODES = {
    quality: {
        score: "quality",
        label: "score",
        sortedBy: "quality",
        sort: function (a, b) {
            return (
                b.scores.quality - a.scores.quality || a.totalCost - b.totalCost
            );
        },
    },
    economy: {
        score: "value",
        label: "economy",
        sortedBy: "economy",
        sort: function (a, b) {
            return (
                b.scores.value - a.scores.value ||
                b.scores.quality - a.scores.quality
            );
        },
    },
    vibe: {
        score: "vibe",
        label: "vibe",
        sortedBy: "greenery",
        sort: function (a, b) {
            return (
                b.scores.vibe - a.scores.vibe ||
                (a.parkM != null ? a.parkM : 1e9) -
                    (b.parkM != null ? b.parkM : 1e9) ||
                a.totalCost - b.totalCost
            );
        },
    },
    commute: {
        score: "commute",
        label: "commute score",
        sortedBy: "commute",
        sort: function (a, b) {
            return (
                b.scores.commute - a.scores.commute ||
                a.commute.worstMinutes - b.commute.worstMinutes ||
                a.commute.averageMinutes - b.commute.averageMinutes ||
                a.totalCost - b.totalCost
            );
        },
    },
};
var activeRankMode = "quality";
function setRankMode(mode) {
    activeRankMode = mode;
    for (var m in RANK_MODES)
        byId("rank-" + m).classList.toggle("on", m === mode);
    byId("areas-panel").hidden = mode !== "commute";
    refreshMap();
}
// The Commute tab ranks by quality until at least one place of interest is set.
function effectiveRankMode() {
    return activeRankMode === "commute" && !areasOfInterest.length
        ? "quality"
        : activeRankMode;
}
