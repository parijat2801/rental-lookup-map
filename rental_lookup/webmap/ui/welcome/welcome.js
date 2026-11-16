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
    var overlay = byId("welcome-overlay");
    WELCOME_STEPS.forEach(function (name) {
        var panel = byId("welcome-" + (name === "title" ? "title-step" : name));
        var on = name === step;
        panel.classList.toggle("on", on);
        panel.setAttribute("aria-hidden", on ? "false" : "true");
        panel.inert = !on;
    });
    overlay.classList.toggle("welcome-title", step === "title");
    var dialog = overlay.querySelector("[role=dialog]");
    dialog.setAttribute("aria-labelledby", WELCOME_LABELS[step]);
    dialog.focus();
    if (step === "title") startWelcomeAscii();
    else freezeWelcomeAscii();
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
// Full-viewport Bangalore skyline. Vidhana Soudha sits in the middle, towers
// pack the rest of the width, and the bottom rows are the elevated metro and
// the road. The first paint is still. Motion (lit windows, traffic, a plane)
// starts after a beat.
var welcomeAsciiTimer = null;
var welcomeAsciiDelay = null;
var welcomeSkyline = null;
var welcomeAsciiTick = 0;
var welcomeResizeBound = false;
function stopWelcomeAscii() {
    if (welcomeAsciiDelay) {
        clearTimeout(welcomeAsciiDelay);
        welcomeAsciiDelay = null;
    }
    if (welcomeAsciiTimer) {
        clearInterval(welcomeAsciiTimer);
        welcomeAsciiTimer = null;
    }
}
function welcomePut(grid, y, x, ch) {
    if (y < 0 || x < 0 || y >= grid.length || x >= grid[0].length) return;
    grid[y][x] = ch;
}
function welcomeTower(grid, x, ground, w, h) {
    var top = ground - h;
    for (var yy = top; yy < ground; yy++) {
        for (var xx = x; xx < x + w; xx++) {
            var edge = xx === x || xx === x + w - 1 || yy === top;
            var pane = (xx - x) % 2 === 1 && (yy - top) % 2 === 1;
            welcomePut(grid, yy, xx, edge ? "#" : pane ? ":" : "#");
        }
    }
    if (w >= 5) {
        var mast = x + Math.floor(w / 2);
        welcomePut(grid, top - 1, mast, "|");
        welcomePut(grid, top - 2, mast, "+");
    }
}
function welcomeSoudha(grid, x, ground, w) {
    var rows = grid.length;
    var bodyH = Math.max(10, Math.floor(rows * 0.42));
    var top = ground - bodyH;
    for (var yy = top; yy < ground; yy++) {
        var cornice = (yy - top) % 4 === 0;
        for (var xx = x; xx < x + w; xx++) {
            var edge = xx === x || xx === x + w - 1;
            var column = (xx - x) % 2 === 0;
            welcomePut(grid, yy, xx, cornice || edge || column ? "#" : ":");
        }
    }
    var steps = Math.max(4, Math.floor(rows * 0.12));
    for (var s = 1; s <= steps; s++) {
        var inset = Math.floor((s / steps) * w * 0.28);
        for (var col = inset; col < w - inset; col++)
            welcomePut(grid, top - s, x + col, "#");
    }
    var centerW = Math.max(10, Math.floor(w * 0.28));
    if (centerW % 2) centerW--;
    var cx = x + Math.floor((w - centerW) / 2);
    var rise = Math.max(4, Math.floor(rows * 0.14));
    for (var ry = 0; ry < rise; ry++) {
        for (var rx = 0; rx < centerW; rx++) {
            var column = rx % 2 === 0;
            welcomePut(grid, top - steps - ry, cx + rx, column ? "#" : ":");
        }
    }
    var domeW = Math.max(8, centerW - 2);
    if (domeW % 2) domeW--;
    var domeH = Math.max(4, Math.floor(rows * 0.1));
    var dx = cx + Math.floor((centerW - domeW) / 2);
    var dy = top - steps - rise - domeH;
    for (var row = 0; row < domeH; row++) {
        var t = (row + 0.5) / domeH;
        var half = Math.max(1, Math.round(Math.sqrt(1 - (1 - t) * (1 - t)) * (domeW / 2)));
        var mid = Math.floor(domeW / 2);
        for (var col = mid - half; col <= mid + half; col++)
            welcomePut(grid, dy + row, dx + col, "#");
    }
    var finial = dx + Math.floor(domeW / 2);
    welcomePut(grid, dy - 1, finial, "|");
    welcomePut(grid, dy - 2, finial, "+");
}
function buildWelcomeSkyline(cols, rows) {
    var grid = [];
    for (var y = 0; y < rows; y++) {
        grid[y] = [];
        for (var x = 0; x < cols; x++) grid[y][x] = ".";
    }
    var street = rows < 20 ? 3 : 4;
    var ground = rows - street;
    var soudhaW = Math.max(16, Math.floor(cols * 0.34));
    if (soudhaW % 2) soudhaW--;
    var soudhaX = Math.floor((cols - soudhaW) / 2);
    function fillSide(from, to, tallFirst) {
        var x = from;
        var n = 0;
        while (x < to) {
            var span = to - x;
            var w = 4 + ((x * 3 + n * 5) % 4);
            if (span - w < 4) w = span;
            var ramp = ((x * 7 + n * 11) % 13) / 12;
            var h = Math.floor(ground * (0.62 + ramp * 0.34));
            if (tallFirst && n === 0) h = Math.floor(ground * 0.96);
            h = Math.max(8, Math.min(h, ground - 1));
            welcomeTower(grid, x, ground, w, h);
            x += w;
            n++;
        }
    }
    fillSide(0, soudhaX, false);
    fillSide(soudhaX + soudhaW, cols, true);
    welcomeSoudha(grid, soudhaX, ground, soudhaW);
    for (var mx = 0; mx < cols; mx++) {
        grid[ground][mx] = mx % 14 === 0 ? "|" : "=";
        if (street > 1) grid[ground + 1][mx] = mx % 14 === 0 ? "|" : ":";
        if (street > 2) grid[ground + 2][mx] = "-";
        if (street > 3) grid[ground + 3][mx] = "-";
    }
    return { cols: cols, rows: rows, ground: ground, street: street, grid: grid };
}
function welcomeGridSize() {
    var probe = byId("welcome-ascii");
    var sample = document.createElement("span");
    sample.textContent = "M";
    probe.appendChild(sample);
    var rect = sample.getBoundingClientRect();
    sample.remove();
    var charW = rect.width || 5.4;
    var charH = rect.height || 9;
    var box = probe.getBoundingClientRect();
    var width = box.width || 400;
    var height = box.height || 150;
    return {
        cols: Math.max(24, Math.floor(width / charW)),
        rows: Math.max(12, Math.floor(height / charH)),
    };
}
function paintWelcomeAscii(tick, moving) {
    var size = welcomeGridSize();
    if (
        !welcomeSkyline ||
        welcomeSkyline.cols !== size.cols ||
        welcomeSkyline.rows !== size.rows
    )
        welcomeSkyline = buildWelcomeSkyline(size.cols, size.rows);
    var sky = welcomeSkyline;
    var t = moving ? tick : 0;
    var planeX = t % sky.cols;
    var east = t % sky.cols;
    var west = (sky.cols - (t % sky.cols)) % sky.cols;
    var lines = new Array(sky.rows);
    for (var y = 0; y < sky.rows; y++) {
        var parts = new Array(sky.cols);
        var src = sky.grid[y];
        for (var x = 0; x < sky.cols; x++) {
            var ch = src[x];
            if (y === 1 && x === planeX && ch === ".") ch = ">";
            if (sky.street > 2 && y === sky.ground + 2 && (x - east + sky.cols) % 9 === 0)
                ch = "o";
            if (sky.street > 3 && y === sky.ground + 3 && (x - west + sky.cols) % 11 === 0)
                ch = "o";
            if (sky.street === 3 && y === sky.ground + 2 && (x - east + sky.cols) % 9 === 0)
                ch = "o";
            if (moving && ch === ":" && (x * 5 + y * 3 + tick) % 13 === 0) ch = "*";
            parts[x] =
                ch === "*" || ch === ">" || ch === "o"
                    ? '<span class="welcome-ascii-on">' + ch + "</span>"
                    : ch;
        }
        lines[y] = parts.join("");
    }
    byId("welcome-ascii").innerHTML = lines.join("\n");
}
function freezeWelcomeAscii() {
    stopWelcomeAscii();
    paintWelcomeAscii(0, false);
}
function startWelcomeAscii() {
    stopWelcomeAscii();
    welcomeSkyline = null;
    welcomeAsciiTick = 0;
    paintWelcomeAscii(0, false);
    requestAnimationFrame(function () {
        if (welcomeStep !== "title") return;
        welcomeSkyline = null;
        paintWelcomeAscii(welcomeAsciiTick, !!welcomeAsciiTimer);
    });
    if (!welcomeResizeBound) {
        welcomeResizeBound = true;
        window.addEventListener("resize", function () {
            welcomeSkyline = null;
            var overlay = byId("welcome-overlay");
            if (!overlay || overlay.hidden) return;
            paintWelcomeAscii(welcomeAsciiTick, welcomeStep === "title" && !!welcomeAsciiTimer);
        });
    }
    if (!MOTION) return;
    welcomeAsciiDelay = setTimeout(function () {
        welcomeAsciiDelay = null;
        if (welcomeStep !== "title") return;
        welcomeAsciiTimer = setInterval(function () {
            if (welcomeStep !== "title" || !MOTION) {
                freezeWelcomeAscii();
                return;
            }
            paintWelcomeAscii(++welcomeAsciiTick, true);
        }, 140);
    }, 700);
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
    paintCostHistogram("welcome-cost-hist", +low.value, +high.value, welcomeBhkSelection());
}
function welcomeBhkSelection() {
    var chips = { bhk1: false, bhk2: false, bhk3: false, bhk3plus: false };
    document.querySelectorAll("[data-welcome-bhk].on").forEach(function (chip) {
        chips[chip.dataset.welcomeBhk] = true;
    });
    return chips;
}
function toggleWelcomeBhk(button) {
    var on = !button.classList.contains("on");
    button.classList.toggle("on", on);
    button.setAttribute("aria-pressed", on);
    paintWelcomeCost();
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
    setOverlayOpen(byId("welcome-overlay"), true);
    setWelcomeStep("title");
}
maybeOpenWelcome();
