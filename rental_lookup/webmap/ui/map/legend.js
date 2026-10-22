// Bottom-left legend: colour ramp always visible, marker styles on demand.
var legend = L.control({ position: "topright" });
legend.onAdd = function () {
    var container = L.DomUtil.create("details", "map-legend");
    container.innerHTML =
        '<summary><span>Low</span><span class="legend-ramp">' +
        TIER_COLORS.map(function (c) {
            return '<span style="background:' + c + '"></span>';
        }).join("") +
        '</span><span>High</span></summary><div class="legend-rows">' +
        "<div>" +
        starMarkIcon() +
        "Starred</div>" +
        '<div><span class="legend-dot" style="background:#d1d5db"></span>Delisted since last run</div>' +
        '<div><span class="legend-dot" style="opacity:.5;border:2px dashed #65a30d"></span>Shared / approximate location</div></div>';
    L.DomEvent.disableClickPropagation(container);
    return container;
};
