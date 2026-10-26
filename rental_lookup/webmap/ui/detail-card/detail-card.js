// ===========================================================================
// Detail card: label helpers, then filling, positioning and pinning the card
// ===========================================================================
function amenityLabels(d) {
    var labels = [];
    if (d.hasPool) labels.push("Pool");
    if (d.hasGym) labels.push("Gym");
    if (d.hasClubhouse) labels.push("Clubhouse");
    if (d.isGated) labels.push("Gated");
    if (d.hasSecurity) labels.push("Security");
    if (d.hasPowerBackup) labels.push("Power backup");
    return labels;
}
function tagsHtml(labels, className) {
    return labels
        .map(function (label) {
            return (
                '<span class="tag ' +
                (className || "") +
                '">' +
                label +
                "</span>"
            );
        })
        .join("");
}
function bhkLabel(d) {
    return escapeHtml((d.bhk || "").replace("BHK", "")) + " BHK";
}
var FURNISHING_LABELS = {
    FULL: "Furnished",
    SEMI: "Semi-furnished",
    NONE: "Unfurnished",
};
var SOURCE_LABELS = { nb: "NoBroker", mb: "MagicBricks", "9a": "99acres", pa: "Property Angel" };
function furnishingLabel(d) {
    return FURNISHING_LABELS[d.furnishing] || "Furnishing unknown";
}
function floorLabel(d) {
    return "Floor " + d.floor + (d.totalFloors ? " of " + d.totalFloors : "");
}
// Shared/approximate coordinates are unreliable, so those listings search Google Maps by name instead.
function googleMapsLinkHtml(d, labelHtml) {
    var query = d.isStacked
        ? [d.society, d.locality].filter(Boolean).join(", ")
        : d.lat + "," + d.lng;
    return (
        '<a class="maps-link" href="https://www.google.com/maps/search/?api=1&query=' +
        encodeURIComponent(query) +
        '" target="_blank" rel="noopener" title="Open in Google Maps">' +
        icon("map-pin") +
        labelHtml +
        "</a>"
    );
}
function ageLabel(d) {
    return d.ageYears >= 99
        ? "Age unknown"
        : d.ageYears <= 0
          ? "New"
          : d.ageYears + " yr old";
}
// How long the listing has been posted (`daysAgo`); used in the detail-card eyebrow.
function listingAgeLabel(d) {
    if (d.daysAgo == null || d.daysAgo < 0) return "";
    if (d.daysAgo === 0) return "Today";
    if (d.daysAgo === 1) return "1 day ago";
    return d.daysAgo + " days ago";
}
function ratingLabel(value) {
    return value == null ? "-" : value;
} // null = NoBroker has no rating

