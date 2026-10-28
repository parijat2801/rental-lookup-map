// ===========================================================================
// Settings modal: quality point weights + listing backup.
// Quality edits apply live and are remembered in localStorage (see scoring.js).
// ===========================================================================
var QUALITY_POINT_SECTIONS = [
    {
        title: "Apartment",
        rows: [
            { key: "goodFacing", label: "Good facing", hint: "E, SE, S or NE" },
            {
                key: "balconyEach",
                label: "Per balcony",
                hint: "Points each; capped below",
            },
            {
                key: "balconyCap",
                label: "Balcony cap",
                hint: "Max from balconies",
            },
            { key: "ageNew", label: "Age ≤ 3 years" },
            { key: "ageMid", label: "Age ≤ 7 years" },
            { key: "ageOld", label: "Age ≤ 15 years" },
            { key: "sqftLarge", label: "Size ≥ 1,500 sqft" },
            { key: "sqftMid", label: "Size ≥ 1,200 sqft" },
            { key: "cupboards", label: "Cupboards ≥ 5" },
        ],
    },
    {
        title: "Amenities",
        rows: [
            { key: "gated", label: "Gated community" },
            { key: "gym", label: "Gym" },
            { key: "park", label: "Society park" },
            { key: "powerBackup", label: "Power backup" },
            { key: "pool", label: "Pool" },
            { key: "clubhouse", label: "Clubhouse" },
            { key: "security", label: "Security" },
            { key: "carParking", label: "Car parking" },
            { key: "fireSafety", label: "Fire safety" },
            { key: "intercom", label: "Intercom" },
        ],
    },
    {
        title: "Neighbourhood",
        rows: [
            { key: "lifestyleHigh", label: "Lifestyle score ≥ 8" },
            { key: "lifestyleMid", label: "Lifestyle score ≥ 6" },
            { key: "transitHigh", label: "Transit score ≥ 8" },
            { key: "transitMid", label: "Transit score ≥ 7" },
            { key: "reliableWater", label: "Reliable water supply" },
        ],
    },
    {
        title: "Listing signals",
        rows: [
            { key: "brandedBuilder", label: "Branded builder" },
            { key: "negotiable", label: "Rent negotiable" },
            { key: "photosMany", label: "Photos ≥ 10" },
            { key: "photosSome", label: "Photos ≥ 5" },
        ],
    },
];
var SETTINGS_PANELS = {
    quality: {
        title: "Quality score",
        hint: "Points each trait adds (or subtracts). Economy ranking uses the same score per rupee.",
        quality: true,
    },
    backup: {
        title: "Listings & backup",
        hint: "Refresh listings or export/import stars and dismissals.",
        quality: false,
    },
};
var activeSettingsPanel = "quality";

function qualityRowsHtml(rows) {
    return rows
        .map(function (row) {
            var hint = row.hint
                ? '<span class="hint">' + escapeHtml(row.hint) + "</span>"
                : "";
            return (
                '<div class="quality-weight-row" data-key="' +
                row.key +
                '">' +
                '<div class="quality-weight-copy"><span>' +
                escapeHtml(row.label) +
                "</span>" +
                hint +
                "</div>" +
                '<input type="number" min="-99" max="99" step="1" ' +
                'data-quality-point="' +
                row.key +
                '" aria-label="' +
                escapeHtml(row.label) +
                ' points" ' +
                'oninput="onQualityPointInput(this)" ' +
                'onchange="onQualityPointCommit(this)" />' +
                "</div>"
            );
        })
        .join("");
}

function backupPanelHtml() {
    return (
        '<div class="settings-actions">' +
        '<button class="settings-action" id="resync-button" ' +
        'onclick="toggleSettings(false); toggleResyncConfirm(true)">' +
        '<span data-icon="refresh-cw"></span>' +
        '<span class="settings-action-copy">' +
        '<span id="resync-label">Resync listings</span>' +
        '<span class="hint">Fetch fresh listings and rebuild the map</span>' +
        "</span></button>" +
        '<button class="settings-action" onclick="copyStarredToClipboard()">' +
        '<span data-icon="copy"></span>' +
        '<span class="settings-action-copy">' +
        "<span>Copy starred listings</span>" +
        '<span class="hint">Clipboard text for the current filters</span>' +
        "</span></button>" +
        '<button class="settings-action" onclick="downloadStarsBackup()">' +
        '<span data-icon="download"></span>' +
        '<span class="settings-action-copy">' +
        "<span>Download backup</span>" +
        '<span class="hint">Stars and dismissals as JSON</span>' +
        "</span></button>" +
        '<button class="settings-action" onclick="restoreStarsBackup()">' +
        '<span data-icon="upload"></span>' +
        '<span class="settings-action-copy">' +
        "<span>Restore from backup</span>" +
        '<span class="hint">Merge a previously downloaded JSON</span>' +
        "</span></button>" +
        "</div>"
    );
}

