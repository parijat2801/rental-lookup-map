// Sidebar: drag its right edge to resize, or collapse it to give the map the full width.
// Both are remembered in localStorage.
var SIDEBAR_MIN = 420, SIDEBAR_MAX = 540, SIDEBAR_DEFAULT = 420;
function clampSidebarWidth(width) {
    return Math.round(Math.max(SIDEBAR_MIN, Math.min(SIDEBAR_MAX, window.innerWidth * 0.6, width)));
}
var sidebarWidth = clampSidebarWidth(+localStorage.getItem('rental_sidebar_width') || SIDEBAR_DEFAULT);
var sidebarCollapsed = localStorage.getItem('rental_sidebar_collapsed') === '1';
function applySidebar() {
    var root = document.documentElement.style;
    root.setProperty('--sidebar-open', sidebarWidth + 'px');
    root.setProperty('--sidebar', (sidebarCollapsed ? 0 : sidebarWidth) + 'px');
    document.body.classList.toggle('sidebar-collapsed', sidebarCollapsed);
}
// Width the sidebar takes from the map (0 when collapsed or stacked on mobile).
function sidebarOffset() { return sidebarCollapsed || window.innerWidth <= 820 ? 0 : sidebarWidth; }
function toggleSidebar(collapse) {
    sidebarCollapsed = collapse === undefined ? !sidebarCollapsed : collapse;
    localStorage.setItem('rental_sidebar_collapsed', sidebarCollapsed ? '1' : '0');
    applySidebar();
}
applySidebar();
byId('sidebar').addEventListener('transitionend', function(e) { if (e.propertyName === 'width') map.invalidateSize(); });
(function() {
    var handle = byId('sidebar-resize'), startX = 0, startWidth = 0, frame = 0;
    handle.addEventListener('pointerdown', function(e) {
        e.preventDefault();
        handle.setPointerCapture(e.pointerId);
        startX = e.clientX; startWidth = sidebarWidth;
        document.body.classList.add('resizing');
    });
    handle.addEventListener('pointermove', function(e) {
        if (!document.body.classList.contains('resizing')) return;
        sidebarWidth = clampSidebarWidth(startWidth + e.clientX - startX);
        applySidebar();
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(function() { map.invalidateSize({debounceMoveend: true}); });
    });
    function endResize() {
        if (!document.body.classList.contains('resizing')) return;
        document.body.classList.remove('resizing');
        localStorage.setItem('rental_sidebar_width', sidebarWidth);
        map.invalidateSize();
    }
    handle.addEventListener('pointerup', endResize);
    handle.addEventListener('pointercancel', endResize);
    handle.addEventListener('dblclick', function() {
        sidebarWidth = SIDEBAR_DEFAULT;
        localStorage.setItem('rental_sidebar_width', sidebarWidth);
        applySidebar();
    });
})();

