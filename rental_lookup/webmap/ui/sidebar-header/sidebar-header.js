// Header menus: popovers toggled from the sidebar header; any click outside closes them.
function toggleMenu(id, e) {
    e.stopPropagation();
    document.querySelectorAll(".popover").forEach(function (p) {
        p.hidden = p.id !== id || !p.hidden;
        if (!p.hidden)
            animateIn(
                p,
                { y: -4, scale: 0.97, transformOrigin: "top right" },
                0.16,
            );
    });
}
document.addEventListener("click", function (e) {
    if (!e.target.closest(".popover"))
        document.querySelectorAll(".popover").forEach(function (p) {
            p.hidden = true;
        });
});
