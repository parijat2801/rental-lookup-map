// --- Commute paths on the map ------------------------------------------------------------
// In commute mode the selected listing gets a route drawn from every place of interest, by
// whichever mode is quicker: the OSRM road route, or walk/auto legs around a metro ride.
var OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/";
var COMMUTE_PATH_DRAW_S = 1.4,
    COMMUTE_PATH_STAGGER_S = 0.2,
    COMMUTE_ROUTE_SLACK_KM = 0.03; // a divided road's far carriageway still counts as reaching a point
map.createPane("commutePaths");
map.getPane("commutePaths").style.zIndex = 350; // under the listing dots (overlay pane, 400)
var commutePathLayer = L.layerGroup().addTo(map),
    commutePathKey = "",
    commutePathTweens = [],
    commuteRouteCache = {}, // "coordKey|areaId" -> [[lat, lng], ...] road geometry
    commutePathListing = null,
    commutePathLines = [], // full geometry of every drawn segment, for keeping the card clear
    commutePathSamples = null; // {zoom, points}: pixel offsets along the paths from the listing

// Changes when the selection, the areas or a quickest mode changes; equal keys skip a redraw.
function commutePathSignature(d) {
    if (!d || !d.commute || effectiveRankMode() !== "commute") return "";
    return (
        d.url +
        "|" +
        d.commute.perArea
            .map(function (c) {
                return (
                    c.area.id +
                    ":" +
                    (c.bestMode === "metro"
                        ? c.metro.fromIndex + "-" + c.metro.toIndex
                        : "drive")
                );
            })
            .join(",")
    );
}
function syncCommutePaths() {
    if (!commutePathLayer) return; // renderMarkers can run before this file's top level
    var d = selectedListing,
        key = commutePathSignature(d);
    if (key === commutePathKey) return;
    commutePathKey = key;
    clearCommutePaths();
    if (!key) return;
    Promise.all(
        d.commute.perArea.map(function (c) {
            return commuteSegments(d, c);
        }),
    ).then(function (paths) {
        if (commutePathKey !== key) return;
        paths.forEach(function (segments, i) {
            drawCommutePath(segments, i * COMMUTE_PATH_STAGGER_S);
            segments.forEach(function (segment) {
                commutePathLines.push(segment.latlngs);
            });
        });
        commutePathListing = d;
        resettleSelectedCard();
    });
}
function clearCommutePaths() {
    commutePathTweens.forEach(function (tween) {
        tween.kill();
    });
    commutePathTweens = [];
    commutePathLayer.clearLayers();
    commutePathListing = null;
    commutePathLines = [];
    commutePathSamples = null;
}
function hasCommutePaths() {
    return !!commutePathListing && commutePathListing === selectedListing;
}
// How many sample points along the paths fall inside a box placed at (dx, dy) from the listing's dot.
function commutePathCoverage(dx, dy, width, height, zoom) {
    if (zoom == null) zoom = map.getZoom();
    if (!commutePathSamples || commutePathSamples.zoom !== zoom) {
        var origin = map.project(
                [commutePathListing.mapLat, commutePathListing.mapLng],
                zoom,
            ),
            points = [];
        commutePathLines.forEach(function (latlngs) {
            var pixels = latlngs.map(function (p) {
                return map.project(p, zoom).subtract(origin);
            });
            for (var i = 1; i < pixels.length; i++) {
                var a = pixels[i - 1],
                    b = pixels[i],
                    steps = Math.max(1, Math.ceil(a.distanceTo(b) / 8));
                for (var s = 0; s < steps; s++)
                    points.push(a.add(b.subtract(a).multiplyBy(s / steps)));
            }
        });
        commutePathSamples = { zoom: zoom, points: points };
    }
    var covered = 0;
    commutePathSamples.points.forEach(function (p) {
        if (p.x >= dx && p.x <= dx + width && p.y >= dy && p.y <= dy + height)
            covered++;
    });
    return covered;
}

