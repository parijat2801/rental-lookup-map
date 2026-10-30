"""Regenerate data/metro_lines.json (Namma Metro lines + stations) from OpenStreetMap.

Run from the repo root: python scripts/fetch_metro_lines.py
Overpass responses are cached as op_cache_<md5>.json in the working directory.
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUTPUT = "data/metro_lines.json"
RELATIONS = {"purple": 1798771, "green": 1798772, "yellow": 19421927}  # OSM route relation ids
COLORS = {"purple": "#8e24aa", "green": "#2e7d32", "yellow": "#f9a825"}


def overpass(query: str) -> dict:
    """Run an Overpass query, cached on disk by query hash."""
    cache = f"op_cache_{hashlib.md5(query.encode()).hexdigest()}.json"
    if os.path.exists(cache):
        with open(cache) as f:
            return json.load(f)
    result = _overpass_with_retry(query)
    with open(cache, "w") as f:
        json.dump(result, f)
    return result


def _overpass_with_retry(query: str, attempts: int = 6) -> dict:
    req = urllib.request.Request(
        OVERPASS_URL,
        data=urllib.parse.urlencode({"data": query}).encode(),
        headers={"User-Agent": "rental-lookup-metro/1.0"},
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError, ValueError):
            pass
        time.sleep(15 * (attempt + 1))  # Overpass rate-limits aggressively; back off linearly
    raise RuntimeError(f"Overpass gave up after {attempts} attempts")


def _r(p: float) -> float:
    return round(p, 5)  # ~1m precision keeps the file small


def stitch(ways: list) -> list:
    """Join way segments into one path by greedily attaching the nearest endpoint."""
    def d2(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    # Ways to attach a segment w: (which endpoints touch, reverse w?, prepend to path?)
    joins = (((0, -1), False, False), ((-1, -1), True, False), ((-1, 0), False, True), ((0, 0), True, True))
    path, rest = list(ways[0]), ways[1:]
    while rest:
        # Nearest (segment, join); ties go to the earliest segment, then join order.
        _, i, k = min((d2(w[a], path[b]), i, k)
                      for i, w in enumerate(rest)
                      for k, ((a, b), _rev, _front) in enumerate(joins))
        _, rev, front = joins[k]
        w = list(reversed(rest[i])) if rev else list(rest[i])
        path = w + path if front else path + w
        rest.pop(i)
    return [p for j, p in enumerate(path) if j == 0 or p != path[j - 1]]  # drop consecutive duplicates


def fetch_line(rel_id: int) -> tuple:
    """(path, stations) for one metro route relation."""
    rel = overpass(f"[out:json][timeout:90];relation({rel_id});out geom;")["elements"][0]
    ways = [[(_r(p["lat"]), _r(p["lon"])) for p in m["geometry"]]
            for m in rel["members"] if m["type"] == "way" and m.get("geometry")]
    stops = [m for m in rel["members"] if m["type"] == "node" and m.get("role", "").startswith("stop")]

    names = {}
    if stops:
        nodes = overpass("[out:json];node(id:" + ",".join(str(m["ref"]) for m in stops) + ");out;")
        names = {e["id"]: e.get("tags", {}).get("name", "") for e in nodes["elements"]}
    stations = [{"lat": _r(m["lat"]), "lng": _r(m["lon"]), "name": names.get(m["ref"], "")} for m in stops]
    return stitch(ways), stations


def main() -> None:
    out = {}
    for name, rel_id in RELATIONS.items():
        path, stations = fetch_line(rel_id)
        out[name] = {"color": COLORS[name], "path": [list(p) for p in path], "stations": stations}
        print(name, len(path), "pts,", len(stations), "stations")
        time.sleep(20)  # be polite to the public Overpass instance

    text = json.dumps(out, separators=(",", ":"))
    with open(OUTPUT, "w") as f:
        f.write(text)
    print("bytes:", len(text))


if __name__ == "__main__":
    main()
