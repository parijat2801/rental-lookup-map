"""Serve the map locally with auto-save for stars/dismissals.

Run:  python -m rental_lookup.webmap.server [PORT]
Open: http://localhost:8765/map.html

The page POSTs its full star state to /save_stars on every change; it is merged
into the gitignored data/cache/stars_and_dismissals.json (most recent action per
URL wins). That file is a local backup only — stars live in the browser's
localStorage and are never published to GitHub.

POST /resync runs scripts/refresh_map.sh in the background (one at a time, output
in output/resync.log); GET /resync_status reports whether it is still running and
which refresh step it has reached (parsed from the log).
"""
import json
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from rental_lookup.paths import OUTPUT_DIR, REFRESH_SCRIPT_PATH, REPO_ROOT, RESYNC_LOG_PATH, STARS_PATH
from rental_lookup.stars import merge_stars, parse_json_object

DEFAULT_PORT = 8765
MAX_REQUEST_BYTES = 10 * 1024 * 1024
# Matches `=== Step N: label ===` lines written by scripts/refresh_map.sh.
RESYNC_STEP_RE = re.compile(r"^=== Step (\d+):\s*(.+?)\s*===\s*$", re.MULTILINE)
RESYNC_TOTAL_STEPS = 7
_save_lock = threading.Lock()  # requests are handled on separate threads

_resync_lock = threading.Lock()
_resync_process = None
_resync_started_at = None


def parse_resync_progress(log_text: str) -> dict:
    """Current refresh step from the script's banner lines in the log."""
    step, label = 0, "Starting…"
    for match in RESYNC_STEP_RE.finditer(log_text):
        step, label = int(match.group(1)), match.group(2)
    if "=== Done!" in log_text:
        step, label = RESYNC_TOTAL_STEPS, "Done"
    return {"step": step, "totalSteps": RESYNC_TOTAL_STEPS, "stepLabel": label}


def resync_status() -> dict:
    with _resync_lock:
        if _resync_process is None:
            status = {"running": False, "exitCode": None, "startedAt": None}
        else:
            exit_code = _resync_process.poll()
            status = {
                "running": exit_code is None,
                "exitCode": exit_code,
                "startedAt": _resync_started_at,
            }
    progress = {"step": 0, "totalSteps": RESYNC_TOTAL_STEPS, "stepLabel": "Starting…"}
    try:
        progress = parse_resync_progress(RESYNC_LOG_PATH.read_text(encoding="utf-8", errors="replace"))
    except FileNotFoundError:
        pass
    except OSError:
        pass
    return {**status, **progress}


def start_resync() -> bool:
    """Start the refresh script unless one is already running; True if started."""
    global _resync_process, _resync_started_at
    with _resync_lock:
        if _resync_process is not None and _resync_process.poll() is None:
            return False
        RESYNC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with RESYNC_LOG_PATH.open("w") as log:
            _resync_process = subprocess.Popen(["bash", str(REFRESH_SCRIPT_PATH)], cwd=REPO_ROOT,
                                               stdout=log, stderr=subprocess.STDOUT)
        _resync_started_at = datetime.now(timezone.utc).isoformat()
        return True


class MapRequestHandler(SimpleHTTPRequestHandler):
    def _reply_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _is_same_origin(self) -> bool:
        # Browsers send Origin on cross-site POSTs; without this check any web page
        # could start a scrape on this machine.
        origin = self.headers.get("Origin")
        return origin is None or urlsplit(origin).netloc == self.headers.get("Host")

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/resync_status":
            return self._reply_json(200, resync_status())
        super().do_GET()

    def do_POST(self):
        if self.path == "/resync":
            if not self._is_same_origin():
                return self._reply_json(403, {"ok": False, "error": "cross-origin request"})
            if not start_resync():
                return self._reply_json(409, {"ok": False, "error": "a resync is already running"})
            return self._reply_json(202, {"ok": True})
        if self.path != "/save_stars":
            return self._reply_json(404, {"ok": False, "error": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_REQUEST_BYTES:
            return self._reply_json(400, {"ok": False, "error": "bad Content-Length"})
        from_browser = parse_json_object(self.rfile.read(length).decode("utf-8", "replace"))
        if not from_browser:
            return self._reply_json(400, {"ok": False, "error": "expected a JSON object"})

        with _save_lock:
            on_disk = parse_json_object(STARS_PATH.read_text()) if STARS_PATH.exists() else {}
            merged = merge_stars([on_disk, from_browser], keep_tombstones=True)
            merged["savedAt"] = from_browser.get("savedAt") or datetime.now(timezone.utc).isoformat()
            STARS_PATH.parent.mkdir(parents=True, exist_ok=True)
            temp_path = STARS_PATH.with_suffix(".json.tmp")
            temp_path.write_text(json.dumps(merged, indent=2))
            temp_path.replace(STARS_PATH)  # atomic: a crash mid-write can't corrupt the file
        self._reply_json(200, {"ok": True})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    print(f"Serving map at http://localhost:{port}/map.html")
    print(f"Stars auto-save to {STARS_PATH}")
    handler = partial(MapRequestHandler, directory=str(OUTPUT_DIR))
    ThreadingHTTPServer(("", port), handler).serve_forever()


if __name__ == "__main__":
    main()
