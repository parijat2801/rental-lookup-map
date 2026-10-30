// Resync: webmap/server.py re-runs scripts/refresh_map.sh, then the page reloads
// with the rebuilt map. Polling resumes after a reload mid-sync. Progress comes
// from === Step N === banners in output/resync.log via /resync_status.
var resyncPollTimer = null;
var RESYNC_POLL_MS = 1500;
var RESYNC_STEP_LABELS = {
    0: "Starting…",
    1: "Fetching NoBroker",
    2: "Fetching MagicBricks",
    3: "Fetching Property Angel",
    4: "Ranking listings",
    5: "Enriching top listings",
    6: "Fetching ratings",
    7: "Rebuilding map",
};
// Stack under the map legend so expanding the legend pushes this chip down.
var resyncProgressControl = L.control({ position: "topright" });
resyncProgressControl.onAdd = function () {
    var el = byId("resync-progress");
    L.DomEvent.disableClickPropagation(el);
    return el;
};
resyncProgressControl.addTo(map);
function toggleResyncConfirm(show) {
    setOverlayOpen(byId("resync-overlay"), show);
    if (show) byId("resync-confirm-button").focus();
}
function formatResyncElapsed(startedAt) {
    if (!startedAt) return "";
    var seconds = Math.max(0, Math.round((Date.now() - Date.parse(startedAt)) / 1000));
    if (seconds < 60) return seconds + "s";
    var minutes = Math.floor(seconds / 60);
    return minutes + "m " + (seconds % 60) + "s";
}
function updateResyncProgress(status) {
    var card = byId("resync-progress");
    var running = !!status.running;
    card.hidden = !running;
    var resyncButton = byId("resync-button"),
        resyncLabel = byId("resync-label");
    if (resyncButton) resyncButton.disabled = running;
    if (resyncLabel)
        resyncLabel.textContent = running
            ? "Resyncing listings…"
            : "Resync listings";
    if (!running) return;

    var step = Math.max(0, Math.min(status.step || 0, status.totalSteps || 7));
    var total = status.totalSteps || 7;
    var label =
        RESYNC_STEP_LABELS[step] || status.stepLabel || RESYNC_STEP_LABELS[0];
    var parts = [label];
    if (step > 0) parts.push(step + "/" + total);
    var elapsed = formatResyncElapsed(status.startedAt);
    if (elapsed) parts.push(elapsed);
    byId("resync-progress-step").textContent = parts.join(" · ");
    byId("resync-progress-fill").style.width =
        Math.round((step / total) * 100) + "%";
}
function pollResync() {
    fetch("/resync_status")
        .then(function (r) {
            return r.json();
        })
        .then(function (status) {
            if (status.running) {
                updateResyncProgress(status);
                resyncPollTimer = setTimeout(pollResync, RESYNC_POLL_MS);
                return;
            }
            updateResyncProgress(status);
            if (resyncPollTimer === null) return; // nothing was running when the page loaded
            resyncPollTimer = null;
            if (status.exitCode === 0) location.reload();
            else toast("Resync failed. See output/resync.log");
        })
        .catch(function () {
            updateResyncProgress({ running: false });
        });
}
function startResync() {
    fetch("/resync", { method: "POST" })
        .then(function (r) {
            if (r.status !== 202 && r.status !== 409) throw new Error();
            toast(
                r.status === 409
                    ? "A resync is already running"
                    : "Resyncing listings. This takes a few minutes.",
            );
            updateResyncProgress({
                running: true,
                step: 0,
                totalSteps: 7,
                stepLabel: "Starting…",
                startedAt: new Date().toISOString(),
            });
            resyncPollTimer = setTimeout(pollResync, RESYNC_POLL_MS);
        })
        .catch(function () {
            toast("Resync needs the local server: run rental-map-dev");
        });
}
fetch("/resync_status")
    .then(function (r) {
        return r.json();
    })
    .then(function (status) {
        if (status.running) {
            updateResyncProgress(status);
            resyncPollTimer = setTimeout(pollResync, RESYNC_POLL_MS);
        }
    })
    .catch(function () {});
