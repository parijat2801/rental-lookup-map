"""Serve the map with auto-save for stars/dismissals.
Run: python3 serve_map.py
Open: http://localhost:8765/map.html
"""
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os

os.chdir(Path(__file__).parent / "output")
STARS_PATH = Path(__file__).parent / "data" / "cache" / "stars_and_dismissals.json"


class MapHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/save_stars':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                STARS_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(STARS_PATH, 'w') as f:
                    json.dump(data, f, indent=2)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


if __name__ == '__main__':
    port = 8765
    print(f"Serving map at http://localhost:{port}/map.html")
    print(f"Stars auto-save to {STARS_PATH}")
    HTTPServer(('', port), MapHandler).serve_forever()