// Ordered pieces of one trip, from the place of interest to the listing's dot:
// [{kind: "drive" | "leg" | "metro", latlngs, color?}]
function commuteSegments(d, c) {
    var start = [c.area.lat, c.area.lng],
        end = [d.mapLat, d.mapLng];
    if (c.bestMode === "metro") return Promise.resolve(metroSegments(c, start, end));
    var key = coordKey(d.lat, d.lng) + "|" + c.area.id;
    var cached = commuteRouteCache[key];
    var route = cached
        ? Promise.resolve(cached)
        : fetch(
              OSRM_ROUTE_URL +
                  [start, [d.lat, d.lng]]
                      .map(function (p) {
                          return p[1].toFixed(5) + "," + p[0].toFixed(5);
                      })
                      .join(";") +
                  "?overview=full&geometries=geojson",
          )
              .then(function (r) {
                  if (!r.ok) throw new Error("HTTP " + r.status);
                  return r.json();
              })
              .then(function (body) {
                  if (body.code !== "Ok" || !body.routes.length)
                      throw new Error(body.code);
                  return (commuteRouteCache[key] =
                      body.routes[0].geometry.coordinates.map(function (p) {
                          return [p[1], p[0]];
                      }));
              });
    return route
        .then(function (road) {
            if (road.length < 2) throw new Error("No route geometry");
            // Drop any loop past the ends (OSRM snaps to the nearest carriageway and U-turns
            // to reach it), then curve off the road ends so the legs don't meet it at a corner.
            var first = closestApproach(road, start, true);
            road = [first.point].concat(road.slice(first.index + 1));
            var last = closestApproach(road, end, false);
            road = road.slice(0, last.index + 1).concat([last.point]);
            return [
                {
                    kind: "leg",
                    latlngs: curveOffRoad(road, false, start).reverse(),
                },
                { kind: "drive", latlngs: road },
                { kind: "leg", latlngs: curveOffRoad(road, true, end) },
            ];
        })
        .catch(function () {
            return [{ kind: "drive", latlngs: [start, end] }];
        });
}
// Where a road first (or, fromEnd, last) passes within COMMUTE_ROUTE_SLACK_KM of its closest
// approach to target: {index of the segment's first point, point on the segment nearest target}.
function closestApproach(road, target, fromEnd) {
    var kx = Math.cos((target[0] * Math.PI) / 180),
        nearest = Infinity,
        hits = [];
    for (var i = 0; i < road.length - 1; i++) {
        var ax = (road[i][1] - target[1]) * kx,
            ay = road[i][0] - target[0],
            dx = (road[i + 1][1] - target[1]) * kx - ax,
            dy = road[i + 1][0] - target[0] - ay,
            lengthSq = dx * dx + dy * dy;
        var t = lengthSq
            ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / lengthSq))
            : 0;
        var km = 111.32 * Math.hypot(ax + dx * t, ay + dy * t);
        hits.push({ index: i, t: t, km: km });
        nearest = Math.min(nearest, km);
    }
    if (fromEnd) hits.reverse();
    var hit = hits.find(function (h) {
        return h.km <= nearest + COMMUTE_ROUTE_SLACK_KM;
    });
    var a = road[hit.index],
        b = road[hit.index + 1];
    return {
        index: hit.index,
        point: [a[0] + (b[0] - a[0]) * hit.t, a[1] + (b[1] - a[1]) * hit.t],
    };
}
// Quadratic Bézier from the road's last (or, atEnd false, first) point to target, leaving the
// road in the direction it was heading.
function curveOffRoad(road, atEnd, target) {
    var from = atEnd ? road[road.length - 1] : road[0],
        kx = Math.cos((from[0] * Math.PI) / 180),
        step = atEnd ? -1 : 1,
        behind = from;
    for (
        var i = atEnd ? road.length - 2 : 1;
        i >= 0 && i < road.length;
        i += step
    ) {
        behind = road[i];
        if (Math.hypot(behind[0] - from[0], (behind[1] - from[1]) * kx) > 1e-5)
            break;
    }
    var hx = (from[1] - behind[1]) * kx,
        hy = from[0] - behind[0],
        heading = Math.hypot(hx, hy),
        reach =
            Math.hypot((target[1] - from[1]) * kx, target[0] - from[0]) / 2;
    if (!heading || !reach) return [from, target];
    var control = [
        from[0] + (hy / heading) * reach,
        from[1] + (hx / heading) * (reach / kx),
    ];
    var points = [];
    for (var s = 0; s <= 16; s++) {
        var t = s / 16,
            u = 1 - t;
        points.push([
            u * u * from[0] + 2 * u * t * control[0] + t * t * target[0],
            u * u * from[1] + 2 * u * t * control[1] + t * t * target[1],
        ]);
    }
    return points;
}
function metroSegments(c, start, end) {
    var stops = metroStops(c.metro.toIndex, c.metro.fromIndex);
    var first = metroStations[stops[0]],
        last = metroStations[stops[stops.length - 1]];
    var segments = [{ kind: "leg", latlngs: [start, [first.lat, first.lng]] }];
    // One segment per line ridden; the hop between lines takes the colour of the line joined.
    for (var i = 1; i < stops.length; i++) {
        var from = metroStations[stops[i - 1]],
            to = metroStations[stops[i]],
            color = METRO_LINES[to.line].color,
            current = segments[segments.length - 1];
        if (current.kind === "metro" && current.color === color)
            current.latlngs.push([to.lat, to.lng]);
        else
            segments.push({
                kind: "metro",
                color: color,
                latlngs: [
                    [from.lat, from.lng],
                    [to.lat, to.lng],
                ],
            });
    }
    segments.push({ kind: "leg", latlngs: [[last.lat, last.lng], end] });
    return segments;
}

