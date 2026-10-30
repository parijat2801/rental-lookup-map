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

- **Fragmented inventory**: each portal has listings the others don't.
- **Cross-portal dupes**: the same flat is re-listed with different titles, photos and prices.
- **Total cost vs rent**: maintenance and deposit multiples matter, but portals bury them.
- **No real ranking**: portals sort by "relevance" or newest, pushing sponsored and stale inventory.
- **Shortlist chaos**: shortlists live in WhatsApp threads, screenshots and open tabs.
- **Privacy**: a local-first tool keeps your shortlist on your machine, not the portal's.

> **Heads-up:** the scrapers call undocumented internal APIs. They work today and
> may break without notice when a portal changes. See [Disclaimer](#disclaimer).

## Features

**Interactive map** (`output/map.html`)

- One marker per listing, sized by area and coloured by the active ranking.
- Four rankings: **Quality** (light, age, amenities, platform scores, ...),
  **Economy** (quality per rupee), **Vibe** (parks, woods/tree cover and lakes
  nearby), and **Commute**, driven by your
  [places of interest](#places-of-interest). Quality point weights are
  customisable in Settings.
- Sliders for total cost (rent + maintenance), area, photo count, deposit
  multiple, minimum score and listing age; chips for BHK, lift, parking, facing,
  balcony, pool, pet-friendly, branded builder, source and more.
- Star / dismiss listings with undo, bulk-select with shift + drag, and keyboard
  shortcuts (`C` star, `Backspace` dismiss, `Enter` open, `←`/`→` photos,
  `Ctrl+Z` undo, `Esc` close); press `?` for the full list.
- Hover cards with photos, costs, amenities and an optional AI photo checklist.
  A selected listing's card stays pinned to its marker, which pulses.
- On the Commute ranking, the selected listing shows an animated route from each
  place of interest, and the card moves clear of the routes.
- Resizable, collapsible floating sidebar (double-click its edge to reset).
- "Show my location" live blue dot (needs browser location permission).
- Namma Metro line overlay; delisted listings in grey; listings sharing a
  suspicious coordinate dashed.
- Subtle GSAP animations, off when the OS asks for reduced motion.

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

Use `python3` (macOS often has no `python`), or `.venv/bin/python3` without
activating the venv. The install also adds short aliases (`rental-map-dev`, ...)
to `.venv/bin/`.

Serving the map through the bundled server (rather than opening the file) backs
up stars/dismissals to disk (see [Stars and dismissals](#stars-and-dismissals))
and enables **Settings → Resync listings**, which runs `scripts/refresh_map.sh`
in the background (log in `output/resync.log`) and reloads the page when done.

In Cursor / VS Code, `.vscode/` tasks start the dev watcher (**Run Build Task**,
`Cmd/Ctrl+Shift+B`), run pytest (**Run Test Task**), and debug the dev server.

## Usage

Run from the repository root:

| Step | Command | Alias |
| --- | --- | --- |
| Fetch listings (`nobroker`, `magicbricks`, `99acres`, `propertyangel` or `all`) | `python3 -m rental_lookup.sources SOURCE [--cookie COOKIE]` | `rental-map-fetch` |
| Rank NoBroker listings into `output/results.csv` | `python3 -m rental_lookup [--cookie COOKIE]` | `rental-map-rank` |
| Fetch detail pages for the top N NoBroker listings | `python3 -m rental_lookup.enrichment.listing_details [N]` | |
| Look up missing NoBroker transit / lifestyle ratings (~1 s per listing, cached) | `python3 -m rental_lookup.enrichment.listing_details scores [LIMIT]` | |
| Build `output/map.html` once | `python3 -m rental_lookup.webmap.builder` | `rental-map-build` |
| Serve the map with star auto-save | `python3 -m rental_lookup.webmap.server [PORT]` | `rental-map-serve` |
| Build, serve and rebuild + reload on code, template or data changes (a failed build keeps the previous map) | `python3 -m rental_lookup.webmap.dev [PORT]` | `rental-map-dev` |
| Regenerate the metro overlay | `python3 scripts/fetch_metro_lines.py` | |
| Merge star export files | `python3 -m rental_lookup.stars OUTPUT INPUT [INPUT ...]` | |

Notes:

- NoBroker pages already saved under `data/raw_nb/` are reused; empty that folder (as
  `scripts/refresh_map.sh` does) to force a fresh fetch. The previous run is moved
  to `data/raw_nb_prev/` so the map can show delisted listings.
- `COOKIE` is an optional browser `Cookie` header for NoBroker / 99acres, only
  needed if requests get blocked (99acres often needs one behind Akamai).
- For 99acres, set `APIFY_TOKEN` in `.env` to use the Apify scraper instead of the
  JSON API / Chrome SSR path (`python3 -m pip install 'rental-lookup[acres99-apify]'`).
  Optional `APIFY_MAX_RESULTS` caps how many listings to buy (~$0.002 each).
- The map builder works with whatever data is present; every input except the
  template is optional.

### Configuration

Set `CARTO_BASEMAPS_KEY` (env or `.env`, see `.env.example`) for the CARTO light
basemap; without it the map uses Esri's keyless light-grey tiles.

Search areas and budgets are constants at the top of `sources/nobroker.py`,
`scoring.py` and `location.py`. Map quality weights default in
`webmap/ui/scoring/scoring.js`; edits made in Settings → Quality scoring are kept
in the browser.

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
2. Enable the workflow if it is disabled: `gh workflow enable "Update blr-rental-map"`.
3. Add an `APIFY_TOKEN` repository secret for 99acres (Chrome SSR is skipped on
   Actions; capped at `APIFY_MAX_RESULTS=200`). Without it the step soft-fails
   and the map builds from the other sources.
4. Optionally add a `CARTO_BASEMAPS_KEY` repository secret.

## Project layout

```
sources → data/ → enrichment → webmap builder → output/map.html

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

Stars live in the browser's `localStorage` and are never published. The serve /
dev commands also back them up to the gitignored
`data/cache/stars_and_dismissals.json`, and the "Saved state" panel
exports/imports a backup to move them between browsers.

Format: `{"starred": {url: timestamp}, "dismissed": {url: timestamp}}`. A
negative timestamp undoes the action; on merge, the latest action per URL wins.

## Places of interest

On the **Commute** tab, add places (office, gym, friends) by search, a full
Google Maps URL, `lat, lng`, or right-clicking the map. Each listing gets two
times per place:

- **Drive**: [OSRM](https://project-osrm.org) road time × 1.6 for traffic,
  cached in the browser; a straight-line estimate (`~`) shows until routed.
- **Metro**: walk or auto to a nearby station, ride (with line changes), then
  walk or auto on, using `data/metro_lines.json`.

The faster mode counts. A listing's commute score comes from its longest
commute across all places (100 at ≤10 minutes, 0 at 60). Tuning constants are
at the top of `ui/commute/metro.js`.

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
