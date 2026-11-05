# Contributing

Thanks for helping out! Bug fixes, scraper repairs and new sources are all welcome.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e '.[dev]'
python3 -m pytest
```

Use `python3` (macOS often has no `python` command). Without activating the venv, prefix commands with `.venv/bin/python3 -m …`.

The test suite needs no network access; NoBroker parsing is tested against the saved response in `data/spike/nobroker-sample-response.json`.

## Before opening a pull request

- Run `python3 -m pytest` and make sure it passes.
- Keep changes focused; one fix or feature per pull request.
- Don't commit scraped data (`data/raw*/`), generated output (`output/`), or `.env`. Stars/dismissals are gitignored (`data/cache/stars_and_dismissals.json`).
- If you change what the map shows, check it in a browser. `python3 -m rental_lookup.webmap.dev` rebuilds and reloads the page on every save.

## Code conventions

- Match the surrounding code: descriptive names, short docstrings, and comments only where the code can't explain itself.
- Every file and folder location belongs in `rental_lookup/paths.py`.
- Scrapers must stay polite: keep the delay between requests.
- The listing records written by `webmap/builder.py` are read by the page's scripts under `webmap/ui/` (assembled by `webmap/template.html`). Rename a record field in both places together.
- Don't change the star file format (`{"starred": {url: ts}, "dismissed": {url: ts}}`) or the browser `localStorage` keys (`rental_starred`, `rental_dismissed`); existing users' saved stars depend on them.

## When a scraper breaks

Portals change their internal APIs without notice. The usual fix:

1. Open the site with your browser's developer tools on the Network tab, filter by XHR / Fetch, and run the same search.
2. Compare the request and response with the notes in `data/spike/*-api-contract.md` (one per source).
3. Update the request parameters or field mapping in `rental_lookup/sources/`, and the contract notes, then add or update a test with a small sample response.

## Adding a new source

1. Add `rental_lookup/sources/<name>.py` with a `fetch_all(...)` that saves raw pages under a new directory in `paths.py`, an `iter_saved_listings(...)` that reads them back, and a `normalize_listing(raw) -> Listing | None`.
2. Prefix listing ids (as MagicBricks does with `mb_`) so they can't collide.
3. Register it in `SOURCES` in `rental_lookup/sources/__main__.py` so `rental-map-fetch <name>` works.
4. Add a `<name>_record(...)` in `webmap/builder.py` producing the same keys as the existing records, and decide how it should be de-duplicated against the others (`webmap/dedupe.py`).
5. Give its records a short `source` code and add a source chip for it (`ui/filters/filters-sheet.html`, `ui/filters/filters.js` and the source filter in `ui/core/render.js`).
6. Add the fetch step to `scripts/refresh_map.sh` (and the step labels in `ui/resync-dialog/resync-dialog.js` and `RESYNC_TOTAL_STEPS` in `webmap/server.py`) and to `.github/workflows/update-map.yml`; cache its raw folder there if re-fetching is expensive.
7. Add tests for parsing and normalisation, and a `data/spike/<name>-api-contract.md` describing the endpoint and field mapping.

## Reporting bugs

Open a [GitHub issue](https://github.com/sarweshshah/blr-rental-map/issues). For a broken scraper, include the source, the error output and, if you can, the request you see in the browser's developer tools (with cookies and personal data removed). Security problems go through [SECURITY.md](SECURITY.md) instead.
