"""Dev watcher: must not rebuild on files that the server or the builder write."""
from rental_lookup.paths import FIRST_SEEN_PATH, MAP_PAGE_PATH, STARS_PATH
from rental_lookup.webmap import dev


def test_watcher_ignores_files_written_by_server_and_builder():
    watched = set(dev.WATCHED_FILES)
    for folder, pattern in dev.WATCHED_FOLDERS:
        for path in (STARS_PATH, FIRST_SEEN_PATH, MAP_PAGE_PATH):
            assert not (folder in path.parents and path.match(pattern)), path
    assert not watched & {STARS_PATH, FIRST_SEEN_PATH, MAP_PAGE_PATH}


def test_watcher_sees_template_and_code():
    snapshot = dev.snapshot_inputs()
    assert dev.PACKAGE_DIR / "webmap" / "template.html" in snapshot
    assert dev.PACKAGE_DIR / "webmap" / "builder.py" in snapshot
    ui = dev.PACKAGE_DIR / "webmap" / "ui"
    for partial in (ui / "sidebar" / "sidebar.html", ui / "core" / "base.css", ui / "core" / "boot.js"):
        assert partial in snapshot


def test_build_version_is_a_string():
    assert isinstance(dev._build_version(), str)  # large ints lose precision in JS