// Grows the trip from the place of interest to the listing (drawn at once with motion off).
function drawCommutePath(segments, delay) {
    var total = 0;
    var lines = segments.map(function (segment) {
        var lengths = [0];
        for (var i = 1; i < segment.latlngs.length; i++) {
            var a = segment.latlngs[i - 1],
                b = segment.latlngs[i];
            lengths.push(lengths[i - 1] + haversineKm(a[0], a[1], b[0], b[1]));
        }
        total += lengths[lengths.length - 1];
        var options = {
            pane: "commutePaths",
            interactive: false,
            className: "commute-path-" + segment.kind,
            color: segment.color || "currentColor",
            weight: segment.kind === "leg" ? 3 : segment.kind === "metro" ? 5 : 4,
            dashArray: segment.kind === "leg" ? "1 7" : null,
            opacity: 0.9,
        };
        return {
            segment: segment,
            lengths: lengths,
            casing: L.polyline([], {
                pane: "commutePaths",
                interactive: false,
                className: "commute-path-casing",
                weight: options.weight + 3,
                opacity: segment.kind === "leg" ? 0 : 0.85,
            }).addTo(commutePathLayer),
            line: L.polyline([], options).addTo(commutePathLayer),
        };
    });
    function render(progress) {
        var remaining = progress * total;
        lines.forEach(function (l) {
            var points = partialPath(l.segment.latlngs, l.lengths, remaining);
            remaining -= l.lengths[l.lengths.length - 1];
            l.casing.setLatLngs(points);
            l.line.setLatLngs(points);
        });
    }
    if (!MOTION || total === 0) return render(1);
    var state = { progress: 0 };
    commutePathTweens.push(
        gsap.to(state, {
            progress: 1,
            duration: COMMUTE_PATH_DRAW_S,
            delay: delay,
            ease: "power1.inOut",
            onUpdate: function () {
                render(state.progress);
            },
        }),
    );
}
// The first `distance` km of a polyline, given its cumulative lengths.
function partialPath(latlngs, lengths, distance) {
    if (distance <= 0) return [];
    var points = [latlngs[0]];
    for (var i = 1; i < latlngs.length; i++) {
        if (lengths[i] <= distance) {
            points.push(latlngs[i]);
            continue;
        }
        var t = (distance - lengths[i - 1]) / (lengths[i] - lengths[i - 1]),
            a = latlngs[i - 1],
            b = latlngs[i];
        points.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
        break;
    }
    return points;
}