function qualityPanelHtml() {
    return QUALITY_POINT_SECTIONS.map(function (section) {
        return (
            '<section class="quality-weights-section">' +
            '<h4 class="label">' +
            escapeHtml(section.title) +
            "</h4>" +
            qualityRowsHtml(section.rows) +
            "</section>"
        );
    }).join("");
}

function highlightSettingsNav() {
    document.querySelectorAll(".settings-nav-item").forEach(function (btn) {
        btn.classList.toggle(
            "on",
            btn.dataset.settingsPanel === activeSettingsPanel,
        );
    });
}

function syncSettingsPanelHead() {
    var meta = SETTINGS_PANELS[activeSettingsPanel];
    byId("settings-panel-title").textContent = meta.title;
    byId("settings-panel-hint").textContent = meta.hint;
    byId("quality-weights-reset").hidden = !meta.quality;
}

function showSettingsPanel(panel) {
    activeSettingsPanel = panel;
    syncSettingsPanelHead();
    document.querySelectorAll(".settings-panel").forEach(function (el) {
        el.hidden = el.dataset.panel !== panel;
    });
    highlightSettingsNav();
    if (panel === "quality") byId("settings-panels").scrollTop = 0;
    syncQualityWeightsUi();
}

function buildSettingsChrome() {
    var nav = byId("settings-nav"),
        panels = byId("settings-panels");
    if (!nav || !panels) return;

    nav.innerHTML =
        '<div class="settings-nav-group">Personalisation</div>' +
        '<button type="button" class="settings-nav-item" ' +
        'id="settings-nav-quality" data-settings-panel="quality" ' +
        'onclick="showSettingsPanel(\'quality\')">Quality score</button>' +
        '<div class="settings-nav-group">Data</div>' +
        '<button type="button" class="settings-nav-item" ' +
        'data-settings-panel="backup" onclick="showSettingsPanel(\'backup\')">' +
        "Listings &amp; backup</button>";

    panels.innerHTML =
        '<div class="settings-panel" id="settings-panel-quality" ' +
        'data-panel="quality" hidden>' +
        qualityPanelHtml() +
        "</div>" +
        '<div class="settings-panel" id="settings-panel-backup" ' +
        'data-panel="backup" hidden>' +
        backupPanelHtml() +
        "</div>";

    renderStaticIcons(byId("settings-overlay"));
}

function syncQualityWeightsUi() {
    var customized = qualityPointsCustomized();
    document.querySelectorAll("[data-quality-point]").forEach(function (input) {
        var key = input.dataset.qualityPoint;
        if (document.activeElement !== input) input.value = qualityPoints[key];
        var row = input.closest(".quality-weight-row");
        if (row)
            row.classList.toggle(
                "changed",
                qualityPoints[key] !== DEFAULT_QUALITY_POINTS[key],
            );
    });
    var qualityNav = byId("settings-nav-quality");
    if (qualityNav) qualityNav.classList.toggle("changed", customized);
    var reset = byId("quality-weights-reset");
    if (reset) reset.disabled = !customized;
    var qualityTab = byId("rank-quality");
    if (qualityTab) {
        qualityTab.classList.toggle("customized", customized);
        qualityTab.title = customized
            ? "General desirability (custom points)"
            : "General desirability";
    }
    var settingsBtn = byId("settings-button");
    if (settingsBtn) settingsBtn.classList.toggle("customized", customized);
}

function clampQualityPoint(raw) {
    var n = parseInt(raw, 10);
    if (!isFinite(n)) return 0;
    return Math.max(-99, Math.min(99, n));
}
function onQualityPointInput(input) {
    var key = input.dataset.qualityPoint;
    if (!(key in DEFAULT_QUALITY_POINTS)) return;
    // Allow clearing or typing a leading "-" without snapping to 0 mid-edit.
    if (input.value === "" || input.value === "-") return;
    qualityPoints[key] = clampQualityPoint(input.value);
    saveQualityPoints();
    recomputeQualityScores();
    syncQualityWeightsUi();
}
function onQualityPointCommit(input) {
    var key = input.dataset.qualityPoint;
    if (!(key in DEFAULT_QUALITY_POINTS)) return;
    qualityPoints[key] = clampQualityPoint(input.value);
    input.value = qualityPoints[key];
    saveQualityPoints();
    recomputeQualityScores();
    syncQualityWeightsUi();
}
function onResetQualityPoints() {
    resetQualityPoints();
    recomputeQualityScores();
    syncQualityWeightsUi();
    toast("Quality points reset to defaults");
}
function toggleSettings(show) {
    var overlay = byId("settings-overlay");
    if (show) showSettingsPanel(activeSettingsPanel);
    setOverlayOpen(overlay, show);
}

(function initSettingsDialog() {
    if (!byId("settings-overlay")) return;
    buildSettingsChrome();
    showSettingsPanel(activeSettingsPanel);
})();
