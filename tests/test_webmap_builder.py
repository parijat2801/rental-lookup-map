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


def test_template_has_injectable_placeholders():
    template = MAP_TEMPLATE_PATH.read_text(encoding="utf-8")
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
