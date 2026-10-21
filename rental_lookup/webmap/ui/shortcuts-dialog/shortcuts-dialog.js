// Keyboard shortcuts: the ? dialog listing them, and the global key handler.
function toggleShortcuts(show) { setOverlayOpen(byId('shortcuts-overlay'), show); }
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') {  // undo works in any state
        e.preventDefault();
        undo();
        return;
    }
    var key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    if (key === 'Escape' && filtersOpen()) { e.preventDefault(); closeFilters(); return; }
    if (openOverlay) {
        if (key === 'Escape' || (key === '?' && openOverlay.id === 'shortcuts-overlay')) { e.preventDefault(); setOverlayOpen(openOverlay, false); }
        return;
    }
    var typing = e.target.closest && e.target.closest('input, textarea');
    if (e.target.id === 'search-input') {
        if (key === 'Escape') { e.preventDefault(); e.target.value = ''; e.target.blur(); refreshMap(); }
        return;
    }
    if (e.target.id === 'area-input') return;  // handled by onAreaKeydown
    if (key === '?' && !typing) { e.preventDefault(); toggleShortcuts(true); return; }
    var isDismissKey = key === 'x' || key === 'd', isStarKey = key === 'c' || key === 's';

    if (boxSelection.length > 0 && !selectedListing) {
        if (isDismissKey) { e.preventDefault(); dismissBoxSelection(); }
        else if (isStarKey) { e.preventDefault(); starBoxSelection(); }
        else if (key === 'Escape') { e.preventDefault(); clearBoxSelection(); }
        return;
    }

    if (!selectedListing) return;
    if (isDismissKey) { e.preventDefault(); toggleDismiss(selectedListing.url); deselectListing(); }
    else if (isStarKey) { e.preventDefault(); toggleStar(selectedListing.url); }
    else if (key === 'Enter' || key === 'v') { e.preventDefault(); window.open(selectedListing.url, '_blank'); }
    else if (key === 'ArrowLeft') { e.preventDefault(); stepPhoto(-1); }
    else if (key === 'ArrowRight') { e.preventDefault(); stepPhoto(1); }
    else if (key === 'Escape') { e.preventDefault(); deselectListing(); }
});

