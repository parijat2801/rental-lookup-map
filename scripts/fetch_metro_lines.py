import json, urllib.request, urllib.parse, time

RELS = {"purple": 1798771, "green": 1798772, "yellow": 19421927}
COLORS = {"purple": "#8e24aa", "green": "#2e7d32", "yellow": "#f9a825"}

import hashlib, os
def overpass(q):
    key = hashlib.md5(q.encode()).hexdigest()
    cache = f"op_cache_{key}.json"
    if os.path.exists(cache):
        return json.load(open(cache))
    r = _overpass(q)
    json.dump(r, open(cache, "w"))
    return r

def _overpass(q):
    req = urllib.request.Request("https://overpass-api.de/api/interpreter",
        data=urllib.parse.urlencode({"data": q}).encode(),
        headers={"User-Agent": "rental-lookup-metro/1.0"})
    for attempt in range(6):
        try:
            return json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504):
                time.sleep(15 * (attempt + 1))
                continue
            raise
        except Exception:
            time.sleep(15 * (attempt + 1))
            continue
    raise RuntimeError("gave up after 429s")

out = {}
for name, rid in RELS.items():
    d = overpass(f"[out:json][timeout:90];relation({rid});out geom;")
    rel = d["elements"][0]
    ways, stations = [], []
    for m in rel["members"]:
        if m["type"] == "way" and m.get("geometry"):
            ways.append([(round(p["lat"],5), round(p["lon"],5)) for p in m["geometry"]])
        elif m["type"] == "node" and m.get("role","").startswith("stop"):
            stations.append({"lat": round(m["lat"],5), "lng": round(m["lon"],5)})
    # fetch station names for stop nodes
    ids = [m["ref"] for m in rel["members"] if m["type"]=="node" and m.get("role","").startswith("stop")]
    if ids:
        nq = "[out:json];node(id:" + ",".join(map(str,ids)) + ");out;"
        nd = overpass(nq)
        names = {e["id"]: e["tags"].get("name","") for e in nd["elements"]}
        stations = [{"lat": round(m["lat"],5), "lng": round(m["lon"],5), "name": names.get(m["ref"],"")}
                    for m in rel["members"] if m["type"]=="node" and m.get("role","").startswith("stop")]
    # stitch ways into one path: greedy nearest-endpoint ordering
    def d2(a, b): return (a[0]-b[0])**2 + (a[1]-b[1])**2
    path = list(ways[0])
    rest = ways[1:]
    while rest:
        best = None
        for i, w in enumerate(rest):
            for cand, rev, front in ((d2(w[0], path[-1]), False, False),
                                     (d2(w[-1], path[-1]), True, False),
                                     (d2(w[-1], path[0]), False, True),
                                     (d2(w[0], path[0]), True, True)):
                if best is None or cand < best[0]:
                    best = (cand, i, rev, front)
        _, i, rev, front = best
        w = list(reversed(rest[i])) if rev else list(rest[i])
        path = w + path if front else path + w
        rest.pop(i)
    # drop consecutive duplicates
    path = [p for j, p in enumerate(path) if j == 0 or p != path[j-1]]
    out[name] = {"color": COLORS[name], "path": [[p[0],p[1]] for p in path], "stations": stations}
    print(name, len(path), "pts,", len(stations), "stations")
    time.sleep(20)

with open("data/metro_lines.json","w") as f:
    json.dump(out, f, separators=(",",":"))
print("bytes:", len(open("data/metro_lines.json").read()))
