// Theme: light / dark, remembered in localStorage (falls back to system preference).
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

function currentTheme() {
    return (
        document.documentElement.getAttribute("data-theme") ||
        storedTheme() ||
        systemTheme()
    );
}

function syncThemeToggle() {
    var btn = byId("theme-toggle");
    if (!btn) return;
    var theme = currentTheme();
    var next = theme === "dark" ? "light" : "dark";
    btn.title = "Switch to " + next + " theme";
    btn.setAttribute("aria-label", btn.title);
    btn.innerHTML = icon(theme === "dark" ? "sun" : "moon");
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
    syncThemeToggle();
    // Function decls are hoisted in the single page script, so also wait until
    // `map` has been assigned before touching the basemap / re-rendering.
    if (typeof map !== "undefined" && map) syncBasemap();
    if (prev && prev !== theme && typeof refreshMap === "function") refreshMap();
}

function toggleTheme() {
    applyTheme(currentTheme() === "dark" ? "light" : "dark", true);
}

applyTheme(storedTheme() || systemTheme(), false);
window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", function () {
        if (!storedTheme()) applyTheme(systemTheme(), false);
    });
