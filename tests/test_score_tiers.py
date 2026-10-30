"""Score colours come from absolute cut-offs, not the filtered set."""
from rental_lookup.webmap.builder import load_template


def test_tiers_use_score_not_filtered_matches():
    html = load_template()
    assert "currentTiers = tiersForScore(mode.score)" in html
    assert "percentileTiers(matches.map" not in html
    assert "function tiersForScore(scoreName)" in html
    assert "SCORE_TIERS[scoreName]" in html
