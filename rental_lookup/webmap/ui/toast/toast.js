// Short status message at the bottom of the screen.
var _toastTimer = null;
function toast(message) {
    var el = byId("toast");
    el.textContent = message;
    clearTimeout(_toastTimer);
    if (!MOTION) {
        el.classList.add("show");
        _toastTimer = setTimeout(function () {
            el.classList.remove("show");
        }, 2600);
        return;
    }
    el.style.transition = "none";
    gsap.to(el, {
        autoAlpha: 1,
        y: 0,
        duration: 0.25,
        ease: "power2.out",
        overwrite: true,
    });
    _toastTimer = setTimeout(function () {
        gsap.to(el, { autoAlpha: 0, y: 16, duration: 0.2, ease: "power2.in" });
    }, 2600);
}
