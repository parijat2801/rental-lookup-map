"""Vibe rank mode: greenery scoring is wired into the map template."""
from rental_lookup.webmap.builder import load_template


def test_map_template_has_vibe_rank_tab():
    html = load_template()
    assert 'id="rank-vibe"' in html
    assert "setRankMode('vibe')" in html
    assert "vibe:" in html  # RANK_MODES.vibe
    assert "function vibeScore(d)" in html
    assert "function greeneryHtml(d)" in html
    assert "parkM" in html or "d.parkM" in html


def test_map_template_scores_include_vibe():
    html = load_template()
    assert "vibe: vibeScore(d)" in html
    # Vibe colours come from percentileTiers, not the fixed quality cut-offs.
    assert "vibe: QUALITY_TIERS" not in html.replace(" ", "")
