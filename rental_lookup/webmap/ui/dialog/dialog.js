// Modal dialogs (.overlay elements). One is open at a time; Esc closes it (see shortcuts-dialog.js).
var openOverlay = null;
function setOverlayOpen(overlay, show) {
    openOverlay = show ? overlay : null;
    if (show) {
        overlay.hidden = false;
        animateIn(overlay, {}, 0.18);
        if (MOTION)
            gsap.fromTo(
                overlay.firstElementChild,
                { y: 12, scale: 0.96 },
                { y: 0, scale: 1, duration: 0.3, ease: "back.out(1.6)" },
            );
    } else if (MOTION) {
        gsap.to(overlay, {
            autoAlpha: 0,
            duration: 0.15,
            overwrite: true,
            onComplete: function () {
                if (openOverlay !== overlay) overlay.hidden = true;
            },
        });
    } else {
        overlay.hidden = true;
    }
}
