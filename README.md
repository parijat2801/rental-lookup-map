# rental-map

Find a flat in Bangalore without tabbing between rental portals.

rental-map scrapes **NoBroker** and **MagicBricks**, de-duplicates listings across
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
- Four rankings: **Quality** (light, age, amenities, platform scores, ...),
  **Value** (quality per rupee), **Villa Vibe** (spacious, outdoorsy, central) and
  **Best Deals** (amenities and location relative to cost), plus a fifth,
  **Commute**, driven by your [areas of interest](#areas-of-interest).
- Sliders for total cost (rent + maintenance), area, photo count, deposit
  multiple, minimum score and listing age; chips for BHK, lift, parking, facing,
  balcony, pool, pet-friendly, branded builder, source and more.
- Star / dismiss listings with undo, bulk-select with shift + drag, and keyboard
  shortcuts (`C` star, `X` dismiss, `Enter` open, `←`/`→` photos, `Ctrl+Z` undo,
  `Esc` close); press `?` for the full list.
- Hover cards with photos, costs, amenities and an optional AI photo checklist.
  A selected listing's card stays pinned to its marker as the map pans, and the
  marker pulses so it's easy to spot.
- Resizable sidebar (drag its edge, double-click to reset) that can be collapsed
  to give the map the full width; both settings are remembered per browser.
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
- Network access to NoBroker, MagicBricks and the OpenStreetMap Overpass API

## Quick start

```bash
git clone https://github.com/sarweshshah/rental-map.git
cd rental-map
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

scripts/refresh_map.sh   # fetch, enrich and build output/map.html (takes a while)
rental-map-dev           # serve it at http://localhost:8765/map.html, rebuilding on changes
```

Serving the map through the bundled server (rather than opening the file) makes
every star and dismissal auto-save to `data/cache/stars_and_dismissals.json`.

### Build / run commands

Installing the package adds these commands:

| Command | Same as | What it does |
| --- | --- | --- |
| `rental-map-fetch SOURCE` | `python -m rental_lookup.sources SOURCE` | Fetch listings from `nobroker`, `magicbricks` or `all` into `data/`. |
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
| Fetch from every source | `rental-map-fetch all [--cookie COOKIE]` |
| Rank NoBroker listings into `output/results.csv` | `rental-map-rank [--cookie COOKIE]` |
| Fetch detail pages for the top N NoBroker listings | `python -m rental_lookup.enrichment.listing_details [N]` |
| Build `output/map.html` from saved data | `rental-map-build` |
| Serve the map with star auto-save | `rental-map-serve [PORT]` |
| Serve, watch and rebuild on changes | `rental-map-dev [PORT]` |
| Regenerate the metro overlay | `python scripts/fetch_metro_lines.py` |
| Merge star files (used by CI) | `python -m rental_lookup.stars OUTPUT INPUT [INPUT ...]` |

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
scoring functions of `webmap/template.html`.

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
fetches fresh listings, merges stars from the published `stars.json`, the CI cache
and the repo, builds the map, and pushes `index.html` + `stars.json` to the
`gh-pages` branch.

To use it on your fork:

1. Create a `gh-pages` branch and enable GitHub Pages for it.
2. Optionally add a `CARTO_BASEMAPS_KEY` repository secret.
3. Point the published `stars.json` URL in the "Sync stars" step at your own
   Pages site.

## Project layout

```
rental_lookup/
  sources/          scrapers: nobroker, magicbricks, facebook (experimental)
  enrichment/       slow per-listing extras: listing_details
  webmap/           builder (data -> output/map.html), template.html, server, dev watcher
  models.py         normalised Listing and related dataclasses
  location.py       OpenStreetMap parks / lakes / metro and distance lookups
  scoring.py        CLI suitability score; ranking_report.py writes results.csv
  listing_age.py    days since a listing was posted
  stars.py          merging starred / dismissed listings across copies
  paths.py          every data and output location in one place
scripts/            refresh_map.sh, fetch_metro_lines.py
tests/              pytest suite (no network needed)
data/
  raw/ raw_prev/ raw_mb/   saved API pages (gitignored, re-fetched each run)
  cache/                   stars, first-seen dates, detail and photo caches (tracked)
  metro_lines.json         metro overlay
  spike/                   API contracts and sample responses
docs/               design notes and API investigations
output/             generated map.html and results.csv (gitignored)
```

## Stars and dismissals

Stars are stored as `{"starred": {url: timestamp}, "dismissed": {url: timestamp}}`.
A negative timestamp records an un-star / un-dismiss, and when copies are merged
the most recent action for each URL wins. The map merges three copies on load:
the stars embedded at build time, the browser's `localStorage`, and a `stars.json`
published next to the page. The "Saved state" panel can back up and restore them
as a file.

## Areas of interest

On the **Commute** tab, add the places you want to get to easily (office, gym,
friends): search for a place, paste a full Google Maps URL or `lat, lng`, or
right-click anywhere on the map. Short `maps.app.goo.gl` links can't be read from
the page; open them and paste the full URL instead. Each listing then gets two
commute times per area:

- **Drive**: road time from the public [OSRM](https://project-osrm.org) server,
  multiplied by `DRIVE_TRAFFIC_FACTOR` (1.6) because OSRM assumes empty roads.
  The page routes about one batch of 100 locations per second, listings in view
  first, and caches the results in `localStorage`. Until a listing is routed, a
  straight-line estimate is shown with a leading `~`.
- **Metro**: computed in the page from the Namma Metro stations in
  `data/metro_lines.json`: walk (up to 1.5 km) or take an auto to one of the
  three nearest stations, wait, ride (including changes between lines), then walk
  or take an auto to the area. Lines that open after the last
  `python scripts/fetch_metro_lines.py` run aren't counted.

The **Best / Drive / Metro** toggle picks which time counts. Areas combine with
AND: a listing has to be easy to reach from every area, so its commute score comes
from its longest commute (100 at 10 minutes or less, falling to 0 at 60 minutes).
Ties go to the shorter average commute, then the lower cost. Areas, the toggle and drive times are kept per browser.
All speeds and penalties are constants at the top of the "Areas of interest and
commute" section in `rental_lookup/webmap/template.html`. `COMMUTE_BLEND_WEIGHT`
(currently 0) is where commute can later be blended into the other rankings.

## Development

```bash
pip install -e '.[dev]'
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for conventions and how to add a new source.

## Disclaimer

This project is not affiliated with NoBroker, MagicBricks, Facebook or any other
listing platform. The scrapers use undocumented endpoints that may change or be
blocked at any time, and automated access may be against those sites' terms of
service. You are responsible for how you use this software. Be polite: the
scrapers already pause between requests, so please don't remove that.

Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.

## License

[MIT](LICENSE) © The rental-map contributors
