"""Development loop: build the map, serve it, and rebuild + reload the browser on changes.

Run:  python -m rental_lookup.webmap.dev [PORT]   (or `rental-map-dev`)
Open: http://localhost:8765/map.html

Watches the package code, the template and the scraped/cached inputs. Each change
re-runs the builder in a fresh process (so code edits take effect) and the open
page reloads itself. Changes to server.py or dev.py need a restart.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from rental_lookup.paths import (
    ACRES99_PAGES_DIR, ENV_PATH, FAKE_LOCATION_IDS_PATH, LISTING_DETAILS_PATH, MAGICBRICKS_PAGES_DIR,
    MAP_PAGE_PATH, METRO_LINES_PATH, NOBROKER_PAGES_DIR, OUTPUT_DIR, PLATFORM_SCORES_PATH,
    PREVIOUS_NOBROKER_PAGES_DIR, PROPERTYANGEL_PAGES_DIR, REPO_ROOT,
)
from rental_lookup.webmap.server import DEFAULT_PORT, MapRequestHandler

PACKAGE_DIR = Path(__file__).resolve().parent.parent
# (folder, glob) pairs and single files that feed the build. The stars file and
# first_seen.json are deliberately absent: the server and the builder write them.
WATCHED_FOLDERS = (
    (PACKAGE_DIR, "**/*.py"),
    (PACKAGE_DIR, "**/*.html"),
    (PACKAGE_DIR, "**/*.css"),
    (PACKAGE_DIR, "**/*.js"),
    (NOBROKER_PAGES_DIR, "*.json"),
    (PREVIOUS_NOBROKER_PAGES_DIR, "*.json"),
    (MAGICBRICKS_PAGES_DIR, "*.json"),
    (ACRES99_PAGES_DIR, "*.json"),
    (PROPERTYANGEL_PAGES_DIR, "*.json"),
)
WATCHED_FILES = (LISTING_DETAILS_PATH, PLATFORM_SCORES_PATH, FAKE_LOCATION_IDS_PATH, METRO_LINES_PATH, ENV_PATH)
NEEDS_RESTART = {PACKAGE_DIR / "webmap" / "server.py", PACKAGE_DIR / "webmap" / "dev.py"}
POLL_SECONDS = 1.0
QUIET_SECONDS = 1.0  # scrapers save many pages in a row; wait for writes to settle

# Polled by the page; a new value makes it reload. A string because ints this
# large lose precision as JS numbers.
_RUN_ID = str(time.time_ns())
_build_count = 0


def _build_version() -> str:
    return f"{_RUN_ID}-{_build_count}"

LIVE_RELOAD_SCRIPT = """<script>
(function() {
    var loadedVersion = null;
    setInterval(function() {
        fetch('/__build_version').then(function(r) { return r.json(); }).then(function(body) {
            if (loadedVersion === null) loadedVersion = body.version;
            else if (body.version !== loadedVersion) location.reload();
        }).catch(function() {});
    }, 1000);
})();
</script>"""


class DevRequestHandler(MapRequestHandler):
    """The normal map server, plus live reload for map.html."""

    def log_message(self, format, *args):
        pass  # the page polls every second; keep the console readable

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/__build_version":
            return self._reply_json(200, {"version": _build_version()})
        if path == "/map.html" and MAP_PAGE_PATH.exists():
            # Embedded data never contains "</body>" (to_script_json escapes "</").
            head, _, tail = MAP_PAGE_PATH.read_text(encoding="utf-8").rpartition("</body>")
            body = (head + LIVE_RELOAD_SCRIPT + "</body>" + tail).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def snapshot_inputs() -> dict:
    """Modification time of every watched file, keyed by path."""
    mtimes = {}
    for folder, pattern in WATCHED_FOLDERS:
        if folder.exists():
            for path in folder.glob(pattern):
                if "__pycache__" not in path.parts:
                    mtimes[path] = path.stat().st_mtime_ns
    for path in WATCHED_FILES:
        if path.exists():
            mtimes[path] = path.stat().st_mtime_ns
    return mtimes


def _changed_paths(before: dict, after: dict) -> list:
    return sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))


def rebuild() -> bool:
    """Run the builder in a fresh process; True on success."""
    global _build_count
    started = time.monotonic()
    result = subprocess.run([sys.executable, "-m", "rental_lookup.webmap.builder"],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout + result.stderr)
        print("[!] Build failed; still serving the previous map")
        return False
    summary = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "Map built"
    _build_count += 1
    print(f"{summary} in {time.monotonic() - started:.1f}s")
    return True


def watch_and_rebuild() -> None:
    known = snapshot_inputs()
    while True:
        time.sleep(POLL_SECONDS)
        current = snapshot_inputs()
        if current == known:
            continue
        while True:
            time.sleep(QUIET_SECONDS)
            settled = snapshot_inputs()
            if settled == current:
                break
            current = settled

        changed = _changed_paths(known, current)
        names = ", ".join(str(p.relative_to(REPO_ROOT)) for p in changed[:3])
        print(f"\nChanged: {names}{f' (+{len(changed) - 3} more)' if len(changed) > 3 else ''}")
        if NEEDS_RESTART & set(changed):
            print("  (server changes take effect after restarting this command)")
        rebuild()
        known = current


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    rebuild()
    try:
        server = ThreadingHTTPServer(("", port), partial(DevRequestHandler, directory=str(OUTPUT_DIR)))
    except OSError as e:
        sys.exit(f"Can't listen on port {port} ({e.strerror}). Stop the other server or pass a different PORT.")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Serving map at http://localhost:{port}/map.html (live reload on)")
    print("Watching code, template and data for changes. Ctrl+C to stop.")
    try:
        watch_and_rebuild()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