// Fill the detail card for listing `d` and position it near the mouse event `e`.
// With e = null the card is only refreshed in place (photo position kept).
function showDetailCard(e, d) {
    if (e) {
        cardPhotos =
            d.photos && d.photos.length > 0
                ? d.photos
                : d.coverPhoto
                  ? [d.coverPhoto]
                  : [];
        cardPhotoIndex = 0;
        var hasSeveralPhotos = cardPhotos.length > 1;
        byId("card-photo").src = cardPhotos[0] || "";
        byId("card-photo").style.display = d.coverPhoto ? "block" : "none";
        byId("card-photo-counter").textContent = hasSeveralPhotos
            ? "1 / " + cardPhotos.length
            : "";
        byId("card-carousel")
            .querySelectorAll(".nav")
            .forEach(function (b) {
                b.style.display = hasSeveralPhotos ? "flex" : "none";
            });
    }
    var badges = [];
    if (isStarred(d.url))
        badges.push('<span class="tag">' + icon("star") + "Starred</span>");
    if (d.isDelisted) badges.push('<span class="tag warning">Delisted</span>');
    else if (d.isFakeLocation)
        badges.push('<span class="tag warning">Location unreliable</span>');
    if (d.isPetFriendly)
        badges.push(
            '<span class="tag">' + icon("paw-print") + "Pet friendly</span>",
        );
    byId("card-badges").innerHTML = badges.join("");

    var eyebrow = [
        d.isDelisted ? "" : "#" + d.rank,
        SOURCE_LABELS[d.source] || "NoBroker",
        listingAgeLabel(d),
    ];
    byId("card-eyebrow").innerHTML =
        scorePillHtml(d) +
        '<span class="label">' +
        eyebrow.filter(Boolean).join(" · ") +
        "</span>";
    byId("card-title").textContent = d.society || "Unnamed society";
    byId("card-location").innerHTML = googleMapsLinkHtml(
        d,
        escapeHtml((d.locality || "").substring(0, 60)),
    );
    byId("card-price").innerHTML =
        "<b>" +
        formatRupees(d.totalCost) +
        "</b> /month" +
        (d.maintenance > 0
            ? ' <span class="muted">· ' +
              formatRupees(d.rent) +
              " rent + " +
              formatRupees(d.maintenance) +
              " maintenance</span>"
            : "") +
        (d.deposit > 0
            ? '<br><span class="deposit">' +
              formatRupees(d.deposit) +
              " deposit</span>"
            : "");

    var facts = [
        ["bed-double", bhkLabel(d)],
        ["sofa", furnishingLabel(d)],
        ["ruler", d.sqft.toLocaleString() + " sqft"],
        [
            "compass",
            d.facing ? escapeHtml(d.facing) + " facing" : "Facing unknown",
        ],
        [
            "fence",
            (d.balconies >= 0 ? d.balconies : "?") +
                " balcon" +
                (d.balconies === 1 ? "y" : "ies"),
        ],
        ["building-2", floorLabel(d)],
        ["calendar", ageLabel(d)],
    ];
    if (d.cupboards > 0) facts.push(["archive", d.cupboards + " cupboards"]);
    if (d.availableFrom)
        facts.push(["calendar-check", "From " + escapeHtml(d.availableFrom)]);
    var amenities = amenityLabels(d);
    byId("card-details").innerHTML =
        '<div class="facts">' +
        facts
            .map(function (f) {
                return "<span>" + icon(f[0]) + f[1] + "</span>";
            })
            .join("") +
        "</div>" +
        (amenities.length
            ? '<div class="tags">' + tagsHtml(amenities, "positive") + "</div>"
            : "") +
        greeneryHtml(d) +
        commuteHtml(d) +
        samePropertyHtml(d) +
        '<div class="meta">' +
        [
            d.street ? escapeHtml(d.street) : "",
            d.source === "nb"
                ? "NoBroker transit " +
                  ratingLabel(d.nbTransit) +
                  " · lifestyle " +
                  ratingLabel(d.nbLifestyle)
                : "",
            d.propertyCode ? escapeHtml(d.propertyCode) : "",
        ]
            .filter(Boolean)
            .join(" · ") +
        "</div>";

    var isPinned = selectedListing && selectedListing.url === d.url;
    var actionsHtml = isPinned
        ? '<div class="actions">' +
          '<button class="' +
          (isStarred(d.url) ? "on" : "") +
          '" onclick="toggleStar(selectedListing.url)">' +
          icon("star") +
          (isStarred(d.url) ? "Starred" : "Star") +
          "</button>" +
          '<button onclick="toggleDismiss(selectedListing.url);deselectListing();">' +
          icon("eye-off") +
          "Dismiss</button>" +
          "<button onclick=\"window.open(selectedListing.url,'_blank');\">" +
          icon("external-link") +
          "Open</button></div>"
        : "";
    byId("card-extras").innerHTML = actionsHtml;

    if (!e) {
        rememberDetailCardHeight();
        return;
    }
    var wasHidden = detailCard.style.display !== "block";
    detailCard.style.display = "block";
    detailCard.style.visibility = "";
    var anchor = selectedListing === d ? markerScreenPoint(d) : null;
    placeDetailCard(
        anchor ? anchor.x : e.originalEvent.clientX,
        anchor ? anchor.y : e.originalEvent.clientY,
    );
    if (wasHidden || detailCard.dataset.url !== d.url)
        animateIn(detailCard, { y: 6, scale: 0.98 }, 0.2);
    detailCard.dataset.url = d.url;
}
// Other matching listings at the same spot as d; clicking one (on a pinned card) switches to it.
function samePropertyHtml(d) {
    if (!d.propertyKey) return "";
    var others = filteredListings.filter(function (x) {
        return x.propertyKey === d.propertyKey && x !== d;
    });
    if (!others.length) return "";
    return (
        '<div class="same-property"><div class="label">' +
        others.length +
        " more in this property</div>" +
        others
            .map(function (x) {
                return (
                    '<button class="same-property-row" data-url="' +
                    escapeHtml(x.url) +
                    '">' +
                    "<span>" +
                    bhkLabel(x) +
                    " · " +
                    x.sqft.toLocaleString() +
                    " sqft · " +
                    floorLabel(x) +
                    (x.isDelisted ? " · Delisted" : "") +
                    "</span><b>" +
                    formatRupeesShort(x.totalCost) +
                    "</b></button>"
                );
            })
            .join("") +
        "</div>"
    );
}
detailCard.addEventListener("click", function (e) {
    var row = e.target.closest(".same-property-row");
    if (!row) return;
    var d = filteredListings.find(function (x) {
        return x.url === row.dataset.url;
    });
    if (d) selectListing(d, {});
});
// Keep the card's vertical centre fixed when Vibe/Commute folds open or close.
var detailCardHeight = 0;
function rememberDetailCardHeight() {
    detailCardHeight = detailCard.offsetHeight;
}
// toggle does not bubble; capture so we see fold open/close on the card.
detailCard.addEventListener(
    "toggle",
    function (e) {
        if (!e.target.classList.contains("card-fold")) return;
        var oldHeight = detailCardHeight || detailCard.offsetHeight;
        var newHeight = detailCard.offsetHeight;
        if (newHeight === oldHeight) return;
        var top = parseFloat(detailCard.style.top) || 0;
        var center = top + oldHeight / 2;
        var nextTop = Math.max(
            10,
            Math.min(center - newHeight / 2, window.innerHeight - newHeight - 10),
        );
        if (MOTION) {
            gsap.killTweensOf(detailCard, "top");
            gsap.to(detailCard, {
                top: nextTop,
                duration: 0.2,
                ease: "power2.out",
            });
        } else {
            detailCard.style.top = nextTop + "px";
        }
        detailCardHeight = newHeight;
    },
    true,
);
// Card position for an anchor at viewport (x, y): beside it, on screen and clear of the sidebar.
function cardPosition(anchorX, anchorY) {
    var x = anchorX + 20,
        y = anchorY - 120;
    if (x + 350 > window.innerWidth) x = anchorX - 360;
    x = Math.max(x, sidebarOffset() + 10);
    y = Math.max(
        10,
        Math.min(y, window.innerHeight - detailCard.offsetHeight - 10),
    );
    return { left: x, top: y };
}
function placeDetailCard(anchorX, anchorY) {
    var pos = cardPosition(anchorX, anchorY);
    if (MOTION) gsap.killTweensOf(detailCard, "left,top");
    detailCard.style.left = pos.left + "px";
    detailCard.style.top = pos.top + "px";
    rememberDetailCardHeight();
}
// Viewport position of listing d's marker, optionally at a future map center/zoom.
function markerScreenPoint(d, center, zoom) {
    var point = center
        ? map
              .project([d.mapLat, d.mapLng], zoom)
              .subtract(map.project(center, zoom))
              .add(map.getSize().divideBy(2))
        : map.latLngToContainerPoint([d.mapLat, d.mapLng]);
    var rect = map.getContainer().getBoundingClientRect(),
        size = map.getSize();
    return {
        x: rect.left + point.x,
        y: rect.top + point.y,
        inView:
            point.x >= 0 &&
            point.y >= 0 &&
            point.x <= size.x &&
            point.y <= size.y,
    };
}
// A pinned card follows its marker while the map pans and zooms, hiding while the marker is off screen.
function pinnedCardShown() {
    return selectedListing && detailCard.style.display === "block";
}
function followSelectedListing() {
    if (!pinnedCardShown()) return;
    var point = markerScreenPoint(selectedListing);
    detailCard.style.visibility = point.inView ? "" : "hidden";
    if (point.inView) placeDetailCard(point.x, point.y);
}
map.on("move zoomend resize", followSelectedListing);
map.on("zoomanim", function (e) {
    if (!pinnedCardShown()) return;
    var point = markerScreenPoint(selectedListing, e.center, e.zoom),
        pos = cardPosition(point.x, point.y);
    detailCard.style.visibility = point.inView ? "" : "hidden";
    if (MOTION)
        gsap.to(detailCard, {
            left: pos.left,
            top: pos.top,
            duration: 0.25,
            ease: "power2.out",
        });
    else {
        detailCard.style.left = pos.left + "px";
        detailCard.style.top = pos.top + "px";
    }
});
