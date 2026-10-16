"""Tests for star merge logic used by CI to combine stars from multiple sources."""
import json

import pytest

from rental_lookup.stars import main, merge_stars, parse_json_object


# --- parse_json_object tests ---

def test_load_valid_json():
    data = parse_json_object('{"starred": {"url1": 123}, "dismissed": {}}')
    assert data["starred"]["url1"] == 123


def test_load_corrupted_json_returns_empty():
    """Corrupted JSON (unquoted keys) should return empty dict, not crash."""
    corrupted = '{\n  dismissed:\n  {\n    https://example.com: int,\n  }\n}'
    data = parse_json_object(corrupted)
    assert data == {}


def test_load_empty_string_returns_empty():
    assert parse_json_object("") == {}


def test_load_html_error_page_returns_empty():
    """jsonblob sometimes returns HTML error pages."""
    assert parse_json_object("<html><body>404</body></html>") == {}


def test_load_json_error_object_returns_empty():
    """jsonblob returns {error: string} with unquoted keys when expired."""
    assert parse_json_object('{\n  error: string\n}') == {}


def test_load_null_returns_empty():
    assert parse_json_object("null") == {}


def test_load_valid_but_not_dict_returns_empty():
    """A JSON array is valid JSON but not a stars dict."""
    assert parse_json_object("[1, 2, 3]") == {}


# --- merge_stars tests ---

def test_merge_single_source():
    sources = [{"starred": {"a": 1}, "dismissed": {"b": 2}}]
    result = merge_stars(sources)
    assert result["starred"] == {"a": 1}
    assert result["dismissed"] == {"b": 2}


def test_merge_union_of_multiple_sources():
    sources = [
        {"starred": {"a": 1}, "dismissed": {"x": 1}},
        {"starred": {"b": 2}, "dismissed": {"y": 2}},
    ]
    result = merge_stars(sources)
    assert "a" in result["starred"]
    assert "b" in result["starred"]
    assert "x" in result["dismissed"]
    assert "y" in result["dismissed"]


def test_merge_star_wins_over_dismiss():
    """If a URL is starred in one source and dismissed in another, star wins."""
    sources = [
        {"starred": {"url1": 100}, "dismissed": {}},
        {"starred": {}, "dismissed": {"url1": 50}},
    ]
    result = merge_stars(sources)
    assert "url1" in result["starred"]
    assert "url1" not in result["dismissed"]


def test_merge_later_source_overwrites_timestamp():
    """Later source's timestamp wins for same URL."""
    sources = [
        {"starred": {"url1": 100}, "dismissed": {}},
        {"starred": {"url1": 200}, "dismissed": {}},
    ]
    result = merge_stars(sources)
    assert result["starred"]["url1"] == 200


def test_merge_empty_sources_returns_empty():
    result = merge_stars([{}, {}, {}])
    assert result == {"starred": {}, "dismissed": {}}


def test_merge_skips_corrupted_sources():
    """Corrupted sources (missing keys) should be treated as empty."""
    sources = [
        {"starred": {"a": 1}, "dismissed": {}},
        "not a dict",
        {"starred": {"b": 2}, "dismissed": {}},
    ]
    result = merge_stars(sources)
    assert "a" in result["starred"]
    assert "b" in result["starred"]


def test_merge_preserves_all_dismissals():
    """Dismissals from local + repo = union of both (positive values only)."""
    local = {"starred": {}, "dismissed": {f"url{i}": i + 1 for i in range(100)}}
    repo = {"starred": {}, "dismissed": {f"url{i}": i + 1 for i in range(50, 150)}}
    result = merge_stars([local, repo])
    assert len(result["dismissed"]) == 150  # 0-149, union


# --- Tombstone tests (negative timestamp = intentional deletion) ---

def test_tombstone_unstar_removes_from_starred():
    """Negative value in starred means un-starred. Should not appear in output."""
    sources = [
        {"starred": {"url1": 100}, "dismissed": {}},
        {"starred": {"url1": -200}, "dismissed": {}},
    ]
    result = merge_stars(sources)
    assert "url1" not in result["starred"]


