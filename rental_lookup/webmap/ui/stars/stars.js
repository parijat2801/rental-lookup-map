// ===========================================================================
// Stars & dismissals
//   {url: epochMs}; a negative value is a tombstone (un-starred / un-dismissed
//   at that time). Copies are merged so the most recent action wins, the same
//   rule as rental_lookup/stars.py.
// ===========================================================================
var starredAt = {};
var dismissedAt = {};
function mergeLatest(target, entries) {
    for (var url in entries || {}) {
        var ts = entries[url];
        if (typeof ts !== 'number') continue;
        if (target[url] === undefined || Math.abs(ts) > Math.abs(target[url])) target[url] = ts;
    }
}
// 1. Stars embedded at build time, 2. this browser's localStorage.
LISTINGS.forEach(function(d) {
    if (d.savedStarredAt) starredAt[d.url] = d.savedStarredAt;
    if (d.savedDismissedAt) dismissedAt[d.url] = d.savedDismissedAt;
});
try {
    mergeLatest(starredAt, JSON.parse(localStorage.getItem('rental_starred') || '{}'));
    mergeLatest(dismissedAt, JSON.parse(localStorage.getItem('rental_dismissed') || '{}'));
} catch (e) {}
// 3. Shared stars.json published next to the page on GitHub Pages.
fetch('stars.json').then(function(r) { return r.ok ? r.json() : {}; })
    .then(function(shared) {
        if (!shared || typeof shared !== 'object') return;
        mergeLatest(starredAt, shared.starred);
        mergeLatest(dismissedAt, shared.dismissed);
        saveStars();
        refreshMap();
    }).catch(function() {});
saveStars();

// Persist to localStorage, and to disk when served by webmap/server.py (no-op elsewhere).
function saveStars() {
    try {
        localStorage.setItem('rental_starred', JSON.stringify(starredAt));
        localStorage.setItem('rental_dismissed', JSON.stringify(dismissedAt));
    } catch (e) {}
    var payload = JSON.stringify({starred: starredAt, dismissed: dismissedAt, savedAt: new Date().toISOString()});
    fetch('/save_stars', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: payload}).catch(function() {});
}
function isStarred(url) { return starredAt[url] > 0; }
function isDismissed(url) { return dismissedAt[url] > 0; }
// Starring clears any dismissal and vice versa.
function markStarred(url) { var now = Date.now(); starredAt[url] = now; dismissedAt[url] = -now; }
function markDismissed(url) { var now = Date.now(); dismissedAt[url] = now; starredAt[url] = -now; }

function toggleStar(url) {
    if (isStarred(url)) { starredAt[url] = -Date.now(); recordUndo('unstar', [url]); }
    else { markStarred(url); recordUndo('star', [url]); justStarredUrls.add(url); }
    saveStars();
    refreshMap();
    if (isStarred(url)) popStarButtons(url);
}
function toggleDismiss(url) {
    if (isDismissed(url)) { dismissedAt[url] = -Date.now(); recordUndo('undismiss', [url]); }
    else { markDismissed(url); recordUndo('dismiss', [url]); toast('Dismissed · Ctrl+Z to undo'); }
    saveStars();
    refreshMap();
}

var undoHistory = [];
function recordUndo(action, urls) {
    undoHistory.push({action: action, urls: urls, time: Date.now()});
    if (undoHistory.length > 50) undoHistory.shift();
}
function undo() {
    var last = undoHistory.pop();
    if (!last) return;
    last.urls.forEach(function(url) {
        var now = Date.now();
        if (last.action === 'dismiss') dismissedAt[url] = -now;
        else if (last.action === 'star') starredAt[url] = -now;
        else if (last.action === 'unstar') { starredAt[url] = now; justStarredUrls.add(url); }
        else if (last.action === 'undismiss') dismissedAt[url] = now;
    });
    saveStars();
    refreshMap();
}

