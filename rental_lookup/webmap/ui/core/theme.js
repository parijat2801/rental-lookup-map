// Theme: light / dark / system, remembered in localStorage (system follows OS).
var THEME_KEY = "rental_theme";

function systemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
}

function storedTheme() {
    try {
        var t = localStorage.getItem(THEME_KEY);
        return t === "light" || t === "dark" ? t : null;
    } catch (e) {
        return null;
    }
}

function themePreference() {
    return storedTheme() || "system";
}

function currentTheme() {
    return (
        document.documentElement.getAttribute("data-theme") ||
        storedTheme() ||
        systemTheme()
    );
}

function syncThemeUi() {
    var pref = themePreference();
    document.querySelectorAll("[data-theme-choice]").forEach(function (btn) {
        var on = btn.dataset.themeChoice === pref;
        btn.classList.toggle("on", on);
        btn.setAttribute("aria-checked", on ? "true" : "false");
    });
}

function applyTheme(theme, persist) {
    if (theme !== "light" && theme !== "dark") theme = systemTheme();
    var prev = document.documentElement.getAttribute("data-theme");
    document.documentElement.setAttribute("data-theme", theme);
    if (persist) {
        try {
            localStorage.setItem(THEME_KEY, theme);
        } catch (e) {}
    }
    syncThemeUi();
    // Function decls are hoisted in the single page script, so also wait until
    // `map` has been assigned before touching the basemap / re-rendering.
    if (typeof map !== "undefined" && map) syncBasemap();
    if (prev && prev !== theme && typeof refreshMap === "function") refreshMap();
}

function setThemePreference(pref) {
    if (pref === "system") {
        try {
            localStorage.removeItem(THEME_KEY);
        } catch (e) {}
        applyTheme(systemTheme(), false);
        return;
    }
    if (pref === "light" || pref === "dark") applyTheme(pref, true);
}

applyTheme(storedTheme() || systemTheme(), false);
window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", function () {
        if (!storedTheme()) applyTheme(systemTheme(), false);
    });
