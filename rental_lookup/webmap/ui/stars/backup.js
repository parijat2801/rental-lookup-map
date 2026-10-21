// Saved-state actions from the header menu: backup download/restore and copying starred listings.
function downloadStarsBackup() {
    var state = {
        starred: starredAt,
        dismissed: dismissedAt,
        exportedAt: new Date().toISOString(),
        starredCount: Object.keys(starredAt).length,
        dismissedCount: Object.keys(dismissedAt).length
    };
    var link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], {type: 'application/json'}));
    link.download = 'stars_and_dismissals.json';
    link.click();
    toast('Saved. Put it in data/cache/ to embed it in the next build.');
}
// Restoring a backup overwrites current entries for the URLs it contains.
function restoreStarsBackup() {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = function(e) {
        var file = e.target.files[0];
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function(ev) {
            try {
                var state = JSON.parse(ev.target.result);
                Object.assign(starredAt, state.starred || {});
                Object.assign(dismissedAt, state.dismissed || {});
                saveStars();
                refreshMap();
                toast('Restored ' + (state.starredCount || 0) + ' stars and ' + (state.dismissedCount || 0) + ' dismissals');
            } catch (err) {
                toast('That file isn\'t a valid backup');
            }
        };
        reader.readAsText(file);
    };
    input.click();
}
function copyStarredToClipboard() {
    var starred = filteredListings.filter(function(d) { return isStarred(d.url); });
    var text = starred.map(function(d, i) {
        return (i + 1) + '. ' + d.society + ' | Rs.' + d.totalCost.toLocaleString() + '/mo | ' + (FURNISHING_LABELS[d.furnishing] ? FURNISHING_LABELS[d.furnishing] + ' | ' : '') + d.sqft + 'sqft | ' + d.bhk + '\n   ' + d.url;
    }).join('\n\n');
    navigator.clipboard.writeText(text)
        .then(function() { toast('Copied ' + starred.length + ' starred listings'); })
        .catch(function() { prompt('Copy the starred listings:', text); });
}

