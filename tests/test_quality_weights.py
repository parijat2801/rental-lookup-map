"""Quality score point weights are editable in Settings and persisted locally."""

from rental_lookup.webmap.builder import load_template


def test_quality_points_defaults_and_persistence():
    html = load_template()
    assert "var DEFAULT_QUALITY_POINTS =" in html
    assert 'QUALITY_POINTS_KEY = "rental_quality_points"' in html
    assert "function loadQualityPoints()" in html
    assert "function saveQualityPoints()" in html
    assert "function recomputeQualityScores()" in html
    assert "loadQualityPoints();" in html


def test_quality_score_reads_quality_points():
    html = load_template()
    assert "var p = qualityPoints," in html
    assert "s += p.goodFacing;" in html
    assert "s += p.gym;" in html
    assert "s += p.gated;" in html
    assert "s += p.floor1;" in html
    assert "s += p.floor3;" in html
    assert "s += p.floor4Plus;" in html
    assert "floor1: -5" in html
    assert "floor3: 8" in html
    assert "floor4Plus: 5" in html


def test_settings_modal_wired():
    html = load_template()
    assert 'id="settings-overlay"' in html
    assert 'id="settings-button"' in html
    assert "function toggleSettings(" in html
    assert "function showSettingsPanel(" in html
    assert "toggleSettings(true)" in html
    assert "settings-nav" in html
    assert "Personalisation" in html
    assert "Quality score" in html
    assert "Listings & backup" in html or "Listings &amp; backup" in html
    assert "Resync listings" in html
    assert "Copy starred listings" in html
    assert 'min="-99"' in html
    assert "Math.max(-99, Math.min(99" in html
    assert "quality-section-" not in html
    assert "onSettingsNav" not in html
    assert 'id="saved-popover"' not in html
    assert 'data-icon="ellipsis"' not in html
