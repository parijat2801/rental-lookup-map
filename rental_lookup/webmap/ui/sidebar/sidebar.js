// Sidebar: floating overlay on the map. Drag its right edge to resize, or collapse it.
// Both are remembered in localStorage.
var SIDEBAR_MIN = 420,
    SIDEBAR_MAX = 460,
    SIDEBAR_DEFAULT = 420,
    SIDEBAR_INSET = 12;
function clampSidebarWidth(width) {
    return Math.round(
        Math.max(
            SIDEBAR_MIN,
            Math.min(SIDEBAR_MAX, window.innerWidth * 0.6, width),
        ),
    );
}
var sidebarWidth = clampSidebarWidth(
    +localStorage.getItem("rental_sidebar_width") || SIDEBAR_DEFAULT,
);
var sidebarCollapsed = localStorage.getItem("rental_sidebar_collapsed") === "1";
function applySidebar() {
    var root = document.documentElement.style;
    root.setProperty("--sidebar-open", sidebarWidth + "px");
    root.setProperty("--sidebar", (sidebarCollapsed ? 0 : sidebarWidth) + "px");
    document.body.classList.toggle("sidebar-collapsed", sidebarCollapsed);
}
// Left edge clearance for map UI (sidebar width + inset); 0 when collapsed or stacked on mobile.
function sidebarOffset() {
    return sidebarCollapsed || window.innerWidth <= 820
        ? 0
        : sidebarWidth + SIDEBAR_INSET;
}
function toggleSidebar(collapse) {
    sidebarCollapsed = collapse === undefined ? !sidebarCollapsed : collapse;
    localStorage.setItem(
        "rental_sidebar_collapsed",
        sidebarCollapsed ? "1" : "0",
    );
    applySidebar();
}
applySidebar();
(function () {
    var handle = byId("sidebar-resize"),
        startX = 0,
        startWidth = 0;
    handle.addEventListener("pointerdown", function (e) {
        e.preventDefault();
        handle.setPointerCapture(e.pointerId);
        startX = e.clientX;
        startWidth = sidebarWidth;
        document.body.classList.add("resizing");
    });
    handle.addEventListener("pointermove", function (e) {
        if (!document.body.classList.contains("resizing")) return;
        sidebarWidth = clampSidebarWidth(startWidth + e.clientX - startX);
        applySidebar();
    });
    function endResize() {
        if (!document.body.classList.contains("resizing")) return;
        document.body.classList.remove("resizing");
        localStorage.setItem("rental_sidebar_width", sidebarWidth);
    }
    handle.addEventListener("pointerup", endResize);
    handle.addEventListener("pointercancel", endResize);
    handle.addEventListener("dblclick", function () {
        sidebarWidth = SIDEBAR_DEFAULT;
        localStorage.setItem("rental_sidebar_width", sidebarWidth);
        applySidebar();
    });
})();
