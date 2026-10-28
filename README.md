# blr-rental-map

Find a flat in Bangalore without tabbing between rental portals.

blr-rental-map scrapes **NoBroker**, **MagicBricks**, **99acres** and **Property Angel**,
de-duplicates same-flat re-listings across them (society + floor + rent/amenities —
not merely the same building), scores each one, and puts everything on a single
interactive map with real filters, rankings and a shared star/dismiss list. It also
produces a ranked CSV scored against distances to parks, lakes and metro stations
from OpenStreetMap.

Everything runs locally: listing data and your stars live in plain JSON files in
this repo. An optional GitHub Actions workflow refreshes the map daily and
publishes it to GitHub Pages.

### Why this exists

- **Fragmented Inventory**: Inventory is split across NoBroker, MagicBricks, 99acres and Property Angel —
  each portal has listings the others don't, so you miss flats if you only use one.
- **Cross-portal dupes**: The same flat is often re-listed under different titles, photos and prices;
  without cross-portal de-dupe you waste time chasing duplicates.
- **Total cost vs Rent**: "Rent" alone is misleading: maintenance, deposit multiples and total monthly
  cost matter, but portals bury or omit them from filters.
- **Quality vs value** vs location trade-offs aren't ranked; portals sort by
  "relevance" or newest, which pushes sponsored and stale inventory.
- **Shortlist chaos**: Shortlists live in WhatsApp threads, screenshots and open tabs — there's no
  shared star/dismiss list that survives closing the browser.
- **Privacy**: Everything you star becomes a profile for the portal; a local-first tool keeps
  your shortlist on your machine instead of on theirs.
- **Tab fatigue**: Comparing options means tabbing forever — this project puts one map, real
  rankings and your shortlist in a single place so you can decide.

