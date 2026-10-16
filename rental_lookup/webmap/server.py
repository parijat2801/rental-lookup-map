"""Serve the map locally with auto-save for stars/dismissals.

Run:  python -m rental_lookup.webmap.server [PORT]
Open: http://localhost:8765/map.html

The page POSTs its full star state to /save_stars on every change; it is merged
into data/cache/stars_and_dismissals.json (most recent action per URL wins), so
a fresh browser with no saved state can never wipe the file.
"""
import json
import sys
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from rental_lookup.paths import OUTPUT_DIR, STARS_PATH
from rental_lookup.stars import merge_stars, parse_json_object

DEFAULT_PORT = 8765
MAX_REQUEST_BYTES = 10 * 1024 * 1024
_save_lock = threading.Lock()  # requests are handled on separate threads


class MapRequestHandler(SimpleHTTPRequestHandler):
    def _reply_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
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


def main(port: int = DEFAULT_PORT) -> None:
    print(f"Serving map at http://localhost:{port}/map.html")
    print(f"Stars auto-save to {STARS_PATH}")
    handler = partial(MapRequestHandler, directory=str(OUTPUT_DIR))
    ThreadingHTTPServer(("", port), handler).serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT)
