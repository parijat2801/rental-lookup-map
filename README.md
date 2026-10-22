# rental-map

Find a flat in Bangalore without tabbing between rental portals.

rental-map scrapes **NoBroker**, **MagicBricks** and **Property Angel**, de-duplicates listings across
them, scores each one, and puts everything on a single interactive map with real
filters, rankings and a shared star/dismiss list. It also produces a ranked CSV
scored against distances to parks, lakes and metro stations from OpenStreetMap.

Everything runs locally: listing data and your stars live in plain JSON files in
this repo. An optional GitHub Actions workflow refreshes the map daily and
publishes it to GitHub Pages.

> **Heads-up:** the scrapers call undocumented internal APIs. They work today and
> may break without notice when a portal changes. See [Disclaimer](#disclaimer).

## Features

**Interactive map** (`output/map.html`)

- One marker per listing, sized by area and coloured by the active ranking.
- Three rankings: **Quality** (light, age, amenities, platform scores, ...),
  **Value** (quality per rupee) and **Best Deals** (amenities and location
  relative to cost), plus a fourth,
  **Commute**, driven by your [places of interest](#places-of-interest).
- Sliders for total cost (rent + maintenance), area, photo count, deposit
  multiple, minimum score and listing age; chips for BHK, lift, parking, facing,
  balcony, pool, pet-friendly, branded builder, source and more.
- Star / dismiss listings with undo, bulk-select with shift + drag, and keyboard
  shortcuts (`C` star, `X` dismiss, `Enter` open, `←`/`→` photos, `Ctrl+Z` undo,
  `Esc` close); press `?` for the full list.
- Hover cards with photos, costs, amenities and an optional AI photo checklist.
  A selected listing's card stays pinned to its marker as the map pans, and the
  marker pulses so it's easy to spot.
- Floating sidebar over the map (drag its edge to resize, double-click to reset)
  that can be collapsed; both settings are remembered per browser.
- "Show my location" button that puts a live blue dot on the map (needs browser
  location permission).
- Namma Metro line overlay; listings delisted since the last run shown in grey;
  listings sharing a suspicious coordinate shown dashed.
- Subtle animations via GSAP, switched off when the OS asks for reduced motion.

**CLI ranking** (`output/results.csv`): NoBroker listings within a budget, scored
0–100+ on pet-friendliness, space, light, freshness, amenities and distance to the
nearest park, lake and metro station.

## Requirements

- Python 3.9+ (CI uses 3.13)
- Network access to NoBroker, MagicBricks, Property Angel and the OpenStreetMap Overpass API

## Quick start

```bash
git clone https://github.com/sarweshshah/rental-map.git
cd rental-map
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

scripts/refresh_map.sh   # fetch, enrich and build output/map.html (takes a while)
rental-map-dev           # serve it at http://localhost:8765/map.html, rebuilding on changes
```

Serving the map through the bundled server (rather than opening the file) also
backs up stars/dismissals to the gitignored `data/cache/stars_and_dismissals.json`
(browser `localStorage` is the source of truth). It enables **••• → Resync
listings**, which runs `scripts/refresh_map.sh` in the background (output in
`output/resync.log`) and reloads the page when done.

### Build / run commands

Installing the package adds these commands:

| Command | Same as | What it does |
| --- | --- | --- |
| `rental-map-fetch SOURCE` | `python -m rental_lookup.sources SOURCE` | Fetch listings from `nobroker`, `magicbricks`, `propertyangel` or `all` into `data/`. |
| `rental-map-rank` | `python -m rental_lookup` | Score NoBroker listings into `output/results.csv`. |
| `rental-map-build` | `python -m rental_lookup.webmap.builder` | Build `output/map.html` once. |
| `rental-map-serve [PORT]` | `python -m rental_lookup.webmap.server` | Serve the map without the watcher. |
| `rental-map-dev [PORT]` | `python -m rental_lookup.webmap.dev` | Build the map, serve it, and watch for changes: edits to the code, the template or the data files trigger a rebuild, and the open page reloads itself. A failed build keeps serving the previous map. |

`rental-map-fetch` and `rental-map-rank` take `--cookie COOKIE` and `--help`.

In Cursor / VS Code, the same commands are set up as tasks in `.vscode/`:
**Run Build Task** (`Cmd/Ctrl+Shift+B`) starts the dev watcher, **Run Test Task**
runs pytest, and the Run and Debug panel can launch the dev server under the
debugger.

## Usage

Each step can also be run on its own, from the repository root:

| Step | Command |
| --- | --- |
| Fetch NoBroker listings | `rental-map-fetch nobroker [--cookie COOKIE]` |
| Fetch MagicBricks listings | `rental-map-fetch magicbricks` |
| Fetch Property Angel listings | `rental-map-fetch propertyangel` |
| Fetch from every source | `rental-map-fetch all [--cookie COOKIE]` |
| Rank NoBroker listings into `output/results.csv` | `rental-map-rank [--cookie COOKIE]` |
| Fetch detail pages for the top N NoBroker listings | `python -m rental_lookup.enrichment.listing_details [N]` |
| Look up NoBroker transit / lifestyle ratings missing from search results (~1 s per listing, cached) | `python -m rental_lookup.enrichment.listing_details scores [LIMIT]` |
| Build `output/map.html` from saved data | `rental-map-build` |
| Serve the map with star auto-save | `rental-map-serve [PORT]` |
| Serve, watch and rebuild on changes | `rental-map-dev [PORT]` |
| Regenerate the metro overlay | `python scripts/fetch_metro_lines.py` |
| Merge star export files | `python -m rental_lookup.stars OUTPUT INPUT [INPUT ...]` |

Notes:

- NoBroker pages already saved under `data/raw/` are reused; empty that folder (as
  `scripts/refresh_map.sh` does) to force a fresh fetch. The previous run is moved
  to `data/raw_prev/` so the map can show delisted listings.
- `COOKIE` is an optional NoBroker `Cookie` header, only needed if requests start
  getting blocked.
- The map builder works with whatever data is present; every input except the
  template is optional.

### Configuration

| Variable | Used by | Purpose |
| --- | --- | --- |
| `CARTO_BASEMAPS_KEY` | map builder | CARTO light basemap. Without it the map uses Esri's keyless light-grey tiles. Can also be set in a local `.env` (see `.env.example`). |

Search areas, budgets and scoring weights are constants at the top of the
relevant modules (`sources/nobroker.py`, `scoring.py`, `location.py`) and in the
scoring functions of `webmap/ui/scoring/scoring.js`.

### Experimental: Facebook groups

`rental_lookup.sources.facebook` parses rental posts from Facebook groups. It is
not part of the map pipeline and needs an extra dependency and your cookies:

```bash
pip install -e '.[facebook]'
python -m rental_lookup.sources.facebook cookies.txt
```

## Automated daily map (GitHub Actions)

[`.github/workflows/update-map.yml`](.github/workflows/update-map.yml) runs on
every push to `main`, daily at 08:00 IST and on demand. It runs the tests,
fetches fresh listings, builds the map, and pushes `index.html` to the
`gh-pages` branch. Personal stars/dismissals are never published.

To use it on your fork:

1. Create a `gh-pages` branch and enable GitHub Pages for it.
2. Optionally add a `CARTO_BASEMAPS_KEY` repository secret.

## Project layout

```
sources → data/ → enrichment → webmap builder → output/map.html
```

```
rental_lookup/
  sources/         scrapers (nobroker, magicbricks, propertyangel)
  enrichment/      per-listing extras (detail pages, scores)
  webmap/
    builder.py     data/ + ui/ → output/map.html
    ui/            front-end components (one folder each; core/ is shared)
    server.py      serve the map
    dev.py         serve + rebuild on changes
  models.py        Listing dataclass
  scoring.py       CLI ranking → results.csv
  paths.py         all on-disk locations
data/
  raw*/            saved API pages (gitignored)
  cache/           first-seen, detail caches (tracked); stars file is gitignored
scripts/           refresh_map.sh, fetch_metro_lines.py
tests/             pytest
output/            map.html, results.csv (gitignored)
```

## Stars and dismissals

Stars are personal and stay on your machine. The browser's `localStorage` is the
source of truth; when you use `rental-map-dev` / `rental-map-serve`, changes are
also backed up to the gitignored `data/cache/stars_and_dismissals.json`. Neither
the repo nor GitHub Pages publishes them.

Format: `{"starred": {url: timestamp}, "dismissed": {url: timestamp}}`. A
negative timestamp is an un-star / un-dismiss; when copies are merged the most
recent action per URL wins. The "Saved state" panel can export/import a backup
file to move stars between browsers.

## Places of interest

On the **Commute** tab, add the places you want to get to easily (office, gym,
friends): search for a place, paste a full Google Maps URL or `lat, lng`, or
right-click anywhere on the map. Short `maps.app.goo.gl` links can't be read from
the page; open them and paste the full URL instead. Each listing then gets two
commute times per place:

- **Drive**: road time from the public [OSRM](https://project-osrm.org) server,
  multiplied by `DRIVE_TRAFFIC_FACTOR` (1.6) because OSRM assumes empty roads.
  The page routes about one batch of 100 locations per second, listings in view
  first, and caches the results in `localStorage`. Until a listing is routed, a
  straight-line estimate is shown with a leading `~`.
- **Metro**: computed in the page from the Namma Metro stations in
  `data/metro_lines.json`: walk (up to 1.5 km) or take an auto to one of the
  three nearest stations, wait, ride (including changes between lines), then walk
  or take an auto to the place. Lines that open after the last
  `python scripts/fetch_metro_lines.py` run aren't counted.

Ranking uses the faster of drive and metro for each place; both times are shown.
Places combine with AND: a listing has to be easy to reach from every place, so its
commute score comes from its longest commute (100 at 10 minutes or less, falling
to 0 at 60 minutes). Ties go to the shorter average commute, then the lower cost.
Places and drive times are kept per browser.
All speeds and penalties are constants at the top of
`rental_lookup/webmap/ui/commute/metro.js`. `COMMUTE_BLEND_WEIGHT` in
`ui/scoring/score-tiers.js` (currently 0) is where commute can later be blended into the other rankings.

## Development

```bash
pip install -e '.[dev]'
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for conventions and how to add a new source.

## Disclaimer

This project is not affiliated with NoBroker, MagicBricks, Property Angel, Facebook or any other
listing platform. The scrapers use undocumented endpoints that may change or be
blocked at any time, and automated access may be against those sites' terms of
service. You are responsible for how you use this software. Be polite: the
scrapers already pause between requests, so please don't remove that.

Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.

## License

[MIT](LICENSE) © The rental-map contributors
