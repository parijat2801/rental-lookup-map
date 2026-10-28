// ===========================================================================
// Helpers
// ===========================================================================
function byId(id) {
    return document.getElementById(id);
}
var HTML_ESCAPES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
};
// Escape scraped text before putting it into innerHTML.
function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
        return HTML_ESCAPES[c];
    });
}
function formatRupees(amount) {
    return "₹" + Math.round(amount).toLocaleString("en-IN");
}
function formatRupeesShort(amount) {
    if (amount >= 100000)
        return "₹" + (amount / 100000).toFixed(amount % 100000 ? 1 : 0) + "L";
    return "₹" + Math.round(amount / 1000) + "K";
}

// Lucide icons as inline SVG strings, so re-rendered lists don't need a DOM rescan.
var _iconCache = {};
function icon(name) {
    if (_iconCache[name]) return _iconCache[name];
    var pascal = name.replace(/(^|-)(\w)/g, function (_, __, c) {
        return c.toUpperCase();
    });
    var node = window.lucide && lucide.icons[pascal];
    if (!node) return "";
    var inner = node
        .map(function (child) {
            var attrs = Object.keys(child[1])
                .map(function (k) {
                    return k + '="' + child[1][k] + '"';
                })
                .join(" ");
            return "<" + child[0] + " " + attrs + "/>";
        })
        .join("");
    return (_iconCache[name] =
        '<svg class="icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        inner +
        "</svg>");
}
function starMarkIcon() {
    return icon("star").replace('class="icon"', 'class="icon star-mark"');
}
function renderStaticIcons(root) {
    (root || document).querySelectorAll("[data-icon]").forEach(function (el) {
        var svg = icon(el.dataset.icon);
        el.outerHTML = el.className
            ? svg.replace('class="icon"', 'class="icon ' + el.className + '"')
            : svg;
    });
}
renderStaticIcons();

// GSAP drives the UI motion; without it (offline), OS reduced-motion, or a user
// opt-out in Settings → Animation, things just appear.
var MOTION_KEY = "rental_motion";
var MOTION = false;

function motionPreferenceEnabled() {
    try {
        return localStorage.getItem(MOTION_KEY) !== "0";
    } catch (e) {
        return true;
    }
}

function refreshMotion() {
    MOTION =
        !!window.gsap &&
        motionPreferenceEnabled() &&
        !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.documentElement.setAttribute(
        "data-motion",
        MOTION ? "on" : "off",
    );
}

function setMotionEnabled(on) {
    try {
        localStorage.setItem(MOTION_KEY, on ? "1" : "0");
    } catch (e) {}
    refreshMotion();
    if (typeof syncMotionUi === "function") syncMotionUi();
}

function syncMotionUi() {
    var toggle = byId("motion-toggle");
    if (toggle) toggle.checked = motionPreferenceEnabled();
}

refreshMotion();
window
    .matchMedia("(prefers-reduced-motion: reduce)")
    .addEventListener("change", refreshMotion);

function animateIn(el, from, duration) {
    if (MOTION)
        gsap.fromTo(el, Object.assign({ autoAlpha: 0 }, from), {
            autoAlpha: 1,
            x: 0,
            y: 0,
            scale: 1,
            duration: duration || 0.22,
            ease: "power2.out",
            overwrite: true,
        });
}

var GOOD_FACING = ["E", "SE", "S", "NE"];
var CAR_PARKING_TYPES = ["FOUR_WHEELER", "BOTH"];
var RELIABLE_WATER = ["CORPORATION", "BOREWELL_AND_CORPORATION", "CORP_BORE"];
var STANDALONE_SOCIETIES = [
    "standalone building",
    "standalone",
    "stand alone",
    "none",
    "",
];
