"""Map server: the /resync endpoints that re-run the refresh script from the page."""
import json
import threading
import time
import urllib.error
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer

import pytest

from rental_lookup.webmap import server


@pytest.fixture
def map_server(tmp_path, monkeypatch):
    script = tmp_path / "refresh.sh"
    script.write_text(
        "echo '=== Step 1: Fetch NoBroker ==='\n"
        "sleep 0.3\n"
        "echo '=== Step 2: Fetch MagicBricks ==='\n"
        "sleep 0.3\n"
        "echo '=== Done! ==='\n"
    )
    monkeypatch.setattr(server, "REFRESH_SCRIPT_PATH", script)
    monkeypatch.setattr(server, "RESYNC_LOG_PATH", tmp_path / "resync.log")
    monkeypatch.setattr(server, "_resync_process", None)
    monkeypatch.setattr(server, "_resync_started_at", None)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(server.MapRequestHandler, directory=str(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path
    httpd.shutdown()


def _request(url, method="GET", headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method=method, headers=headers or {})) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_resync_runs_script_once_at_a_time(map_server):
    base, tmp_path = map_server
    idle = _request(base + "/resync_status")[1]
    assert idle["running"] is False
    assert idle["step"] == 0
    assert idle["totalSteps"] == 7
    assert _request(base + "/resync", "POST")[0] == 202
    assert _request(base + "/resync", "POST")[0] == 409
    assert _request(base + "/resync_status")[1]["running"] is True

    deadline = time.monotonic() + 5
    while _request(base + "/resync_status")[1]["running"] and time.monotonic() < deadline:
        time.sleep(0.1)
    status = _request(base + "/resync_status")[1]
    assert status["running"] is False
    assert status["exitCode"] == 0
    assert status["step"] == 7
    assert status["stepLabel"] == "Done"
    assert "Fetch NoBroker" in (tmp_path / "resync.log").read_text()


def test_resync_status_reports_current_step(map_server, monkeypatch, tmp_path):
    log = tmp_path / "resync.log"
    log.write_text("=== Step 1: Fetch NoBroker ===\n=== Step 3: Fetch Property Angel ===\n")
    monkeypatch.setattr(server, "RESYNC_LOG_PATH", log)
    monkeypatch.setattr(server, "_resync_process", None)
    progress = server.parse_resync_progress(log.read_text())
    assert progress == {
        "step": 3,
        "totalSteps": 7,
        "stepLabel": "Fetch Property Angel",
    }


def test_resync_rejects_cross_origin_requests(map_server):
    base, _ = map_server
    assert _request(base + "/resync", "POST", {"Origin": "https://evil.example"})[0] == 403
    assert _request(base + "/resync_status")[1]["running"] is False