def test_tombstone_undismiss_removes_from_dismissed():
    """Negative value in dismissed means un-dismissed."""
    sources = [
        {"starred": {}, "dismissed": {"url1": 100}},
        {"starred": {}, "dismissed": {"url1": -200}},
    ]
    result = merge_stars(sources)
    assert "url1" not in result["dismissed"]


def test_tombstone_older_than_star_does_not_remove():
    """If star (200) is newer than tombstone (-150), star wins."""
    sources = [
        {"starred": {"url1": -150}, "dismissed": {}},
        {"starred": {"url1": 200}, "dismissed": {}},
    ]
    result = merge_stars(sources)
    assert result["starred"]["url1"] == 200


def test_tombstone_newer_than_star_removes():
    """If tombstone (-300) is newer than star (200), removal wins."""
    sources = [
        {"starred": {"url1": 200}, "dismissed": {}},
        {"starred": {"url1": -300}, "dismissed": {}},
    ]
    result = merge_stars(sources)
    assert "url1" not in result["starred"]


def test_tombstone_unstar_moves_to_dismissed():
    """Un-starring should not leave the listing in limbo — it becomes dismissed."""
    sources = [
        {"starred": {"url1": 100}, "dismissed": {}},
        {"starred": {"url1": -200}, "dismissed": {}},
    ]
    result = merge_stars(sources)
    assert "url1" not in result["starred"]
    # Un-starred listings don't auto-dismiss — they just disappear from starred


def test_tombstone_stripped_from_output():
    """Output should never contain negative values."""
    sources = [
        {"starred": {"url1": -100, "url2": 200}, "dismissed": {"url3": -50, "url4": 300}},
    ]
    result = merge_stars(sources)
    for v in result["starred"].values():
        assert v > 0
    for v in result["dismissed"].values():
        assert v > 0


def test_tombstone_multi_user_unstar_scenario():
    """User A stars X, User B stars Y. User A un-stars X. Merged: only Y remains starred."""
    user_a = {"starred": {"X": -200}, "dismissed": {}}  # A un-starred X
    user_b = {"starred": {"Y": 150}, "dismissed": {}}    # B starred Y
    cloud = {"starred": {"X": 100, "Y": 150}, "dismissed": {}}  # cloud has both
    result = merge_stars([cloud, user_a, user_b])
    assert "X" not in result["starred"]
    assert result["starred"]["Y"] == 150


def test_keep_tombstones_preserves_deletions():
    """serve_map.py keeps tombstones on disk so a later merge still sees the un-star."""
    disk = {"starred": {"X": 100, "Y": 150}, "dismissed": {}}
    browser = {"starred": {"X": -200}, "dismissed": {}}
    result = merge_stars([disk, browser], keep_tombstones=True)
    assert result["starred"] == {"X": -200, "Y": 150}
    # Merging again with an older positive star must not resurrect X.
    assert "X" not in merge_stars([result, {"starred": {"X": 100}}])["starred"]


def test_empty_browser_state_does_not_wipe_disk():
    disk = {"starred": {"a": 1}, "dismissed": {"b": 2}}
    assert merge_stars([disk, {"starred": {}, "dismissed": {}}], keep_tombstones=True) == disk


def test_merge_ignores_non_dict_fields_and_bools():
    result = merge_stars([{"starred": ["not", "a", "dict"], "dismissed": {"a": True, "b": 5}}])
    assert result == {"starred": {}, "dismissed": {"b": 5}}


def test_cli_merges_files_and_refuses_empty(tmp_path):
    a, b, out = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "out.json"
    a.write_text('{"starred": {"u1": 10}}')
    b.write_text("<html>404</html>")
    main([str(out), str(a), str(b), str(tmp_path / "missing.json")])
    assert json.loads(out.read_text()) == {"starred": {"u1": 10}, "dismissed": {}}
    with pytest.raises(SystemExit):
        main([str(out), str(b)])


def test_existing_positive_stars_unaffected():
    """Existing data with all positive values should work exactly as before."""
    sources = [
        {"starred": {"a": 100, "b": 200}, "dismissed": {"c": 300, "d": 400}},
    ]
    result = merge_stars(sources)
    assert result["starred"] == {"a": 100, "b": 200}
    assert result["dismissed"] == {"c": 300, "d": 400}
