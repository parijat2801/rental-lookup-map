// --- Commute in the detail card and list ----------------------------------------------
function formatMinutes(minutes) {
    return Math.round(minutes) + " min";
}
function commuteHtml(d) {
    if (!d.commute) return "";
    function time(iconName, minutes, title) {
        return (
            '<span class="commute-time" title="' +
            escapeHtml(title) +
            '">' +
            icon(iconName) +
            minutes +
            "</span>"
        );
    }
    return (
        '<div class="commute">' +
        d.commute.perArea
            .map(function (c) {
                var drive = time(
                    "car",
                    (c.estimated ? "~" : "") + formatMinutes(c.drive),
                    "Drive, " +
                        c.driveKm.toFixed(1) +
                        " km" +
                        (c.estimated ? " (estimate)" : ""),
                );
                var metro = c.metro
                    ? time(
                          "train-front",
                          formatMinutes(c.metro.minutes),
                          "Metro: " +
                              c.metro.fromStation +
                              " → " +
                              c.metro.toStation +
                              (c.metro.transfers
                                  ? ", " +
                                    c.metro.transfers +
                                    (c.metro.transfers === 1
                                        ? " change"
                                        : " changes")
                                  : ""),
                      )
                    : "<span></span>";
                return (
                    '<div class="commute-row"><span class="area-label">' +
                    icon("flag") +
                    "<span>" +
                    escapeHtml(c.area.name) +
                    "</span></span>" +
                    drive +
                    metro +
                    "</div>"
                );
            })
            .join("") +
        "</div>"
    );
}
function commuteLineHtml(d) {
    if (!d.commute || effectiveRankMode() !== "commute") return "";
    var perArea = d.commute.perArea,
        modes = perArea.map(function (c) {
            return c.bestMode;
        });
    var modeIcon = modes.every(function (m) {
        return m === "metro";
    })
        ? "train-front"
        : modes.every(function (m) {
                return m === "drive";
            })
          ? "car"
          : "route";
    var estimated = perArea.some(function (c) {
        return c.bestMode === "drive" && c.estimated;
    })
        ? "~"
        : "";
    var text =
        perArea.length === 1
            ? estimated +
              formatMinutes(perArea[0].best) +
              " to " +
              escapeHtml(perArea[0].area.name)
            : "All " +
              perArea.length +
              " within " +
              estimated +
              formatMinutes(d.commute.worstMinutes) +
              " · avg " +
              formatMinutes(d.commute.averageMinutes);
    return (
        '<div class="details-line secondary" style="display:flex;align-items:center;gap:4px">' +
        icon(modeIcon).replace(
            'class="icon"',
            'class="icon" style="width:12px;height:12px"',
        ) +
        text +
        "</div>"
    );
}

renderAreas();
refreshCommuteScores();
