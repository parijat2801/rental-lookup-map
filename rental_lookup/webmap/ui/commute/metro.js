// ===========================================================================
// Places of interest and commute
//   Each listing gets a drive time (OSRM, cached) and a metro time (computed
//   from the METRO_LINES station graph) to every area; the Commute tab ranks
//   by them. Areas, drive times and the mode are kept in localStorage.
// ===========================================================================
var DRIVE_TRAFFIC_FACTOR = 1.6; // OSRM's demo server assumes empty roads
var ROAD_DETOUR = 1.4,
    WALK_DETOUR = 1.3; // road / walking distance per straight-line km
var CITY_DRIVE_KMH = 20,
    WALK_KMH = 4.8,
    MAX_WALK_KM = 1.5,
    AUTO_PICKUP_MIN = 4;
var METRO_SPEED_KMH = 34,
    METRO_DWELL_MIN = 0.5,
    METRO_TRANSFER_MIN = 5,
    METRO_WAIT_MIN = 5,
    METRO_INTERCHANGE_KM = 0.4,
    METRO_TERMINUS_LINK_KM = 1.5;
var METRO_STATION_CHOICES = 3; // nearest stations tried at each end of a trip
var COMMUTE_FULL_POINTS_MIN = 10,
    COMMUTE_ZERO_POINTS_MIN = 60;
var MAX_AREAS = 8;
var OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving/";
var OSRM_MAX_COORDINATES = 100,
    OSRM_REQUEST_GAP_MS = 1100,
    OSRM_MAX_FAILURES = 4;
var PHOTON_URL = "https://photon.komoot.io/";
var BANGALORE_BBOX = "77.3,12.7,77.9,13.2";

function haversineKm(lat1, lng1, lat2, lng2) {
    var rad = Math.PI / 180,
        dLat = (lat2 - lat1) * rad,
        dLng = (lng2 - lng1) * rad;
    var a =
        Math.pow(Math.sin(dLat / 2), 2) +
        Math.cos(lat1 * rad) *
            Math.cos(lat2 * rad) *
            Math.pow(Math.sin(dLng / 2), 2);
    return 12742 * Math.asin(Math.sqrt(a));
}
function coordKey(lat, lng) {
    return lat.toFixed(4) + "," + lng.toFixed(4);
} // same ~11m grid as builder.coordinate_key
function estimateDriveMinutes(km) {
    return ((km * ROAD_DETOUR) / CITY_DRIVE_KMH) * 60;
}
// Getting between a point and a station: walk when it's close enough, else take an auto.
function stationLegMinutes(km) {
    var auto = estimateDriveMinutes(km) + AUTO_PICKUP_MIN;
    var walkKm = km * WALK_DETOUR;
    return walkKm <= MAX_WALK_KM
        ? Math.min((walkKm / WALK_KMH) * 60, auto)
        : auto;
}

// --- Metro station graph -------------------------------------------------------
var metroStations = []; // {name, line, lat, lng}
var metroMinutesBetween = [],
    metroTransfersBetween = []; // all-pairs, indexed by station
(function buildMetroGraph() {
    var edges = [];
    function link(a, b, minutes, transfers) {
        edges[a].push([b, minutes, transfers]);
        edges[b].push([a, minutes, transfers]);
    }
    Object.keys(METRO_LINES).forEach(function (lineId) {
        (METRO_LINES[lineId].stations || []).forEach(function (station, i) {
            var index = metroStations.length;
            metroStations.push({
                name: station.name,
                line: lineId,
                lat: station.lat,
                lng: station.lng,
            });
            edges[index] = [];
            if (i > 0) {
                var previous = metroStations[index - 1];
                link(
                    index - 1,
                    index,
                    (haversineKm(
                        previous.lat,
                        previous.lng,
                        station.lat,
                        station.lng,
                    ) /
                        METRO_SPEED_KMH) *
                        60 +
                        METRO_DWELL_MIN,
                    0,
                );
            }
        });
    });
    // Interchange stations have a different name on each line, so pair them up by distance.
    metroStations.forEach(function (a, i) {
        for (var j = i + 1; j < metroStations.length; j++) {
            var b = metroStations[j];
            if (
                a.line !== b.line &&
                haversineKm(a.lat, a.lng, b.lat, b.lng) < METRO_INTERCHANGE_KM
            )
                link(i, j, METRO_TRANSFER_MIN, 1);
        }
    });
    // OSM leaves a shared terminus off one of its lines (Yellow ends at Ragigudda, one stop short of
    // RV Road on Green), so a line end close to another line rides on to that line's nearest station.
    metroStations.forEach(function (a, i) {
        var isTerminus =
            i === 0 ||
            i === metroStations.length - 1 ||
            metroStations[i - 1].line !== a.line ||
            metroStations[i + 1].line !== a.line;
        if (
            !isTerminus ||
            edges[i].some(function (edge) {
                return edge[2] === 1;
            })
        )
            return;
        var nearest = -1,
            nearestKm = METRO_TERMINUS_LINK_KM;
        metroStations.forEach(function (b, j) {
            var km = haversineKm(a.lat, a.lng, b.lat, b.lng);
            if (b.line !== a.line && km < nearestKm) {
                nearest = j;
                nearestKm = km;
            }
        });
        if (nearest >= 0)
            link(
                i,
                nearest,
                (nearestKm / METRO_SPEED_KMH) * 60 +
                    METRO_DWELL_MIN +
                    METRO_TRANSFER_MIN,
                1,
            );
    });
    var n = metroStations.length;
    for (var source = 0; source < n; source++) {
        var minutes = new Array(n).fill(Infinity),
            transfers = new Array(n).fill(0),
            done = new Array(n).fill(false);
        minutes[source] = 0;
        for (;;) {
            var u = -1;
            for (var k = 0; k < n; k++)
                if (
                    !done[k] &&
                    minutes[k] < Infinity &&
                    (u < 0 || minutes[k] < minutes[u])
                )
                    u = k;
            if (u < 0) break;
            done[u] = true;
            edges[u].forEach(function (edge) {
                if (minutes[u] + edge[1] < minutes[edge[0]]) {
                    minutes[edge[0]] = minutes[u] + edge[1];
                    transfers[edge[0]] = transfers[u] + edge[2];
                }
            });
        }
        metroMinutesBetween.push(minutes);
        metroTransfersBetween.push(transfers);
    }
})();
// The few stations quickest to reach from (lat, lng): [{index, minutes}].
function nearestStations(lat, lng) {
    return metroStations
        .map(function (s, index) {
            return {
                index: index,
                minutes: stationLegMinutes(haversineKm(lat, lng, s.lat, s.lng)),
            };
        })
        .sort(function (a, b) {
            return a.minutes - b.minutes;
        })
        .slice(0, METRO_STATION_CHOICES);
}
// Fastest metro trip between two points given their nearest stations, or null without a usable pair.
function metroTrip(fromStations, toStations) {
    var best = null;
    fromStations.forEach(function (a) {
        toStations.forEach(function (b) {
            if (
                a.index === b.index ||
                metroMinutesBetween[a.index][b.index] === Infinity
            )
                return;
            var minutes =
                a.minutes +
                METRO_WAIT_MIN +
                metroMinutesBetween[a.index][b.index] +
                b.minutes;
            if (!best || minutes < best.minutes) {
                best = {
                    minutes: minutes,
                    fromStation: metroStations[a.index].name,
                    toStation: metroStations[b.index].name,
                    transfers: metroTransfersBetween[a.index][b.index],
                };
            }
        });
    });
    return best;
}
