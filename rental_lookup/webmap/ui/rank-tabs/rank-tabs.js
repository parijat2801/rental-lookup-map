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
    value: {
        score: "value",
        label: "value",
        sortedBy: "value for money",
        sort: function (a, b) {
            return (
                b.scores.value - a.scores.value ||
                b.scores.quality - a.scores.quality
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
