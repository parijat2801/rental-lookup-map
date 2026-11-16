// First-visit welcome. Feature intro, then optional budget and BHK.
// refreshMap() writes rental_filters on boot, so a first visit sets a pending
// flag before that happens. A reload while it is pending shows the overlay
// again. Someone who already had saved filters, and no pending flag, skips it.
var WELCOME_DONE_KEY = "rental_welcome_done";
var WELCOME_PENDING_KEY = "rental_welcome_pending";
var welcomeStep = "title";
var WELCOME_STEPS = ["title", "features", "questions"];
var WELCOME_LABELS = {
    title: "welcome-title",
    features: "welcome-features-title",
    questions: "welcome-questions-title",
};

function welcomeNeeded() {
    try {
        if (localStorage.getItem(WELCOME_DONE_KEY) === "1") return false;
        if (localStorage.getItem(WELCOME_PENDING_KEY) === "1") return true;
        if (localStorage.getItem(FILTERS_STORAGE_KEY)) return false;
    } catch (e) {
        return false;
    }
    return true;
}
function setWelcomeStep(step) {
    welcomeStep = step;
    var index = WELCOME_STEPS.indexOf(step);
    WELCOME_STEPS.forEach(function (name) {
        var panel = byId("welcome-" + (name === "title" ? "title-step" : name));
        var on = name === step;
        panel.classList.toggle("on", on);
        panel.setAttribute("aria-hidden", on ? "false" : "true");
        panel.inert = !on;
    });
    byId("welcome-step-label").textContent = index + 1 + " of 3";
    var segments = byId("welcome-progress").children;
    for (var i = 0; i < segments.length; i++)
        segments[i].classList.toggle("on", i <= index);
    var dialog = byId("welcome-overlay").querySelector("[role=dialog]");
    dialog.setAttribute("aria-labelledby", WELCOME_LABELS[step]);
    dialog.focus();
    if (step === "title") startWelcomeAscii();
    else stopWelcomeAscii();
    if (step === "title" && MOTION) animateIn(byId("welcome-title"), { y: 8 }, 0.45);
    if (step === "questions") paintWelcomeCost();
}
function showWelcomeTitle() {
    setWelcomeStep("title");
}
function showWelcomeQuestions() {
    setWelcomeStep("questions");
}
function showWelcomeFeatures() {
    setWelcomeStep("features");
}
function markWelcomeDone() {
    try {
        localStorage.setItem(WELCOME_DONE_KEY, "1");
        localStorage.removeItem(WELCOME_PENDING_KEY);
    } catch (e) {}
}
function dismissWelcome() {
    stopWelcomeAscii();
    markWelcomeDone();
    setOverlayOpen(byId("welcome-overlay"), false);
}
// A small city skyline. Windows wink and stars blink, in the manner of the
// old ASCII skyline screensavers (asciiskyline / asciicity).
var WELCOME_ASCII_W = 48;
var WELCOME_ASCII_H = 13;
var WELCOME_BUILDINGS = [
    { x: 1, w: 6, h: 5 },
    { x: 8, w: 7, h: 8 },
    { x: 16, w: 5, h: 6 },
    { x: 22, w: 8, h: 10 },
    { x: 31, w: 6, h: 7 },
    { x: 38, w: 8, h: 4 },
];
var WELCOME_STARS = [
    [0, 4, "."],
    [1, 14, "*"],
    [0, 27, "."],
    [2, 36, "*"],
    [1, 44, "."],
    [0, 20, "*"],
];
var welcomeAsciiTimer = null;
function stopWelcomeAscii() {
    if (welcomeAsciiTimer) {
        clearInterval(welcomeAsciiTimer);
        welcomeAsciiTimer = null;
    }
}
function paintWelcomeAscii(tick) {
    var grid = [];
    for (var y = 0; y < WELCOME_ASCII_H; y++) {
        grid[y] = [];
        for (var x = 0; x < WELCOME_ASCII_W; x++) grid[y][x] = " ";
    }
    WELCOME_STARS.forEach(function (star, i) {
        if ((tick + i * 3) % 10 < 2) return;
        grid[star[0]][star[1]] = star[2];
    });
    WELCOME_BUILDINGS.forEach(function (b) {
        var top = WELCOME_ASCII_H - 1 - b.h;
        var mid = b.x + Math.floor(b.w / 2);
        if (top > 0) grid[top - 1][mid] = "|";
        for (var y = top; y < WELCOME_ASCII_H; y++) {
            grid[y][b.x] = "|";
            grid[y][b.x + b.w - 1] = "|";
            for (var x = b.x + 1; x < b.x + b.w - 1; x++) {
                if (y === top || y === WELCOME_ASCII_H - 1) grid[y][x] = "_";
                else if ((y - top) % 2 === 1 && (x - b.x) % 2 === 0)
                    grid[y][x] =
                        (tick + x * 5 + y * 3) % 14 < 10 ? "#" : " ";
            }
        }
    });
    for (var gx = 0; gx < WELCOME_ASCII_W; gx++)
        if (grid[WELCOME_ASCII_H - 1][gx] === " ")
            grid[WELCOME_ASCII_H - 1][gx] = "_";
    byId("welcome-ascii").innerHTML = grid
        .map(function (row) {
            return row
                .map(function (ch) {
                    if (ch === "#")
                        return '<span class="welcome-ascii-on">#</span>';
                    if (ch === "*" || ch === ".")
                        return '<span class="welcome-ascii-star">' + ch + "</span>";
                    return ch;
                })
                .join("");
        })
        .join("\n");
}
function startWelcomeAscii() {
    stopWelcomeAscii();
    paintWelcomeAscii(0);
    if (!MOTION) return;
    var tick = 0;
    welcomeAsciiTimer = setInterval(function () {
        if (welcomeStep !== "title" || !MOTION) {
            stopWelcomeAscii();
            return;
        }
        paintWelcomeAscii(++tick);
    }, 160);
}
function onWelcomeBackdrop(event) {
    if (event.target !== event.currentTarget) return;
    if (welcomeStep === "questions") dismissWelcome();
}
function onWelcomeEscape() {
    if (welcomeStep === "questions") dismissWelcome();
}
function onWelcomeCostInput(slider) {
    var low = byId("welcome-cost-min"),
        high = byId("welcome-cost-max");
    if (+low.value > +high.value)
        slider.value = slider === low ? high.value : low.value;
    paintWelcomeCost();
}
function paintWelcomeCost() {
    paintDualRangeTrack(
        "welcome-cost-min",
        "welcome-cost-max",
        "welcome-cost-fill",
    );
    var low = byId("welcome-cost-min"),
        high = byId("welcome-cost-max");
    byId("welcome-cost-value").textContent =
        formatRupeesShort(+low.value) +
        " – " +
        formatRupeesShort(+high.value) +
        (+high.value >= +high.max ? "+" : "");
    paintCostHistogram("welcome-cost-hist", +low.value, +high.value);
}
function toggleWelcomeBhk(button) {
    var on = !button.classList.contains("on");
    button.classList.toggle("on", on);
    button.setAttribute("aria-pressed", on);
}
function applyWelcome() {
    byId("filter-cost-min").value = byId("welcome-cost-min").value;
    byId("filter-cost-max").value = byId("welcome-cost-max").value;
    document.querySelectorAll("[data-welcome-bhk].on").forEach(function (chip) {
        filterChips[chip.dataset.welcomeBhk] = true;
    });
    syncChips();
    refreshMap();
    dismissWelcome();
}
function maybeOpenWelcome() {
    if (!welcomeNeeded()) return;
    try {
        localStorage.setItem(WELCOME_PENDING_KEY, "1");
    } catch (e) {}
    setWelcomeStep("title");
    setOverlayOpen(byId("welcome-overlay"), true);
}
maybeOpenWelcome();
