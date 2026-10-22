// Resync: webmap/server.py re-runs scripts/refresh_map.sh, then the page reloads
// with the rebuilt map. Polling resumes after a reload mid-sync.
var resyncPollTimer = null;
function toggleResyncConfirm(show) {
    setOverlayOpen(byId("resync-overlay"), show);
    if (show) byId("resync-confirm-button").focus();
}
function setResyncRunning(running) {
    byId("resync-button").disabled = running;
    byId("resync-label").textContent = running
        ? "Resyncing listings…"
        : "Resync listings";
}
function pollResync() {
    fetch("/resync_status")
        .then(function (r) {
            return r.json();
        })
        .then(function (status) {
            if (status.running) {
                setResyncRunning(true);
                resyncPollTimer = setTimeout(pollResync, 5000);
                return;
            }
            setResyncRunning(false);
            if (resyncPollTimer === null) return; // nothing was running when the page loaded
            resyncPollTimer = null;
            if (status.exitCode === 0) location.reload();
            else toast("Resync failed. See output/resync.log");
        })
        .catch(function () {
            setResyncRunning(false);
        });
}
function startResync() {
    document.querySelectorAll(".popover").forEach(function (p) {
        p.hidden = true;
    });
    fetch("/resync", { method: "POST" })
        .then(function (r) {
            if (r.status !== 202 && r.status !== 409) throw new Error();
            toast(
                r.status === 409
                    ? "A resync is already running"
                    : "Resyncing listings. This takes a few minutes.",
            );
            resyncPollTimer = setTimeout(pollResync, 5000);
            setResyncRunning(true);
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
            setResyncRunning(true);
            resyncPollTimer = setTimeout(pollResync, 5000);
        }
    })
    .catch(function () {});
