"""Web map builder: template injection and safe inlining of scraped data."""
import json

import pytest

from rental_lookup.paths import MAP_TEMPLATE_PATH
from rental_lookup.webmap import builder


def test_inject_replaces_single_line_declaration():
    page = builder.inject("a\nvar LISTINGS = [1,2];\nvar map = 1;\n", "LISTINGS", "[3]")
    assert page == "a\nvar LISTINGS = [3];\nvar map = 1;\n"


def test_inject_does_not_interpret_backslashes():
    assert builder.inject("var LISTINGS = [];", "LISTINGS", '["\\\\1"]') == 'var LISTINGS = ["\\\\1"];'


def test_inject_fails_loudly_when_marker_missing():
    with pytest.raises(ValueError):
        builder.inject("var OTHER = [];", "LISTINGS", "[]")


def test_script_json_cannot_close_script_tag():
    out = builder.to_script_json({"description": "nice flat</script><script>alert(1)"})
    assert "</script>" not in out
    assert json.loads(out)["description"] == "nice flat</script><script>alert(1)"


def test_html_entities_decoded_without_breaking_json():
    records = builder._unescape_strings([{"society": "Tom &amp; Jerry &quot;Heights&quot;", "n": 1}])
    assert records == [{"society": 'Tom & Jerry "Heights"', "n": 1}]
    assert json.loads(builder.to_script_json(records))[0]["society"] == 'Tom & Jerry "Heights"'


def test_load_template_expands_nested_includes(tmp_path):
    (tmp_path / "parts").mkdir()
    (tmp_path / "parts" / "outer.html").write_text("<div>\n  <!-- @include inner.html -->\n</div>\n")
    (tmp_path / "parts" / "inner.html").write_text("  <p>hi</p>\n")
    (tmp_path / "style.css").write_text("a{}\n")
    (tmp_path / "app.js").write_text("var x = 1;")
    (tmp_path / "page.html").write_text(
        "<style>\n/* @include style.css */\n</style>\n<!-- @include parts/outer.html -->\n"
        "<script>\n// @include app.js\n</script>\n")
    assert builder.load_template(tmp_path / "page.html") == (
        "<style>\na{}\n</style>\n<div>\n  <p>hi</p>\n</div>\n<script>\nvar x = 1;\n</script>\n")


def test_load_template_fails_loudly_on_missing_include(tmp_path):
    (tmp_path / "page.html").write_text("<!-- @include nope.html -->\n")
    with pytest.raises(FileNotFoundError):
        builder.load_template(tmp_path / "page.html")


def test_load_template_rejects_include_cycles(tmp_path):
    (tmp_path / "a.html").write_text("<!-- @include b.html -->\n")
    (tmp_path / "b.html").write_text("<!-- @include a.html -->\n")
    with pytest.raises(ValueError):
        builder.load_template(tmp_path / "a.html")


def test_every_ui_file_is_included_once():
    ui_dir = MAP_TEMPLATE_PATH.parent / "ui"
    included = []
    pending = [MAP_TEMPLATE_PATH]
    while pending:
        path = pending.pop()
        for match in builder.INCLUDE_LINE.finditer(path.read_text(encoding="utf-8")):
            target = (path.parent / match.group(1)).resolve()
            included.append(target)
            pending.append(target)
    ui_files = {p.resolve() for p in ui_dir.rglob("*") if p.is_file()}
    assert sorted(included) == sorted(ui_files)
    assert "@include" not in builder.load_template()


def test_template_has_injectable_placeholders():
    template = builder.load_template()
    page = builder.inject(builder.inject(template, "LISTINGS", "[]"), "METRO_LINES", "{}")
    page = builder.inject(page, "CARTO_KEY", '"k"')
    assert "var LISTINGS = [];" in page and "var METRO_LINES = {};" in page and 'var CARTO_KEY = "k";' in page


def test_carto_key_prefers_environment(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("CARTO_BASEMAPS_KEY=from_file\n")
    monkeypatch.setenv("CARTO_BASEMAPS_KEY", "from_env")
    assert builder.carto_key(env) == "from_env"


def test_carto_key_reads_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OTHER=x\nCARTO_BASEMAPS_KEY = 'from_file'\n")
    monkeypatch.delenv("CARTO_BASEMAPS_KEY", raising=False)
    assert builder.carto_key(env) == "from_file"


def test_carto_key_empty_when_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("CARTO_BASEMAPS_KEY", raising=False)
    assert builder.carto_key(tmp_path / ".env") == ""
