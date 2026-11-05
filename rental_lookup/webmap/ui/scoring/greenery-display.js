// Greenery distances for the Vibe rank mode (detail card + sidebar list).
function formatMetres(metres) {
    if (metres == null) return null;
    return metres < 1000
        ? Math.round(metres) + " m"
        : (metres / 1000).toFixed(1).replace(/\.0$/, "") + " km";
}
function greeneryParts(d) {
    var parts = [];
    if (d.parkM != null)
        parts.push({ icon: "trees", label: "Park", metres: d.parkM });
    if (d.woodsM != null)
        parts.push({ icon: "leaf", label: "Woods", metres: d.woodsM });
    if (d.lakeM != null)
        parts.push({ icon: "waves", label: "Lake", metres: d.lakeM });
    return parts;
}
// Detail card block: park / woods / lake distances (always, when present).
function greeneryHtml(d) {
    var parts = greeneryParts(d);
    if (!parts.length && !d.hasPark) return "";
    var rows = parts
        .map(function (p) {
            return (
                '<div class="greenery-row"><span class="area-label">' +
                icon(p.icon) +
                "<span>" +
                p.label +
                "</span></span>" +
                '<span class="greenery-dist">' +
                formatMetres(p.metres) +
                "</span></div>"
            );
        })
        .join("");
    if (d.hasPark && d.isGated) {
        rows +=
            '<div class="greenery-row"><span class="area-label">' +
            icon("flower-2") +
            "<span>Society park</span></span>" +
            '<span class="greenery-dist">On site</span></div>';
    }
    var nearest = parts.slice().sort(function (a, b) {
        return a.metres - b.metres;
    })[0];
    var hint = nearest
        ? nearest.label + " " + formatMetres(nearest.metres)
        : d.hasPark && d.isGated
          ? "Society park"
          : "";
    var open = effectiveRankMode() === "vibe" ? " open" : "";
    return (
        '<details class="card-fold greenery"' +
        open +
        ">" +
        "<summary>" +
        '<span class="fold-title">' +
        icon("trees") +
        "<span>Vibe</span></span>" +
        (hint ? '<span class="fold-hint">' + hint + "</span>" : "") +
        icon("chevron-down").replace('class="icon"', 'class="icon chevron"') +
        "</summary>" +
        '<div class="fold-body">' +
        rows +
        "</div></details>"
    );
}
// Sidebar list line, only while the Vibe tab is active.
function greeneryLineHtml(d) {
    if (effectiveRankMode() !== "vibe") return "";
    var parts = greeneryParts(d);
    if (!parts.length) {
        return d.hasPark && d.isGated
            ? '<div class="details-line secondary" style="display:flex;align-items:center;gap:4px">' +
                  icon("flower-2").replace(
                      'class="icon"',
                      'class="icon" style="width:12px;height:12px"',
                  ) +
                  "Society park</div>"
            : "";
    }
    parts.sort(function (a, b) {
        return a.metres - b.metres;
    });
    var text = parts
        .slice(0, 2)
        .map(function (p) {
            return p.label + " " + formatMetres(p.metres);
        })
        .join(" · ");
    return (
        '<div class="details-line secondary" style="display:flex;align-items:center;gap:4px">' +
        icon("trees").replace(
            'class="icon"',
            'class="icon" style="width:12px;height:12px"',
        ) +
        text +
        "</div>"
    );
}