> **Heads-up:** the scrapers call undocumented internal APIs. They work today and
> may break without notice when a portal changes. See [Disclaimer](#disclaimer).

## Features

**Interactive map** (`output/map.html`)

- One marker per listing, sized by area and coloured by the active ranking.
- Four rankings: **Quality** (light, age, amenities, platform scores, ...),
  **Economy** (quality per rupee), **Vibe** (parks, woods/tree cover and lakes
  nearby), and **Commute**, driven by your
  [places of interest](#places-of-interest). Quality point weights are
  customisable in Settings so the ranking matches what you care about.
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
nearest park, woods/tree cover, lake and metro station.

## Requirements

- Python 3.9+ (CI uses 3.13)
- Network access to NoBroker, MagicBricks, 99acres, Property Angel and the OpenStreetMap Overpass API

## Quick start

```bash
git clone https://github.com/sarweshshah/blr-rental-map.git
cd blr-rental-map
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e '.[dev]'

scripts/refresh_map.sh               # fetch, enrich and build output/map.html (takes a while)
python3 -m rental_lookup.webmap.dev  # http://localhost:8765/map.html, rebuilds on changes
```

Prefer `python3` (macOS often has no `python` command). With the venv
activated, `python3` is the venv interpreter; without activation use
`.venv/bin/python3`. After `python3 -m pip install -e '.[dev]'`, short aliases
like `rental-map-dev` are also installed into `.venv/bin/` — they only work when
that directory is on your `PATH` (i.e. the venv is activated).

Serving the map through the bundled server (rather than opening the file) also
backs up stars/dismissals to the gitignored `data/cache/stars_and_dismissals.json`
(browser `localStorage` is the source of truth). It enables **Settings → Resync
listings**, which runs `scripts/refresh_map.sh` in the background (output in
`output/resync.log`) and reloads the page when done.

### Build / run commands

| Command | Optional alias | What it does |
| --- | --- | --- |
| `python3 -m rental_lookup.sources SOURCE` | `rental-map-fetch SOURCE` | Fetch listings from `nobroker`, `magicbricks`, `99acres`, `propertyangel` or `all` into `data/`. |
| `python3 -m rental_lookup` | `rental-map-rank` | Score NoBroker listings into `output/results.csv`. |
| `python3 -m rental_lookup.webmap.builder` | `rental-map-build` | Build `output/map.html` once. |
| `python3 -m rental_lookup.webmap.server [PORT]` | `rental-map-serve [PORT]` | Serve the map without the watcher. |
| `python3 -m rental_lookup.webmap.dev [PORT]` | `rental-map-dev [PORT]` | Build the map, serve it, and watch for changes: edits to the code, the template or the data files trigger a rebuild, and the open page reloads itself. A failed build keeps serving the previous map. |

`rental-map-fetch` / `python3 -m rental_lookup.sources` and
`rental-map-rank` / `python3 -m rental_lookup` take `--cookie COOKIE` and `--help`.

In Cursor / VS Code, the same commands are set up as tasks in `.vscode/`:
**Run Build Task** (`Cmd/Ctrl+Shift+B`) starts the dev watcher, **Run Test Task**
runs pytest, and the Run and Debug panel can launch the dev server under the
debugger.

## Usage

Each step can also be run on its own, from the repository root:

| Step | Command |
| --- | --- |
| Fetch NoBroker listings | `python3 -m rental_lookup.sources nobroker [--cookie COOKIE]` |
| Fetch MagicBricks listings | `python3 -m rental_lookup.sources magicbricks` |
| Fetch 99acres listings | `python3 -m rental_lookup.sources 99acres [--cookie COOKIE]` |
| Fetch Property Angel listings | `python3 -m rental_lookup.sources propertyangel` |
| Fetch from every source | `python3 -m rental_lookup.sources all [--cookie COOKIE]` |
| Rank NoBroker listings into `output/results.csv` | `python3 -m rental_lookup [--cookie COOKIE]` |
| Fetch detail pages for the top N NoBroker listings | `python3 -m rental_lookup.enrichment.listing_details [N]` |
| Look up NoBroker transit / lifestyle ratings missing from search results (~1 s per listing, cached) | `python3 -m rental_lookup.enrichment.listing_details scores [LIMIT]` |
| Build `output/map.html` from saved data | `python3 -m rental_lookup.webmap.builder` |
| Serve the map with star auto-save | `python3 -m rental_lookup.webmap.server [PORT]` |
| Serve, watch and rebuild on changes | `python3 -m rental_lookup.webmap.dev [PORT]` |
| Regenerate the metro overlay | `python3 scripts/fetch_metro_lines.py` |
| Merge star export files | `python3 -m rental_lookup.stars OUTPUT INPUT [INPUT ...]` |

Notes:

- NoBroker pages already saved under `data/raw_nb/` are reused; empty that folder (as
  `scripts/refresh_map.sh` does) to force a fresh fetch. The previous run is moved
  to `data/raw_nb_prev/` so the map can show delisted listings.
- `COOKIE` is an optional browser `Cookie` header for NoBroker / 99acres, only
  needed if requests start getting blocked (99acres often needs one behind Akamai).
- For 99acres, set `APIFY_TOKEN` in `.env` to use the Apify scraper instead of the
  JSON API / Chrome SSR path (`python3 -m pip install 'rental-lookup[acres99-apify]'`). Optional
  `APIFY_MAX_RESULTS` caps how many listings to buy (~$0.002 each).
- The map builder works with whatever data is present; every input except the
  template is optional.

### Configuration

| Variable | Used by | Purpose |
| --- | --- | --- |
| `CARTO_BASEMAPS_KEY` | map builder | CARTO light basemap. Without it the map uses Esri's keyless light-grey tiles. Can also be set in a local `.env` (see `.env.example`). |

Search areas and budgets are constants at the top of the relevant modules
(`sources/nobroker.py`, `scoring.py`, `location.py`). Map **quality** point
weights default in `webmap/ui/scoring/scoring.js` and can be personalised in the
UI (Settings → Quality scoring); your edits are kept in the browser.

### Experimental: Facebook groups

`rental_lookup.sources.facebook` parses rental posts from Facebook groups. It is
not part of the map pipeline and needs an extra dependency and your cookies:

```bash
python3 -m pip install -e '.[facebook]'
python3 -m rental_lookup.sources.facebook cookies.txt
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
  sources/         scrapers (nobroker, magicbricks, acres99, propertyangel)
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
source of truth; when you use the dev / serve commands above, changes are
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
  `python3 scripts/fetch_metro_lines.py` run aren't counted.

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
python3 -m pip install -e '.[dev]'
python3 -m pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for conventions and how to add a new source.

## Disclaimer

This project is not affiliated with NoBroker, MagicBricks, 99acres, Property Angel,
Facebook or any other listing platform. The scrapers use undocumented endpoints
that may change or be blocked at any time, and automated access may be against
those sites' terms of service. You are responsible for how you use this software.
Be polite: the scrapers already pause between requests, so please don't remove that.

Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.

## License

[MIT](LICENSE) © The blr-rental-map contributors
